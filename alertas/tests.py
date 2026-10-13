from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia

from .models import TIPO_CHOICES, Alerta
from .services import TITULOS_POR_TIPO


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

    def test_todos_los_tipos_de_alerta_tienen_titulo_de_notificacion(self):
        """Si se agrega un tipo nuevo a TIPO_CHOICES sin agregarle su título en
        TITULOS_POR_TIPO, notificar_alerta no explota (usa el de "otro" como
        respaldo) pero manda un título genérico -- este test obliga a no
        olvidarlo."""
        codigos_con_titulo = set(TITULOS_POR_TIPO)
        codigos_declarados = {codigo for codigo, _ in TIPO_CHOICES}
        self.assertEqual(codigos_declarados, codigos_con_titulo)

    def test_cada_tipo_nuevo_crea_la_alerta_y_usa_su_propio_titulo(self):
        membresia = crear_membresia(self.condominio, "residente", username="notif_tipos")
        self.client.force_login(membresia.user)
        tipos_nuevos = [
            "emergencia_medica", "persona_extrana", "fuga_gas", "fuga_agua",
            "atrapado_ascensor", "objeto_sospechoso", "rina_disturbio",
        ]
        for tipo in tipos_nuevos:
            with patch("alertas.services.enviar_push_a_condominio") as mock_expo, \
                 patch("alertas.services.enviar_web_push_a_condominio"):
                r = self.client.post(reverse("alerta-list"), {"tipo": tipo}, content_type="application/json")
            self.assertEqual(r.status_code, 201)
            self.assertEqual(mock_expo.call_args.args[1], TITULOS_POR_TIPO[tipo])


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


class CondominiosVecinosCompartenAlertasTests(TestCase):
    """Dos condominios que comparten vecindario (M2M condominios_vecinos,
    simétrico) ven y reciben notificación de las alertas del otro -- pero
    nada más (miembros, gastos comunes, etc. siguen aislados por separado,
    eso no se tocó en este cambio)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio_a = Condominio.objects.create(nombre="Barrio A", plan="premium")
        cls.condominio_b = Condominio.objects.create(nombre="Barrio B", plan="premium")
        cls.condominio_suelto = Condominio.objects.create(nombre="Barrio Suelto", plan="premium")
        cls.condominio_a.condominios_vecinos.add(cls.condominio_b)

    def test_el_vinculo_es_simetrico(self):
        self.assertIn(self.condominio_b, self.condominio_a.condominios_vecinos.all())
        self.assertIn(self.condominio_a, self.condominio_b.condominios_vecinos.all())
        self.assertNotIn(self.condominio_suelto, self.condominio_a.condominios_vecinos.all())

    def test_ids_red_alertas_incluye_al_propio_y_a_los_vecinos(self):
        ids = self.condominio_a.ids_red_alertas
        self.assertCountEqual(ids, [self.condominio_a.pk, self.condominio_b.pk])
        self.assertEqual(self.condominio_suelto.ids_red_alertas, [self.condominio_suelto.pk])

    def test_un_residente_ve_la_alerta_activa_del_condominio_vecino(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor")
        alerta_b = Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_a = crear_membresia(self.condominio_a, "residente", username="vecino_a_residente")
        self.client.force_login(residente_a.user)
        r = self.client.get(reverse("alerta-list") + "?estado=activa")
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([a["id"] for a in resultados], [alerta_b.id])
        self.assertEqual(resultados[0]["condominio_nombre"], "Barrio B")

    def test_un_condominio_sin_vinculo_no_ve_la_alerta_ajena(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor2")
        Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_suelto = crear_membresia(self.condominio_suelto, "residente", username="suelto_residente")
        self.client.force_login(residente_suelto.user)
        r = self.client.get(reverse("alerta-list") + "?estado=activa")
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual(resultados, [])

    def test_un_residente_vecino_puede_resolver_la_alerta_del_otro_condominio(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor3")
        alerta_b = Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_a = crear_membresia(self.condominio_a, "residente", username="vecino_a_resuelve")
        self.client.force_login(residente_a.user)
        r = self.client.patch(
            reverse("alerta-resolver", kwargs={"pk": alerta_b.pk}),
            data={"estado": "falsa_alarma"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        alerta_b.refresh_from_db()
        self.assertEqual(alerta_b.estado, "falsa_alarma")
        self.assertEqual(alerta_b.resuelta_por_id, residente_a.pk)

    def test_el_historial_del_condominio_a_incluye_las_del_vecino_b(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor4")
        Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_a = crear_membresia(self.condominio_a, "residente", username="vecino_a_historial")
        self.client.force_login(residente_a.user)
        r = self.client.get(reverse("alertas-historial"))
        self.assertEqual(len(r.context["alertas"]), 1)
        self.assertContains(r, "Barrio B")

    def test_notificar_alerta_avisa_tambien_al_condominio_vecino(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor5")
        self.client.force_login(autor_b.user)
        with patch("alertas.services.enviar_push_a_condominio") as mock_expo, \
             patch("alertas.services.enviar_web_push_a_condominio") as mock_web:
            r = self.client.post(reverse("alerta-list"), {"tipo": "robo"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(mock_expo.call_count, 2)
        self.assertEqual(mock_web.call_count, 2)
        condominios_avisados = {llamada.args[0] for llamada in mock_expo.call_args_list}
        self.assertEqual(condominios_avisados, {self.condominio_a, self.condominio_b})


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


class AlertaAdminTests(TestCase):
    """Insignias de color para tipo/estado (ver tipo_badge/estado_badge en
    alertas/admin.py) -- confirma que el changelist renderiza bien con
    ellas, no solo que el método en sí devuelve el valor esperado."""

    def test_changelist_renderiza_con_las_insignias(self):
        condominio = Condominio.objects.create(nombre="Test Admin Alerta", plan="premium")
        autor = crear_membresia(condominio, "residente", username="admin_alerta_autor")
        Alerta.objects.create(condominio=condominio, autor=autor, tipo="robo", estado="activa")
        staff = User.objects.create_superuser(username="admin_alerta_staff", password="x", email="admin_alerta_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/alertas/alerta/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Robo")
        self.assertContains(r, "Activa")
