from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia

from .models import Aviso, AvisoLectura


def crear_membresia(condominio, rol, **user_kwargs):
    """Sin password: los tests se autentican con force_login."""
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(user=user, condominio=condominio, rol=rol, terminos_aceptados_en=timezone.now())


class AvisoApiTests(TestCase):
    """Solo directiva/administración pueden crear o eliminar avisos
    (EsDirectivaOAdministracion); cualquier miembro puede leerlos. También
    confirma el aislamiento de tenant de CondominioQuerysetMixin."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Avisos A", plan="premium")
        cls.otro_condominio = Condominio.objects.create(nombre="Test Avisos B", plan="premium")

    def setUp(self):
        self.directiva = crear_membresia(self.condominio, "directiva", username="aviso_directiva")
        self.residente = crear_membresia(self.condominio, "residente", username="aviso_residente")
        self.aviso = Aviso.objects.create(condominio=self.condominio, autor=self.directiva, titulo="Corte de agua", cuerpo="Mañana de 9 a 12.")
        Aviso.objects.create(
            condominio=self.otro_condominio,
            autor=crear_membresia(self.otro_condominio, "directiva", username="aviso_otro_directiva"),
            titulo="No debería verse", cuerpo="...",
        )

    def test_residente_puede_listar_solo_los_de_su_condominio(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("aviso-list"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        resultados = datos["results"] if isinstance(datos, dict) else datos
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["titulo"], "Corte de agua")

    def test_residente_no_puede_crear_un_aviso(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("aviso-list"), {"titulo": "Prueba", "cuerpo": "..."})
        self.assertEqual(r.status_code, 403)

    def test_directiva_puede_crear_un_aviso(self):
        self.client.force_login(self.directiva.user)
        r = self.client.post(reverse("aviso-list"), {"titulo": "Asamblea", "cuerpo": "Sábado 10am"})
        self.assertEqual(r.status_code, 201)
        aviso = Aviso.objects.get(titulo="Asamblea")
        self.assertEqual(aviso.condominio, self.condominio)
        self.assertEqual(aviso.autor, self.directiva)

    def test_residente_no_puede_eliminar_un_aviso(self):
        self.client.force_login(self.residente.user)
        r = self.client.delete(reverse("aviso-detail", args=[self.aviso.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Aviso.objects.filter(pk=self.aviso.pk).exists())

    def test_directiva_puede_eliminar_un_aviso(self):
        self.client.force_login(self.directiva.user)
        r = self.client.delete(reverse("aviso-detail", args=[self.aviso.pk]))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Aviso.objects.filter(pk=self.aviso.pk).exists())

    def test_sin_autenticar_no_puede_listar(self):
        r = self.client.get(reverse("aviso-list"))
        self.assertEqual(r.status_code, 401)

    def test_crear_aviso_llama_a_ambos_canales_de_push(self):
        self.client.force_login(self.directiva.user)
        with patch("comunicacion.services.enviar_push_a_condominio") as mock_expo, \
             patch("comunicacion.services.enviar_web_push_a_condominio") as mock_web:
            r = self.client.post(reverse("aviso-list"), {"titulo": "Asamblea", "cuerpo": "Sábado 10am"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(mock_expo.call_count, 1)
        self.assertEqual(mock_web.call_count, 1)
        self.assertEqual(mock_expo.call_args.kwargs["excluir_user_id"], self.directiva.user_id)
        self.assertEqual(mock_web.call_args.kwargs["excluir_user_id"], self.directiva.user_id)


class AvisoLecturaTests(TestCase):
    """Confirmación de lectura: cualquier miembro puede marcar un aviso como
    visto, pero las estadísticas ("Visto por X de Y vecinos") solo las ve
    directiva/administración -- a un residente no le aporta nada."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Lectura Avisos", plan="premium")
        cls.otro_condominio = Condominio.objects.create(nombre="Test Lectura Avisos B", plan="premium")

    def setUp(self):
        self.directiva = crear_membresia(self.condominio, "directiva", username="lectura_directiva")
        self.residente = crear_membresia(self.condominio, "residente", username="lectura_residente")
        self.otro_residente = crear_membresia(self.condominio, "residente", username="lectura_residente_2")
        self.aviso = Aviso.objects.create(condominio=self.condominio, autor=self.directiva, titulo="Corte de agua", cuerpo="Mañana de 9 a 12.")

    def test_marcar_leido_crea_el_registro(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("aviso-marcar-leido", args=[self.aviso.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AvisoLectura.objects.filter(aviso=self.aviso, membresia=self.residente).exists())

    def test_marcar_leido_es_idempotente(self):
        self.client.force_login(self.residente.user)
        self.client.post(reverse("aviso-marcar-leido", args=[self.aviso.pk]))
        r = self.client.post(reverse("aviso-marcar-leido", args=[self.aviso.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AvisoLectura.objects.filter(aviso=self.aviso, membresia=self.residente).count(), 1)

    def test_no_puede_marcar_leido_un_aviso_de_otro_condominio(self):
        autor_ajeno = crear_membresia(self.otro_condominio, "directiva", username="lectura_directiva_ajena")
        aviso_ajeno = Aviso.objects.create(condominio=self.otro_condominio, autor=autor_ajeno, titulo="Ajeno", cuerpo="...")
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("aviso-marcar-leido", args=[aviso_ajeno.pk]))
        self.assertEqual(r.status_code, 404)

    def test_residente_no_ve_las_estadisticas_de_lectura(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("aviso-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertIsNone(resultados[0]["leido_por_count"])
        self.assertIsNone(resultados[0]["total_destinatarios"])

    def test_directiva_ve_cuantos_vecinos_lo_han_visto(self):
        AvisoLectura.objects.create(aviso=self.aviso, membresia=self.residente)
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("aviso-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual(resultados[0]["leido_por_count"], 1)
        self.assertEqual(resultados[0]["total_destinatarios"], 3)


class AvisoAdminTests(TestCase):
    """Filtro de condominio como desplegable con buscador (ver AvisoAdmin)
    -- confirma que el changelist sigue renderizando bien."""

    def test_changelist_renderiza_ok(self):
        condominio = Condominio.objects.create(nombre="Test Admin Aviso", plan="premium")
        autor = crear_membresia(condominio, "directiva", username="admin_aviso_autor")
        Aviso.objects.create(condominio=condominio, autor=autor, titulo="Corte de agua", cuerpo="Mañana de 9 a 12.")
        staff = User.objects.create_superuser(username="admin_aviso_staff", password="x", email="admin_aviso_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/comunicacion/aviso/")
        self.assertEqual(r.status_code, 200)

    def test_el_listado_no_crece_en_queries_por_fila(self):
        """autor es un Membresia, y Membresia.__str__ toca autor.user y
        autor.condominio -- sin list_select_related, cada fila nueva sumaría
        2 queries más. Confirma que el total no depende de cuántas filas hay."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        condominio = Condominio.objects.create(nombre="Test N+1 Aviso", plan="premium")
        staff = User.objects.create_superuser(username="n1_aviso_staff", password="x")
        self.client.force_login(staff)

        autor = crear_membresia(condominio, "directiva", username="n1_aviso_autor_0")
        Aviso.objects.create(condominio=condominio, autor=autor, titulo="Aviso 0", cuerpo="...")
        with CaptureQueriesContext(connection) as ctx_una_fila:
            self.client.get("/admin/comunicacion/aviso/")

        for i in range(1, 4):
            autor = crear_membresia(condominio, "directiva", username=f"n1_aviso_autor_{i}")
            Aviso.objects.create(condominio=condominio, autor=autor, titulo=f"Aviso {i}", cuerpo="...")
        with CaptureQueriesContext(connection) as ctx_cuatro_filas:
            self.client.get("/admin/comunicacion/aviso/")

        self.assertEqual(len(ctx_una_fila.captured_queries), len(ctx_cuatro_filas.captured_queries))


class AvisoDelegadoTests(TestCase):
    """Un delegado puede publicar avisos, pero acotados a su propia torre --
    a diferencia de directiva/administración, que publican a todo el
    condominio. Solo directiva/administración pueden eliminar (moderación)."""

    @classmethod
    def setUpTestData(cls):
        from core.models import Torre, Unidad

        cls.condominio = Condominio.objects.create(nombre="Test Aviso Delegado", plan="premium")
        cls.torre1 = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.torre2 = Torre.objects.create(condominio=cls.condominio, nombre="2")
        cls.unidad_t1 = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre1, numero="101")
        cls.unidad_t2 = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre2, numero="201")

    def setUp(self):
        self.delegado_t1 = crear_membresia(self.condominio, "delegado", username="aviso_delegado_t1")
        self.delegado_t1.unidad = self.unidad_t1
        self.delegado_t1.save(update_fields=["unidad"])

        self.residente_t1 = crear_membresia(self.condominio, "residente", username="aviso_residente_t1")
        self.residente_t1.unidad = self.unidad_t1
        self.residente_t1.save(update_fields=["unidad"])

        self.residente_t2 = crear_membresia(self.condominio, "residente", username="aviso_residente_t2")
        self.residente_t2.unidad = self.unidad_t2
        self.residente_t2.save(update_fields=["unidad"])

        self.directiva = crear_membresia(self.condominio, "directiva", username="aviso_delegado_directiva")

    def test_delegado_puede_crear_un_aviso(self):
        self.client.force_login(self.delegado_t1.user)
        r = self.client.post(reverse("aviso-list"), {"titulo": "Reunión de torre", "cuerpo": "Este sábado"})
        self.assertEqual(r.status_code, 201)
        aviso = Aviso.objects.get(titulo="Reunión de torre")
        self.assertEqual(aviso.torre, self.torre1)

    def test_residente_de_otra_torre_no_ve_el_aviso_del_delegado(self):
        Aviso.objects.create(condominio=self.condominio, autor=self.delegado_t1, torre=self.torre1, titulo="Solo T1", cuerpo="...")
        self.client.force_login(self.residente_t2.user)
        r = self.client.get(reverse("aviso-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([a["titulo"] for a in resultados], [])

    def test_residente_de_la_misma_torre_si_ve_el_aviso_del_delegado(self):
        Aviso.objects.create(condominio=self.condominio, autor=self.delegado_t1, torre=self.torre1, titulo="Solo T1", cuerpo="...")
        self.client.force_login(self.residente_t1.user)
        r = self.client.get(reverse("aviso-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([a["titulo"] for a in resultados], ["Solo T1"])

    def test_directiva_ve_los_avisos_de_cualquier_torre(self):
        Aviso.objects.create(condominio=self.condominio, autor=self.delegado_t1, torre=self.torre1, titulo="Solo T1", cuerpo="...")
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("aviso-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([a["titulo"] for a in resultados], ["Solo T1"])

    def test_delegado_no_puede_eliminar_su_propio_aviso(self):
        aviso = Aviso.objects.create(condominio=self.condominio, autor=self.delegado_t1, torre=self.torre1, titulo="Mío", cuerpo="...")
        self.client.force_login(self.delegado_t1.user)
        r = self.client.delete(reverse("aviso-detail", args=[aviso.pk]))
        self.assertEqual(r.status_code, 403)

    def test_notificacion_del_delegado_queda_acotada_a_su_torre(self):
        self.client.force_login(self.delegado_t1.user)
        with patch("comunicacion.services.enviar_push_a_condominio") as mock_expo, \
             patch("comunicacion.services.enviar_web_push_a_condominio") as mock_web:
            r = self.client.post(reverse("aviso-list"), {"titulo": "Reunión de torre", "cuerpo": "Este sábado"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(mock_expo.call_args.kwargs["torre"], self.torre1)
        self.assertEqual(mock_web.call_args.kwargs["torre"], self.torre1)

    def test_aviso_de_directiva_no_queda_acotado_a_ninguna_torre(self):
        self.client.force_login(self.directiva.user)
        r = self.client.post(reverse("aviso-list"), {"titulo": "General", "cuerpo": "..."})
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(Aviso.objects.get(titulo="General").torre)

