from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia

from .models import Alerta


def crear_membresia(condominio, rol, **user_kwargs):
    """Sin password: los tests se autentican con force_login."""
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(user=user, condominio=condominio, rol=rol, terminos_aceptados_en=timezone.now())


class FiltroEstadoAlertaTests(TestCase):
    """`?estado=activa` alguna vez no filtraba nada (no había filter_backend
    configurado) y 'Alertas activas' mostraba TODAS las alertas, incluidas
    las resueltas. Esto fija ese comportamiento."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Filtro Alertas", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", username="filtro_residente")
        self.client.force_login(self.membresia.user)
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="robo", estado="activa")
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="incendio", estado="resuelta")
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="otro", estado="falsa_alarma")

    def test_estado_activa_filtra_de_verdad(self):
        r = self.client.get(reverse("alerta-list") + "?estado=activa")
        datos = r.json()
        resultados = datos["results"] if isinstance(datos, dict) else datos
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["tipo"], "robo")

    def test_sin_filtro_devuelve_todas(self):
        r = self.client.get(reverse("alerta-list"))
        datos = r.json()
        resultados = datos["results"] if isinstance(datos, dict) else datos
        self.assertEqual(len(resultados), 3)


class AutoCierreYResolucionAbiertaTests(TestCase):
    """Cualquier rol puede resolver una alerta (no solo directiva/conserjería,
    ver TieneMembresia en vez de EsDirectivaOConserje), y una alerta activa
    hace más de 30 min se autocierra sola al listarse."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Autocierre", plan="premium")

    def setUp(self):
        self.autor = crear_membresia(self.condominio, "residente", username="auto_autor")
        self.vecino = crear_membresia(self.condominio, "residente", username="auto_vecino")

    def test_un_residente_puede_resolver_la_alerta_de_otro(self):
        alerta = Alerta.objects.create(condominio=self.condominio, autor=self.autor, tipo="robo", estado="activa")
        self.client.force_login(self.vecino.user)
        r = self.client.patch(
            reverse("alerta-resolver", kwargs={"pk": alerta.pk}),
            data={"estado": "resuelta"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, "resuelta")
        self.assertEqual(alerta.resuelta_por_id, self.vecino.pk)

    def test_alerta_vieja_se_autocierra_al_listar(self):
        alerta = Alerta.objects.create(condominio=self.condominio, autor=self.autor, tipo="robo", estado="activa")
        Alerta.objects.filter(pk=alerta.pk).update(fecha_creacion=timezone.now() - timedelta(minutes=45))
        self.client.force_login(self.vecino.user)
        self.client.get(reverse("alerta-list"))
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, "auto_cerrada")


class NotificarAlertaTests(TestCase):
    """Crear una alerta de verdad (vía la API, como hace el botón de pánico)
    debe disparar los dos canales de push -- Expo (app nativa futura) y Web
    Push (la PWA, agregada hoy) -- sin pegarle a ningún servicio real."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Notificar Alerta", plan="premium")

    def test_crear_alerta_llama_a_ambos_canales_de_push(self):
        membresia = crear_membresia(self.condominio, "residente", username="notif_autor")
        self.client.force_login(membresia.user)
        with patch("alertas.services.enviar_push_a_condominio") as mock_expo, \
             patch("alertas.services.enviar_web_push_a_condominio") as mock_web:
            r = self.client.post(reverse("alerta-list"), {"tipo": "robo", "mensaje": "Prueba"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(mock_expo.call_count, 1)
        self.assertEqual(mock_web.call_count, 1)
        self.assertEqual(mock_expo.call_args.kwargs["excluir_user_id"], membresia.user_id)
        self.assertEqual(mock_web.call_args.kwargs["excluir_user_id"], membresia.user_id)


class AlertaHistorialViewTests(TestCase):
    """Página web del historial (`alertas/views.py`) -- distinta del endpoint
    de API que prueba FiltroEstadoAlertaTests arriba."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Historial Alertas", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", username="historial_residente")
        self.client.force_login(self.membresia.user)
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="robo", estado="activa")
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="incendio", estado="resuelta")

    def test_sin_filtro_muestra_todas(self):
        r = self.client.get(reverse("alertas-historial"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["alertas"]), 2)
        self.assertEqual(r.context["estado_seleccionado"], "")

    def test_filtro_por_estado(self):
        r = self.client.get(reverse("alertas-historial") + "?estado=resuelta")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["alertas"]), 1)
        self.assertEqual(r.context["alertas"][0].tipo, "incendio")
        self.assertEqual(r.context["estado_seleccionado"], "resuelta")


class AlertaHistorialMuestraBlockTests(TestCase):
    """El historial mostraba el depto del autor/resolutor pero no el block --
    ahora muestra ambos cuando la unidad tiene torre asignada."""

    def test_muestra_el_block_ademas_del_depto(self):
        from core.models import Torre, Unidad

        condominio = Condominio.objects.create(nombre="Test Historial Block", plan="premium")
        torre = Torre.objects.create(condominio=condominio, nombre="9")
        unidad = Unidad.objects.create(condominio=condominio, torre=torre, numero="302")
        autor = crear_membresia(condominio, "residente", username="historial_block_autor")
        autor.unidad = unidad
        autor.save(update_fields=["unidad"])
        self.client.force_login(autor.user)
        Alerta.objects.create(condominio=condominio, autor=autor, tipo="robo", estado="activa")

        r = self.client.get(reverse("alertas-historial"))
        self.assertContains(r, f"{condominio.etiqueta_torre} 9, {condominio.etiqueta_unidad.lower()} 302")
