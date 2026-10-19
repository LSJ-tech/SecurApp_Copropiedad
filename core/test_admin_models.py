import datetime

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .admin import (
    MAX_FILAS_INLINE,
    CondominioAdmin,
    MembresiaAdmin,
    MembresiaInline,
    TorreAdmin,
    UnidadAdmin,
    UnidadInline,
    cambiar_a_free,
    cambiar_a_premium,
    extender_30_dias,
    marcar_atendida,
    marcar_atendido,
)
from .models import Condominio, Membresia, SolicitudAcceso, SolicitudEliminacion, Torre, Unidad


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
    """estado_suscripcion devuelve (clave_de_color, texto) -- ver el
    decorador @display(label=...) en CondominioAdmin, que arma la insignia
    de color en el changelist a partir de esa clave."""

    def setUp(self):
        self.admin = CondominioAdmin(Condominio, admin.site)

    def test_sin_pagado_hasta_dice_sin_restriccion(self):
        condominio = Condominio.objects.create(nombre="Test Estado A", plan="premium", pagado_hasta=None)
        self.assertEqual(self.admin.estado_suscripcion(condominio), ("libre", "Sin restricción"))

    def test_pagado_hasta_futuro_dice_vigente(self):
        fecha = timezone.localdate() + datetime.timedelta(days=5)
        condominio = Condominio.objects.create(nombre="Test Estado B", plan="premium", pagado_hasta=fecha)
        self.assertEqual(self.admin.estado_suscripcion(condominio), ("vigente", f"Vigente hasta {fecha:%d-%m-%Y}"))

    def test_pagado_hasta_pasado_dice_vencida(self):
        fecha = timezone.localdate() - datetime.timedelta(days=5)
        condominio = Condominio.objects.create(nombre="Test Estado C", plan="premium", pagado_hasta=fecha)
        self.assertEqual(self.admin.estado_suscripcion(condominio), ("vencida", "Vencida hace 5 días"))

    def test_changelist_renderiza_con_la_insignia(self):
        Condominio.objects.create(nombre="Test Estado Changelist", plan="premium", pagado_hasta=None)
        staff = User.objects.create_superuser(username="admin_condo_estado_staff", password="x", email="admin_condo_estado_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/core/condominio/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Sin restricción")


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

    def test_changelist_muestra_la_insignia_de_rol(self):
        r = self.client.get("/admin/core/membresia/")
        self.assertContains(r, "Residente")

    def test_el_listado_no_crece_en_queries_por_fila(self):
        """user, condominio y unidad (con su propio torre/condominio para
        Unidad.__str__) se muestran en cada fila -- sin list_select_related,
        cada membresía nueva sumaría varias queries más."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx_dos_filas:
            self.client.get("/admin/core/membresia/")

        for i in range(4):
            user = User.objects.create_user(username=f"n1_membresia_{i}")
            Membresia.objects.create(user=user, condominio=self.condominio_a, rol="residente", terminos_aceptados_en=timezone.now())
        with CaptureQueriesContext(connection) as ctx_seis_filas:
            self.client.get("/admin/core/membresia/")

        self.assertEqual(len(ctx_dos_filas.captured_queries), len(ctx_seis_filas.captured_queries))

    def test_tiene_el_formulario_y_boton_de_aplicar_filtros(self):
        """list_filter_submit=True es obligatorio para que el desplegable
        (AutocompleteSelectFilter) sirva de algo -- sin él, Unfold renderiza
        un <div> en vez de un <form> y elegir una opción no hace nada
        (bug real encontrado por el usuario: "intenté hacer un filtro pero
        no se aplica")."""
        r = self.client.get("/admin/core/membresia/")
        self.assertContains(r, 'id="filter-form"')

    def test_filtro_por_condominio_acota_los_resultados(self):
        r = self.client.get("/admin/core/membresia/", {"condominio__id__exact": self.condominio_a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "admfiltro_a")
        self.assertNotContains(r, "admfiltro_b")


class SinUnidadFilterTests(TestCase):
    """Filtro "unidad asignada" en /admin/core/membresia/ -- mismo patrón
    que SinCondominioFilter (Usuarios), pero del otro lado de la relación
    opcional: encuentra membresías sin depto asignado."""

    @classmethod
    def setUpTestData(cls):
        # Nombres a propósito sin la palabra "unidad" adentro -- el
        # parameter_name del filtro es "con_unidad" y aparece en los links
        # del propio widget de filtros (ver la misma trampa con
        # SinCondominioFilterTests).
        condominio = Condominio.objects.create(nombre="Test Sin Unidad", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        user_con_depto = User.objects.create_user(username="miembro_con_depto_xyz")
        cls.membresia_con_depto = Membresia.objects.create(user=user_con_depto, condominio=condominio, rol="residente", unidad=unidad, terminos_aceptados_en=timezone.now())
        user_sin_depto = User.objects.create_user(username="miembro_sin_depto_xyz")
        cls.membresia_sin_depto = Membresia.objects.create(user=user_sin_depto, condominio=condominio, rol="residente", terminos_aceptados_en=timezone.now())

    def setUp(self):
        self.staff = User.objects.create_superuser(username="sinunidad_staff", password="x", email="sinunidad_staff@example.com")
        self.client.force_login(self.staff)

    def test_filtro_no_muestra_solo_los_sin_unidad(self):
        r = self.client.get("/admin/core/membresia/", {"con_unidad": "no"})
        self.assertContains(r, "miembro_sin_depto_xyz")
        self.assertNotContains(r, "miembro_con_depto_xyz")

    def test_filtro_si_muestra_solo_los_con_unidad(self):
        r = self.client.get("/admin/core/membresia/", {"con_unidad": "si"})
        self.assertContains(r, "miembro_con_depto_xyz")
        self.assertNotContains(r, "miembro_sin_depto_xyz")

    def test_sin_filtro_muestra_a_todos(self):
        r = self.client.get("/admin/core/membresia/")
        self.assertContains(r, "miembro_con_depto_xyz")
        self.assertContains(r, "miembro_sin_depto_xyz")


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
        cls.unidad_a = Unidad.objects.create(condominio=cls.condominio_a, torre=cls.torre_a, numero="Unidad filtro A")
        Unidad.objects.create(condominio=cls.condominio_b, numero="Unidad filtro B")

    def setUp(self):
        self.superuser = User.objects.create_superuser(username="admfiltro_tu_staff", password="x")
        self.client.force_login(self.superuser)

    def test_torre_changelist_renderiza_y_filtra(self):
        r = self.client.get("/admin/core/torre/", {"condominio__id__exact": self.condominio_a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Torre filtro A")
        self.assertNotContains(r, "Torre filtro B")

    def test_torre_tiene_boton_de_aplicar_filtros(self):
        r = self.client.get("/admin/core/torre/")
        self.assertContains(r, 'id="filter-form"')

    def test_unidad_changelist_renderiza_y_filtra(self):
        r = self.client.get("/admin/core/unidad/", {"condominio__id__exact": self.condominio_a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Unidad filtro A")
        self.assertNotContains(r, "Unidad filtro B")

    def test_unidad_tiene_boton_de_aplicar_filtros(self):
        r = self.client.get("/admin/core/unidad/")
        self.assertContains(r, 'id="filter-form"')

    def test_unidad_changelist_filtra_por_torre(self):
        unidad_otra_torre = Unidad.objects.create(condominio=self.condominio_a, numero="Unidad filtro C")
        r = self.client.get("/admin/core/unidad/", {"torre__id__exact": self.torre_a.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Unidad filtro A")
        self.assertNotContains(r, unidad_otra_torre.numero)


class UnidadAdminCondominioSoloAlCrearTests(TestCase):
    """Una Unidad puede estar compartida por varios residentes (ej. pareja
    en el mismo depto, todos con su Membresia apuntando a la misma fila) --
    cambiar su `condominio` desde el admin después de creada mueve a TODOS
    los que la comparten de una, no solo a la persona que se quería mover
    (justo el error real reportado: "mové un usuario del depto 54 de Empart
    y se movieron todos"). La forma segura de mover a una sola persona es
    MoverMiembroView (ver core/views.py), que re-apunta la Membresia, nunca
    la Unidad. Acá el campo queda de solo lectura una vez creada, para que
    no se pueda repetir ese error desde el admin."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Unidad Condominio Fijo", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="54")

    def setUp(self):
        self.client.force_login(User.objects.create_superuser(username="unidad_condominio_fijo_super", password="x"))

    def test_el_campo_condominio_es_de_solo_lectura_al_editar(self):
        r = self.client.get(f"/admin/core/unidad/{self.unidad.pk}/change/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'name="condominio"')

    def test_intentar_cambiar_el_condominio_por_post_no_lo_mueve(self):
        otro_condominio = Condominio.objects.create(nombre="Test Unidad Condominio Fijo Otro", plan="premium")
        r = self.client.post(f"/admin/core/unidad/{self.unidad.pk}/change/", {
            "condominio": otro_condominio.pk, "numero": "54", "calle": "", "alicuota": "",
        })
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.condominio_id, self.condominio.pk)

    def test_el_campo_condominio_sigue_editable_al_crear(self):
        r = self.client.get("/admin/core/unidad/add/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'name="condominio"')


class UnidadTorreDeOtroCondominioTests(TestCase):
    """El desplegable de torre en el admin de Unidad lista TODAS las torres
    de TODOS los condominios (ver Torre.__str__, que agrega el condominio
    entre paréntesis justo por eso) -- con varios clientes reales es fácil
    elegir una de otro condominio por error. Esto lo bloquea al guardar,
    sea cual sea el formulario (admin normal o la acción en lote)."""

    @classmethod
    def setUpTestData(cls):
        from .models import Torre

        cls.condominio_a = Condominio.objects.create(nombre="Test Torre Ajena A", plan="premium")
        cls.condominio_b = Condominio.objects.create(nombre="Test Torre Ajena B", plan="premium")
        cls.torre_b = Torre.objects.create(condominio=cls.condominio_b, nombre="1")

    def test_el_modelo_rechaza_una_torre_de_otro_condominio(self):
        unidad = Unidad(condominio=self.condominio_a, torre=self.torre_b, numero="101")
        with self.assertRaises(ValidationError) as ctx:
            unidad.full_clean()
        self.assertIn("torre", ctx.exception.message_dict)

    def test_una_torre_del_mismo_condominio_no_da_error(self):
        from .models import Torre

        torre_propia = Torre.objects.create(condominio=self.condominio_a, nombre="1")
        unidad = Unidad(condominio=self.condominio_a, torre=torre_propia, numero="101")
        unidad.full_clean()  # no debe lanzar

    def test_el_admin_no_permite_guardar_la_combinacion_invalida(self):
        staff = User.objects.create_superuser(username="torre_ajena_staff", password="x")
        self.client.force_login(staff)
        r = self.client.post("/admin/core/unidad/add/", {
            "condominio": self.condominio_a.pk, "torre": self.torre_b.pk, "numero": "101", "alicuota": "0",
        })
        self.assertEqual(r.status_code, 200)  # se queda en el form con el error, no redirige
        self.assertContains(r, "no a Test Torre Ajena A")
        self.assertFalse(Unidad.objects.filter(condominio=self.condominio_a, numero="101").exists())


class UnidadTorreDisplayTests(TestCase):
    """Antes mostraba "-" para una unidad sin torre -- ambiguo (¿no tiene,
    o nadie la cargó?). Ahora muestra la etiqueta_unidad del condominio
    (ej. "Casa"), igual que ya se usa en el resto del panel."""

    def setUp(self):
        self.staff = User.objects.create_superuser(username="torre_display_staff", password="x")
        self.client.force_login(self.staff)

    def test_sin_torre_muestra_la_etiqueta_unidad_del_condominio(self):
        from .models import Torre

        condominio = Condominio.objects.create(nombre="Test Torre Display Casa", plan="premium", etiqueta_unidad="Casa")
        Unidad.objects.create(condominio=condominio, numero="668", calle="Teniente Uribe")
        r = self.client.get("/admin/core/unidad/")
        self.assertContains(r, ">Casa<")

    def test_con_torre_muestra_el_nombre_de_la_torre(self):
        from .models import Torre

        condominio = Condominio.objects.create(nombre="Test Torre Display Depto", plan="premium")
        torre = Torre.objects.create(condominio=condominio, nombre="9")
        Unidad.objects.create(condominio=condominio, torre=torre, numero="302")
        r = self.client.get("/admin/core/unidad/")
        self.assertContains(r, ">9<")


class MembresiaAdminFiltroBlockYDeptoTests(TestCase):
    """Filtros nuevos por block (unidad__torre) y depto (unidad) en el
    admin de Membresías, mismo patrón AutocompleteSelectFilter."""

    @classmethod
    def setUpTestData(cls):
        from .models import Torre

        cls.condominio = Condominio.objects.create(nombre="Test Membresia Block Depto", plan="premium")
        cls.torre_9 = Torre.objects.create(condominio=cls.condominio, nombre="9")
        cls.torre_10 = Torre.objects.create(condominio=cls.condominio, nombre="10")
        cls.unidad_9_54 = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre_9, numero="54")
        cls.unidad_10_12 = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre_10, numero="12")
        cls.residente_9 = User.objects.create_user(username="block9_residente")
        cls.residente_10 = User.objects.create_user(username="block10_residente")
        Membresia.objects.create(user=cls.residente_9, condominio=cls.condominio, rol="residente", unidad=cls.unidad_9_54, terminos_aceptados_en=timezone.now())
        Membresia.objects.create(user=cls.residente_10, condominio=cls.condominio, rol="residente", unidad=cls.unidad_10_12, terminos_aceptados_en=timezone.now())

    def setUp(self):
        self.superuser = User.objects.create_superuser(username="block_depto_staff", password="x")
        self.client.force_login(self.superuser)

    def test_filtro_por_block_acota_los_resultados(self):
        r = self.client.get("/admin/core/membresia/", {"unidad__torre__id__exact": self.torre_9.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "block9_residente")
        self.assertNotContains(r, "block10_residente")

    def test_filtro_por_depto_acota_los_resultados(self):
        r = self.client.get("/admin/core/membresia/", {"unidad__id__exact": self.unidad_9_54.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "block9_residente")
        self.assertNotContains(r, "block10_residente")


class AdminOrdenNumericoTests(TestCase):
    """Torre/Unidad/Membresia se ordenaban alfabéticamente en el admin
    (torre/depto "10" antes que "2") -- mismo truco Length() que ya se usa
    en TorreListView/UnidadListView del panel web, ahora también acá.

    IMPORTANTE: estos tests pegan por HTTP a la página real del admin, no
    llaman ModelAdmin.get_queryset() directo -- el ChangeList de Django
    vuelve a aplicar su propio order_by() DESPUÉS de get_queryset() (ver
    ChangeList.get_ordering), así que un test que solo llama get_queryset()
    puede pasar en verde aunque la página real siga saliendo alfabética
    (bug real que pasó acá: get_ordering() faltaba y el fix de
    get_queryset() nunca se notaba en el navegador)."""

    def setUp(self):
        self.staff = User.objects.create_user(username="orden_num_staff", is_staff=True, is_superuser=True)
        self.client.force_login(self.staff)

    def test_torre_admin_ordena_numerico_no_alfabetico(self):
        condominio = Condominio.objects.create(nombre="Test Orden Torre", plan="premium")
        Torre.objects.create(condominio=condominio, nombre="10")
        Torre.objects.create(condominio=condominio, nombre="2")
        Torre.objects.create(condominio=condominio, nombre="1")
        r = self.client.get("/admin/core/torre/")
        nombres = [t.nombre for t in r.context["cl"].result_list]
        self.assertEqual(nombres, ["1", "2", "10"])

    def test_unidad_admin_ordena_numerico_no_alfabetico(self):
        condominio = Condominio.objects.create(nombre="Test Orden Unidad", plan="premium")
        Unidad.objects.create(condominio=condominio, numero="10")
        Unidad.objects.create(condominio=condominio, numero="2")
        Unidad.objects.create(condominio=condominio, numero="1")
        r = self.client.get("/admin/core/unidad/")
        numeros = [u.numero for u in r.context["cl"].result_list]
        self.assertEqual(numeros, ["1", "2", "10"])

    def test_membresia_admin_ordena_por_block_numerico(self):
        condominio = Condominio.objects.create(nombre="Test Orden Membresia", plan="premium")
        torre_10 = Torre.objects.create(condominio=condominio, nombre="10")
        torre_2 = Torre.objects.create(condominio=condominio, nombre="2")
        unidad_10 = Unidad.objects.create(condominio=condominio, torre=torre_10, numero="1")
        unidad_2 = Unidad.objects.create(condominio=condominio, torre=torre_2, numero="1")
        user_10 = User.objects.create_user(username="orden_block10")
        user_2 = User.objects.create_user(username="orden_block2")
        Membresia.objects.create(user=user_10, condominio=condominio, rol="residente", unidad=unidad_10, terminos_aceptados_en=timezone.now())
        Membresia.objects.create(user=user_2, condominio=condominio, rol="residente", unidad=unidad_2, terminos_aceptados_en=timezone.now())
        r = self.client.get("/admin/core/membresia/")
        usernames = [m.user.username for m in r.context["cl"].result_list]
        self.assertEqual(usernames, ["orden_block2", "orden_block10"])


class AdminIndexYSidebarTests(TestCase):
    """El índice del admin arma TODO el sidebar personalizado (UNFOLD.SIDEBAR.navigation,
    config/settings.py) -- cada link usa reverse_lazy con el nombre de URL de un
    modelo registrado, así que un nombre mal escrito ahí no se nota hasta que
    alguien realmente visita /admin/ (reverse_lazy es perezoso). Este test
    fuerza esa resolución, y de paso confirma que SITE_LOGO también resuelve
    bien (depende del storage de staticfiles, no de un path fijo)."""

    def test_admin_index_renderiza_con_todo_el_sidebar_y_el_logo(self):
        staff = User.objects.create_superuser(username="sidebar_staff", password="x", email="sidebar_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 200)
        contenido = r.content.decode()
        self.assertIn("core/logo", contenido)
        for texto in ("Condominios", "Blocks", "Departamentos", "Membresías", "Alertas", "Avisos", "Usuarios"):
            self.assertIn(texto, contenido)


class UserAdminReenganchadoConUnfoldTests(TestCase):
    """auth.User/auth.Group traían el admin de Django sin tocar -- el
    formulario de "Añadir usuario" usaba los widgets planos de Django para
    password1/password2 dentro del tema de Unfold, incompatibles con el JS
    que Unfold espera ahí, y el botón "Guardar" no hacía nada (bug real
    reportado por el usuario: "el admin no puede crear usuario"). Se
    reenganchó con unfold.forms.UserCreationForm/UserChangeForm, que traen
    los widgets correctos -- esto confirma que el formulario de alta
    efectivamente los usa, y que crear un usuario sigue funcionando."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(username="useradmin_staff", password="x", email="useradmin_staff@example.com")
        self.client.force_login(self.superuser)

    def test_el_formulario_de_alta_usa_los_widgets_de_unfold(self):
        r = self.client.get("/admin/auth/user/add/")
        self.assertEqual(r.status_code, 200)
        contenido = r.content.decode()
        self.assertIn('name="password1"', contenido)
        # max-w-2xl es una clase propia de unfold.widgets.INPUT_CLASSES -- el
        # PasswordInput plano de Django nunca la trae, así que esto confirma
        # que el formulario quedó enganchado con unfold.forms.UserCreationForm.
        self.assertIn("max-w-2xl", contenido)

    def test_el_formulario_de_alta_carga_el_medidor_de_contrasena(self):
        r = self.client.get("/admin/auth/user/add/")
        self.assertEqual(r.status_code, 200)
        contenido = r.content.decode()
        self.assertIn("medidor_contrasena.js", contenido)
        self.assertIn("admin_password_medidor.js", contenido)

    def _datos_inline_membresia_vacio(self):
        # El formulario de alta ahora incluye el inline de Membresía (ver
        # MembresiaInlineParaUsuario) -- aunque no se use, su management
        # form (TOTAL_FORMS, etc.) es obligatorio para que el POST valide.
        return {
            "membresia-TOTAL_FORMS": "1",
            "membresia-INITIAL_FORMS": "0",
            "membresia-MIN_NUM_FORMS": "0",
            "membresia-MAX_NUM_FORMS": "1",
            "membresia-0-condominio": "",
            "membresia-0-unidad": "",
            "membresia-0-rol": "residente",
        }

    def test_crear_un_usuario_sigue_funcionando(self):
        r = self.client.post("/admin/auth/user/add/", {
            "username": "nuevo_desde_admin",
            "password1": "unaClaveBienSegura123!",
            "password2": "unaClaveBienSegura123!",
            **self._datos_inline_membresia_vacio(),
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="nuevo_desde_admin").exists())

    def test_crear_usuario_y_asignarle_condominio_en_el_mismo_formulario(self):
        condominio = Condominio.objects.create(nombre="Condominio Para Alta Usuario", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        r = self.client.post("/admin/auth/user/add/", {
            "username": "nuevo_con_condominio",
            "password1": "unaClaveBienSegura123!",
            "password2": "unaClaveBienSegura123!",
            "membresia-TOTAL_FORMS": "1",
            "membresia-INITIAL_FORMS": "0",
            "membresia-MIN_NUM_FORMS": "0",
            "membresia-MAX_NUM_FORMS": "1",
            "membresia-0-condominio": str(condominio.pk),
            "membresia-0-unidad": str(unidad.pk),
            "membresia-0-rol": "residente",
        })
        self.assertEqual(r.status_code, 302)
        nuevo = User.objects.get(username="nuevo_con_condominio")
        self.assertEqual(nuevo.membresia.condominio, condominio)
        self.assertEqual(nuevo.membresia.rol, "residente")

    def test_grupos_sigue_registrado_y_accesible(self):
        r = self.client.get("/admin/auth/group/")
        self.assertEqual(r.status_code, 200)


class SinCondominioFilterTests(TestCase):
    """Filtro "condominio asignado" en /admin/auth/user/ -- para encontrar
    cuentas creadas a mano (ej. desde /admin/auth/user/add/) a las que
    todavía les falta la Membresia que las liga a un condominio."""

    @classmethod
    def setUpTestData(cls):
        # Nombres a propósito sin la palabra "condominio" adentro -- el
        # parameter_name del filtro es "con_condominio" y aparece muchas
        # veces en los links del propio widget de filtros, así que un
        # username que la contenga da falsos positivos en assertContains.
        condominio = Condominio.objects.create(nombre="Test Sin Condominio", plan="premium")
        cls.usuario_asignado = User.objects.create_user(username="usuario_asignado_xyz")
        Membresia.objects.create(user=cls.usuario_asignado, condominio=condominio, rol="residente", terminos_aceptados_en=timezone.now())
        cls.usuario_huerfano = User.objects.create_user(username="usuario_huerfano_xyz")

    def setUp(self):
        self.staff = User.objects.create_superuser(username="sincondo_staff", password="x", email="sincondo_staff@example.com")
        self.client.force_login(self.staff)

    def test_filtro_no_muestra_solo_los_sin_membresia(self):
        r = self.client.get("/admin/auth/user/", {"con_condominio": "no"})
        self.assertContains(r, "usuario_huerfano_xyz")
        self.assertNotContains(r, "usuario_asignado_xyz")

    def test_filtro_si_muestra_solo_los_con_membresia(self):
        r = self.client.get("/admin/auth/user/", {"con_condominio": "si"})
        self.assertContains(r, "usuario_asignado_xyz")
        self.assertNotContains(r, "usuario_huerfano_xyz")

    def test_sin_filtro_muestra_a_todos(self):
        r = self.client.get("/admin/auth/user/")
        self.assertContains(r, "usuario_asignado_xyz")
        self.assertContains(r, "usuario_huerfano_xyz")


class DashboardCallbackTests(TestCase):
    """UNFOLD["DASHBOARD_CALLBACK"] (core/dashboard.py) -- los KPIs y las
    tablas de /admin/ con datos reales, no la grilla de apps por defecto."""

    @classmethod
    def setUpTestData(cls):
        from alertas.models import Alerta

        cls.condominio_activo = Condominio.objects.create(
            nombre="Test Dashboard Activo", plan="premium", activo=True,
            pagado_hasta=timezone.localdate() + datetime.timedelta(days=10),
        )
        Condominio.objects.create(nombre="Test Dashboard Inactivo", plan="premium", activo=False)
        cls.condominio_vencido = Condominio.objects.create(
            nombre="Test Dashboard Vencido", plan="premium",
            pagado_hasta=timezone.localdate() - datetime.timedelta(days=5),
        )
        unidad_1 = Unidad.objects.create(condominio=cls.condominio_activo, numero="1")
        Unidad.objects.create(condominio=cls.condominio_activo, numero="2")
        user = User.objects.create_user(username="dashboard_residente")
        membresia = Membresia.objects.create(user=user, condominio=cls.condominio_activo, rol="residente", unidad=unidad_1, terminos_aceptados_en=timezone.now())
        Alerta.objects.create(condominio=cls.condominio_activo, autor=membresia, tipo="robo", estado="activa")
        SolicitudAcceso.objects.create(condominio="Junta de prueba", nombre="Ana", comuna="Valparaíso", telefono="+56911111111", atendido=False)
        SolicitudAcceso.objects.create(condominio="Ya atendida", nombre="Luis", comuna="Valparaíso", telefono="+56922222222", atendido=True)

    def setUp(self):
        self.staff = User.objects.create_superuser(username="dashboard_staff", password="x", email="dashboard_staff@example.com")
        self.client.force_login(self.staff)

    def test_dashboard_muestra_los_kpis_correctos(self):
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["kpi_condominios_activos"], 2)  # activo + vencido (vencido no tiene activo=False)
        self.assertEqual(r.context["kpi_condominios_total"], 3)
        self.assertEqual(r.context["kpi_unidades"], 2)
        self.assertEqual(r.context["kpi_miembros"], 1)
        self.assertEqual(r.context["kpi_alertas_activas"], 1)
        self.assertEqual(r.context["kpi_solicitudes_pendientes"], 1)
        self.assertEqual(r.context["kpi_suscripciones_vencidas"], 1)

    def test_dashboard_muestra_las_tablas(self):
        r = self.client.get("/admin/")
        contenido = r.content.decode()
        self.assertIn("Test Dashboard Activo", contenido)
        self.assertIn("Ana", contenido)
        self.assertNotIn("Luis", contenido)  # ya atendida, no debería salir

    def test_grafico_de_condominios_por_mes_trae_el_mes_actual(self):
        import json

        r = self.client.get("/admin/")
        datos = json.loads(r.context["chart_condominios_por_mes"])
        self.assertEqual(len(datos["labels"]), 6)
        self.assertEqual(len(datos["datasets"][0]["data"]), 6)
        # los 3 condominios de setUpTestData se crean "ahora" -- el mes
        # actual (último de la lista) tiene que sumarlos.
        self.assertEqual(datos["datasets"][0]["data"][-1], 3)


class EstadoSuscripcionFilterTests(TestCase):
    """Como el cobro es manual (ver SuscripcionActivaMixin), este filtro es
    la lista de seguimiento de pagos -- confirma que agrupa bien los 3
    estados que ya calcula CondominioAdmin.estado_suscripcion."""

    @classmethod
    def setUpTestData(cls):
        cls.vencido = Condominio.objects.create(
            nombre="Filtro Suscripcion Vencido", plan="premium",
            pagado_hasta=timezone.localdate() - datetime.timedelta(days=3),
        )
        cls.vigente = Condominio.objects.create(
            nombre="Filtro Suscripcion Vigente", plan="premium",
            pagado_hasta=timezone.localdate() + datetime.timedelta(days=10),
        )
        cls.libre = Condominio.objects.create(
            nombre="Filtro Suscripcion Libre", plan="premium", pagado_hasta=None,
        )

    def setUp(self):
        self.staff = User.objects.create_superuser(username="filtro_susc_staff", password="x")
        self.client.force_login(self.staff)

    def test_filtro_vencida_muestra_solo_los_vencidos(self):
        r = self.client.get("/admin/core/condominio/?estado_suscripcion=vencida")
        self.assertContains(r, "Filtro Suscripcion Vencido")
        self.assertNotContains(r, "Filtro Suscripcion Vigente")
        self.assertNotContains(r, "Filtro Suscripcion Libre")

    def test_filtro_vigente_muestra_solo_los_vigentes(self):
        r = self.client.get("/admin/core/condominio/?estado_suscripcion=vigente")
        self.assertContains(r, "Filtro Suscripcion Vigente")
        self.assertNotContains(r, "Filtro Suscripcion Vencido")
        self.assertNotContains(r, "Filtro Suscripcion Libre")

    def test_filtro_libre_muestra_solo_los_sin_restriccion(self):
        r = self.client.get("/admin/core/condominio/?estado_suscripcion=libre")
        self.assertContains(r, "Filtro Suscripcion Libre")
        self.assertNotContains(r, "Filtro Suscripcion Vencido")
        self.assertNotContains(r, "Filtro Suscripcion Vigente")

    def test_sin_filtro_muestra_a_todos(self):
        r = self.client.get("/admin/core/condominio/")
        self.assertContains(r, "Filtro Suscripcion Vencido")
        self.assertContains(r, "Filtro Suscripcion Vigente")
        self.assertContains(r, "Filtro Suscripcion Libre")


class CrearUnidadesEnLoteTests(TestCase):
    """Onboardear un condominio grande unidad por unidad es lento -- esta
    acción del admin (ver UnidadAdmin.crear_unidades_en_lote) genera un
    rango numerado de una vez."""

    URL = "/admin/core/unidad/crear-unidades-en-lote/"

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Lote Unidades Test", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="Torre A")
        cls.otro_condominio = Condominio.objects.create(nombre="Otro Condominio Lote", plan="premium")

    def setUp(self):
        self.staff = User.objects.create_superuser(username="lote_unidades_staff", password="x")
        self.client.force_login(self.staff)

    def _post(self, **overrides):
        datos = {
            "_form_submitted": "true",
            "condominio": self.condominio.pk,
            "torre": "",
            "prefijo": "",
            "desde": "101",
            "hasta": "105",
            "alicuota": "",
        }
        datos.update(overrides)
        return self.client.post(self.URL, datos)

    def test_el_boton_aparece_en_el_changelist(self):
        r = self.client.get("/admin/core/unidad/")
        self.assertContains(r, "crear-unidades-en-lote")

    def test_crea_el_rango_completo(self):
        r = self._post()
        self.assertEqual(r.status_code, 302)
        numeros = set(Unidad.objects.filter(condominio=self.condominio).values_list("numero", flat=True))
        self.assertEqual(numeros, {"101", "102", "103", "104", "105"})

    def test_respeta_el_prefijo_y_la_alicuota(self):
        self._post(prefijo="A-", alicuota="0.0033", desde="1", hasta="2")
        creadas = Unidad.objects.filter(condominio=self.condominio, numero__in=["A-1", "A-2"])
        self.assertEqual(creadas.count(), 2)
        for unidad in creadas:
            self.assertEqual(str(unidad.alicuota), "0.0033")

    def test_respeta_la_calle(self):
        self._post(calle="Los Aromos", desde="1", hasta="2")
        creadas = Unidad.objects.filter(condominio=self.condominio, numero__in=["1", "2"])
        self.assertEqual(creadas.count(), 2)
        for unidad in creadas:
            self.assertEqual(unidad.calle, "Los Aromos")

    def test_no_duplica_unidades_que_ya_existian(self):
        Unidad.objects.create(condominio=self.condominio, numero="101")
        self._post()
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio, numero="101").count(), 1)
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio).count(), 5)

    def test_rechaza_torre_que_no_es_del_condominio_elegido(self):
        torre_ajena = Torre.objects.create(condominio=self.otro_condominio, nombre="Torre Ajena")
        r = self._post(torre=torre_ajena.pk)
        self.assertEqual(r.status_code, 200)  # el dialog vuelve a renderizar con el error, no redirige
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio).count(), 0)

    def test_rechaza_rango_invertido(self):
        r = self._post(desde="10", hasta="5")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio).count(), 0)

    def test_rechaza_rango_demasiado_grande(self):
        r = self._post(desde="1", hasta="1000")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio).count(), 0)


class CondominioAdminRegionComunaTests(TestCase):
    """region/comuna pasaron de texto libre a desplegable (comuna en
    cascada según la región, ver CondominioAdminForm) -- confirma que se
    renderizan como <select>, que una combinación real se guarda bien y
    que una combinación que no corresponde (comuna de otra región) se
    rechaza en vez de guardarse mal."""

    def _datos_base(self, nombre, region, comuna):
        return {
            "nombre": nombre, "plan": "premium", "region": region, "comuna": comuna,
            "etiqueta_torre": "Torre", "etiqueta_unidad": "Unidad", "etiqueta_organizacion": "Condominio",
            "genero_unidad": "f",
            "unidades-TOTAL_FORMS": "0", "unidades-INITIAL_FORMS": "0", "unidades-MIN_NUM_FORMS": "0", "unidades-MAX_NUM_FORMS": "1000",
            "membresias-TOTAL_FORMS": "0", "membresias-INITIAL_FORMS": "0", "membresias-MIN_NUM_FORMS": "0", "membresias-MAX_NUM_FORMS": "1000",
            "condominios_vecinos": [],
        }

    def setUp(self):
        self.staff = User.objects.create_superuser(username="region_comuna_staff", password="x")
        self.client.force_login(self.staff)

    def test_el_formulario_de_alta_muestra_desplegables(self):
        r = self.client.get("/admin/core/condominio/add/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('name="region"', html)
        self.assertIn('name="comuna"', html)
        self.assertIn("cascada_region_comuna.js", html)
        self.assertIn("datos_comunas_chile.js", html)
        self.assertIn("Valparaíso", html)

    def test_crea_el_condominio_con_region_y_comuna_validas(self):
        r = self.client.post("/admin/core/condominio/add/", self._datos_base("Admin Region Valida", "valparaiso", "Valparaíso"))
        self.assertEqual(r.status_code, 302)
        condominio = Condominio.objects.get(nombre="Admin Region Valida")
        self.assertEqual(condominio.region, "valparaiso")
        self.assertEqual(condominio.comuna, "Valparaíso")

    def test_rechaza_comuna_que_no_es_de_esa_region(self):
        r = self.client.post("/admin/core/condominio/add/", self._datos_base("Admin Region Invalida", "valparaiso", "Santiago"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "no pertenece a la región elegida")
        self.assertFalse(Condominio.objects.filter(nombre="Admin Region Invalida").exists())
