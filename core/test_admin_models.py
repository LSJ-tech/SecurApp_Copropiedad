import datetime

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .admin import (
    MAX_FILAS_INLINE,
    CodigoInvitacionAdmin,
    CondominioAdmin,
    MembresiaInline,
    UnidadInline,
    cambiar_a_free,
    cambiar_a_premium,
    extender_30_dias,
    marcar_atendida,
    marcar_atendido,
)
from .models import CodigoInvitacion, Condominio, Membresia, SolicitudAcceso, SolicitudEliminacion, Unidad


class ExtenderTreintaDiasTests(TestCase):
    def test_sin_pagado_hasta_extiende_desde_hoy(self):
        condominio = Condominio.objects.create(nombre="Test Extender A", plan="premium", pagado_hasta=None)
        extender_30_dias(None, None, Condominio.objects.filter(pk=condominio.pk))
        condominio.refresh_from_db()
        self.assertEqual(condominio.pagado_hasta, timezone.localdate() + datetime.timedelta(days=30))

    def test_pagado_hasta_futuro_extiende_desde_esa_fecha_no_desde_hoy(self):
        fecha_futura = timezone.localdate() + datetime.timedelta(days=10)
        condominio = Condominio.objects.create(nombre="Test Extender B", plan="premium", pagado_hasta=fecha_futura)
        extender_30_dias(None, None, Condominio.objects.filter(pk=condominio.pk))
        condominio.refresh_from_db()
        self.assertEqual(condominio.pagado_hasta, fecha_futura + datetime.timedelta(days=30))

    def test_pagado_hasta_vencido_extiende_desde_hoy_no_desde_el_pasado(self):
        fecha_pasada = timezone.localdate() - datetime.timedelta(days=5)
        condominio = Condominio.objects.create(nombre="Test Extender C", plan="premium", pagado_hasta=fecha_pasada)
        extender_30_dias(None, None, Condominio.objects.filter(pk=condominio.pk))
        condominio.refresh_from_db()
        self.assertEqual(condominio.pagado_hasta, timezone.localdate() + datetime.timedelta(days=30))


class CambiarPlanTests(TestCase):
    def test_cambiar_a_free(self):
        condominio = Condominio.objects.create(nombre="Test Plan Free", plan="premium")
        cambiar_a_free(None, None, Condominio.objects.filter(pk=condominio.pk))
        condominio.refresh_from_db()
        self.assertEqual(condominio.plan, "free")

    def test_cambiar_a_premium(self):
        condominio = Condominio.objects.create(nombre="Test Plan Premium", plan="free")
        cambiar_a_premium(None, None, Condominio.objects.filter(pk=condominio.pk))
        condominio.refresh_from_db()
        self.assertEqual(condominio.plan, "premium")


class InlinesCapadosTests(TestCase):
    def setUp(self):
        self.condominio = Condominio.objects.create(nombre="Test Inline Cap", plan="premium")
        self.request = RequestFactory().get("/")
        self.request.user = User.objects.create_superuser(username="inline_cap_super", password="x")

    def test_unidad_inline_no_muestra_mas_del_tope(self):
        for i in range(MAX_FILAS_INLINE + 5):
            Unidad.objects.create(condominio=self.condominio, numero=str(i))
        inline = UnidadInline(Condominio, admin.site)
        qs = inline.get_queryset(self.request).filter(condominio=self.condominio)
        self.assertEqual(qs.count(), MAX_FILAS_INLINE)

    def test_membresia_inline_no_muestra_mas_del_tope(self):
        for i in range(MAX_FILAS_INLINE + 5):
            user = User.objects.create_user(username=f"inline_cap_{i}")
            Membresia.objects.create(user=user, condominio=self.condominio, rol="residente", terminos_aceptados_en=timezone.now())
        inline = MembresiaInline(Condominio, admin.site)
        qs = inline.get_queryset(self.request).filter(condominio=self.condominio)
        self.assertEqual(qs.count(), MAX_FILAS_INLINE)


class CondominioAdminEstadoSuscripcionTests(TestCase):
    def setUp(self):
        self.admin = CondominioAdmin(Condominio, admin.site)

    def test_sin_pagado_hasta_dice_sin_restriccion(self):
        condominio = Condominio.objects.create(nombre="Test Estado A", plan="premium", pagado_hasta=None)
        self.assertEqual(self.admin.estado_suscripcion(condominio), "Sin restricción")

    def test_pagado_hasta_futuro_dice_vigente(self):
        fecha = timezone.localdate() + datetime.timedelta(days=5)
        condominio = Condominio.objects.create(nombre="Test Estado B", plan="premium", pagado_hasta=fecha)
        self.assertEqual(self.admin.estado_suscripcion(condominio), f"Vigente hasta {fecha}")

    def test_pagado_hasta_pasado_dice_vencida(self):
        fecha = timezone.localdate() - datetime.timedelta(days=5)
        condominio = Condominio.objects.create(nombre="Test Estado C", plan="premium", pagado_hasta=fecha)
        self.assertEqual(self.admin.estado_suscripcion(condominio), f"Vencida hasta {fecha}")


class CodigoInvitacionAdminTests(TestCase):
    def setUp(self):
        self.admin = CodigoInvitacionAdmin(CodigoInvitacion, admin.site)

    def test_usado_display_false_sin_condominio(self):
        codigo = CodigoInvitacion.objects.create()
        self.assertFalse(self.admin.usado_display(codigo))

    def test_usado_display_true_con_condominio(self):
        condominio = Condominio.objects.create(nombre="Test Codigo Usado", plan="premium")
        codigo = CodigoInvitacion.objects.create(condominio=condominio)
        self.assertTrue(self.admin.usado_display(codigo))


class MarcarAtendidoTests(TestCase):
    def test_marcar_atendido_solicitud_acceso(self):
        solicitud = SolicitudAcceso.objects.create(condominio="Test", nombre="Ana", comuna="Valparaíso", telefono="+56911111111")
        marcar_atendido(None, None, SolicitudAcceso.objects.filter(pk=solicitud.pk))
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.atendido)

    def test_marcar_atendida_solicitud_eliminacion(self):
        solicitud = SolicitudEliminacion.objects.create(nombre="Ana", username="ana_test", condominio_nombre="Test")
        marcar_atendida(None, None, SolicitudEliminacion.objects.filter(pk=solicitud.pk))
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.atendida)
        self.assertIsNotNone(solicitud.fecha_atencion)


class MembresiaAdminChangelistTests(TestCase):
    """El filtro por condominio en /admin/core/membresia/ pasó de la lista
    larga de links por defecto a un desplegable con buscador
    (AutocompleteSelectFilter) -- esto confirma que la página sigue
    renderizando bien (requiere 'unfold.contrib.filters' en INSTALLED_APPS
    para que cargue su template) y que el filtro realmente filtra."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio_a = Condominio.objects.create(nombre="Test Admin Filtro A", plan="premium")
        cls.condominio_b = Condominio.objects.create(nombre="Test Admin Filtro B", plan="premium")
        user_a = User.objects.create_user(username="admfiltro_a")
        user_b = User.objects.create_user(username="admfiltro_b")
        Membresia.objects.create(user=user_a, condominio=cls.condominio_a, rol="residente", terminos_aceptados_en=timezone.now())
        Membresia.objects.create(user=user_b, condominio=cls.condominio_b, rol="residente", terminos_aceptados_en=timezone.now())

    def setUp(self):
        self.superuser = User.objects.create_superuser(username="admfiltro_staff", password="x")
        self.client.force_login(self.superuser)

    def test_changelist_renderiza_ok(self):
        r = self.client.get("/admin/core/membresia/")
        self.assertEqual(r.status_code, 200)

    def test_filtro_por_condominio_acota_los_resultados(self):
        r = self.client.get("/admin/core/membresia/", {"condominio__id__exact": self.condominio_a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "admfiltro_a")
        self.assertNotContains(r, "admfiltro_b")


class TorreYUnidadAdminFiltroCondominioTests(TestCase):
    """Mismo filtro-desplegable-con-buscador que Membresía, aplicado también
    a Torre y Unidad."""

    @classmethod
    def setUpTestData(cls):
        from .models import Torre

        cls.condominio_a = Condominio.objects.create(nombre="Test Torre Filtro A", plan="premium")
        cls.condominio_b = Condominio.objects.create(nombre="Test Torre Filtro B", plan="premium")
        cls.torre_a = Torre.objects.create(condominio=cls.condominio_a, nombre="Torre filtro A")
        Torre.objects.create(condominio=cls.condominio_b, nombre="Torre filtro B")
        cls.unidad_a = Unidad.objects.create(condominio=cls.condominio_a, numero="Unidad filtro A")
        Unidad.objects.create(condominio=cls.condominio_b, numero="Unidad filtro B")

    def setUp(self):
        self.superuser = User.objects.create_superuser(username="admfiltro_tu_staff", password="x")
        self.client.force_login(self.superuser)

    def test_torre_changelist_renderiza_y_filtra(self):
        r = self.client.get("/admin/core/torre/", {"condominio__id__exact": self.condominio_a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Torre filtro A")
        self.assertNotContains(r, "Torre filtro B")

    def test_unidad_changelist_renderiza_y_filtra(self):
        r = self.client.get("/admin/core/unidad/", {"condominio__id__exact": self.condominio_a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Unidad filtro A")
        self.assertNotContains(r, "Unidad filtro B")
