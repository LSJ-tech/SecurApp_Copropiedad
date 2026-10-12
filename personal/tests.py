import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia

from .calculo import calcular_liquidacion
from .models import Afp, Empleado, Liquidacion, ParametrosPeriodo, TramoImpuestoUnico


def crear_membresia(condominio, rol, unidad=None, **user_kwargs):
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(user=user, condominio=condominio, rol=rol, unidad=unidad, terminos_aceptados_en=timezone.now())


def _pagado_hasta_al_dia():
    """Crear/generar empleados y liquidaciones exige suscripción al día
    (SuscripcionActivaMixin) -- la mayoría de estos tests no prueban ESE
    permiso puntual, así que parten con la suscripción vigente."""
    return timezone.localdate() + datetime.timedelta(days=30)


def _parametros(**overrides):
    datos = dict(
        periodo="2026-10", valor_utm=Decimal("65000"), valor_uf=Decimal("38000"),
        ingreso_minimo_mensual=500000, tope_imponible_afp_salud_uf=Decimal("87.8"), tope_imponible_cesantia_uf=Decimal("131.8"),
        tasa_cesantia_trabajador_indefinido_pct=Decimal("0.6"), tasa_cesantia_trabajador_plazo_fijo_pct=Decimal("0"),
    )
    datos.update(overrides)
    return ParametrosPeriodo(**datos)


def _tramos():
    return [
        TramoImpuestoUnico(desde_utm=Decimal("0"), hasta_utm=Decimal("13.5"), tasa_pct=Decimal("0"), rebaja_utm=Decimal("0")),
        TramoImpuestoUnico(desde_utm=Decimal("13.5"), hasta_utm=Decimal("30"), tasa_pct=Decimal("4"), rebaja_utm=Decimal("0.54")),
    ]


class CalculoLiquidacionTests(TestCase):
    """Casos calculados a mano (ver conversación) -- validan que el código hace
    exactamente lo que dice la fórmula, no una certificación legal: las tasas y
    tramos usados acá son ilustrativos, no verificados contra el SII."""

    def test_sin_gratificacion_fonasa_indefinido(self):
        empleado = Empleado(
            sueldo_base=500000, asignacion_colacion=50000, asignacion_movilizacion=30000,
            tipo_contrato="indefinido", sistema_salud="fonasa", aplica_gratificacion=False,
            afp=Afp(nombre="Test AFP", tasa_total_pct=Decimal("11.44")),
        )
        resultado = calcular_liquidacion(empleado, _parametros(), _tramos())

        self.assertEqual(resultado["gratificacion"], 0)
        self.assertEqual(resultado["total_haberes"], 580000)
        self.assertEqual(resultado["descuento_afp"], 57200)
        self.assertEqual(resultado["descuento_salud"], 35000)
        self.assertEqual(resultado["descuento_cesantia"], 3000)
        self.assertEqual(resultado["impuesto_unico"], 0)
        self.assertEqual(resultado["total_descuentos"], 95200)
        self.assertEqual(resultado["liquido_a_pagar"], 484800)

    def test_con_gratificacion_isapre_plazo_fijo(self):
        empleado = Empleado(
            sueldo_base=600000, asignacion_colacion=0, asignacion_movilizacion=0,
            tipo_contrato="plazo_fijo", sistema_salud="isapre", plan_isapre_uf=Decimal("8.5"),
            aplica_gratificacion=True,
            afp=Afp(nombre="Test AFP 2", tasa_total_pct=Decimal("10.49")),
        )
        resultado = calcular_liquidacion(empleado, _parametros(), _tramos())

        self.assertEqual(resultado["gratificacion"], 150000)
        self.assertEqual(resultado["total_haberes"], 750000)
        self.assertEqual(resultado["descuento_afp"], 78675)
        self.assertEqual(resultado["descuento_salud"], 323000)
        self.assertEqual(resultado["descuento_cesantia"], 0)
        self.assertEqual(resultado["total_descuentos"], 401675)
        self.assertEqual(resultado["liquido_a_pagar"], 348325)

    def test_tramo_con_impuesto_unico(self):
        empleado = Empleado(
            sueldo_base=1800000, asignacion_colacion=0, asignacion_movilizacion=0,
            tipo_contrato="indefinido", sistema_salud="fonasa", aplica_gratificacion=False,
            afp=Afp(nombre="Test AFP", tasa_total_pct=Decimal("11.44")),
        )
        resultado = calcular_liquidacion(empleado, _parametros(), _tramos())

        self.assertEqual(resultado["descuento_afp"], 205920)
        self.assertEqual(resultado["descuento_salud"], 126000)
        self.assertEqual(resultado["descuento_cesantia"], 10800)
        self.assertEqual(resultado["impuesto_unico"], 23191)
        self.assertEqual(resultado["total_descuentos"], 365911)
        self.assertEqual(resultado["liquido_a_pagar"], 1434089)

    def test_tope_imponible_limita_la_base_de_descuentos(self):
        # tope AFP/salud bajo a propósito (10 UF = 380000), tope cesantía alto
        # (131.8 UF) para probar que son dos topes independientes -- por ley
        # el de cesantía siempre es más alto que el de AFP/salud.
        parametros = _parametros(tope_imponible_afp_salud_uf=Decimal("10"), tope_imponible_cesantia_uf=Decimal("131.8"))
        empleado = Empleado(
            sueldo_base=1000000, asignacion_colacion=0, asignacion_movilizacion=0,
            tipo_contrato="indefinido", sistema_salud="fonasa", aplica_gratificacion=False,
            afp=Afp(nombre="Test AFP", tasa_total_pct=Decimal("10")),
        )
        resultado = calcular_liquidacion(empleado, parametros, _tramos())
        # AFP/salud se calculan sobre el tope (380000), no sobre el sueldo completo
        self.assertEqual(resultado["descuento_afp"], 38000)
        self.assertEqual(resultado["descuento_salud"], 26600)
        # cesantía no está topada acá (tope mucho más alto que el sueldo) -- se calcula sobre el sueldo completo
        self.assertEqual(resultado["descuento_cesantia"], 6000)


class EmpleadoPermisosTests(TestCase):
    """Mismo criterio que GastoComun: administración crea/edita (datos de
    sueldo), directiva supervisa (ve pero no crea)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Personal", plan="premium", pagado_hasta=_pagado_hasta_al_dia())
        cls.afp = Afp.objects.create(nombre="Test AFP", tasa_total_pct=Decimal("11.44"))

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="personal_admon")
        self.directiva = crear_membresia(self.condominio, "directiva", username="personal_directiva")
        self.residente = crear_membresia(self.condominio, "residente", username="personal_residente")

    def _datos_empleado(self):
        return {
            "nombre": "Juan Pérez", "rut": "11.111.111-1", "cargo": "Conserje",
            "tipo_contrato": "indefinido", "fecha_ingreso": "2026-01-01",
            "afp": self.afp.pk, "sistema_salud": "fonasa", "sueldo_base": "500000",
            "asignacion_colacion": "0", "asignacion_movilizacion": "0",
        }

    def test_administracion_puede_crear_empleado(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("empleado-crear"), self._datos_empleado())
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Empleado.objects.filter(condominio=self.condominio, nombre="Juan Pérez").exists())

    def test_directiva_no_puede_crear_empleado(self):
        self.client.force_login(self.directiva.user)
        r = self.client.post(reverse("empleado-crear"), self._datos_empleado())
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Empleado.objects.filter(condominio=self.condominio).exists())

    def test_directiva_puede_ver_la_lista(self):
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("empleados"))
        self.assertEqual(r.status_code, 200)

    def test_residente_no_puede_ver_la_lista(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("empleados"))
        self.assertEqual(r.status_code, 302)


class PersonalSuscripcionTests(TestCase):
    """Crear un empleado o generar una liquidación exigen suscripción al día
    (SuscripcionActivaMixin) -- ver/editar lo que ya existe sigue disponible."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Personal Suscripcion", plan="premium", pagado_hasta=None)
        cls.afp = Afp.objects.create(nombre="Test AFP", tasa_total_pct=Decimal("11.44"))
        cls.empleado = Empleado.objects.create(
            condominio=cls.condominio, nombre="Pedro Soto", rut="22.222.222-2", cargo="Aseo",
            tipo_contrato="indefinido", fecha_ingreso="2026-01-01", afp=cls.afp,
            sistema_salud="fonasa", sueldo_base=450000,
        )

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="personal_susc_admon")

    def test_crear_empleado_bloqueado_si_la_suscripcion_no_esta_al_dia(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("empleado-crear"), {
            "nombre": "Ana Lopez", "rut": "33.333.333-3", "cargo": "Conserje",
            "tipo_contrato": "indefinido", "fecha_ingreso": "2026-01-01",
            "afp": self.afp.pk, "sistema_salud": "fonasa", "sueldo_base": "500000",
            "asignacion_colacion": "0", "asignacion_movilizacion": "0",
        })
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Empleado.objects.filter(rut="33.333.333-3").exists())

    def test_generar_liquidacion_bloqueado_si_la_suscripcion_no_esta_al_dia(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("liquidacion-generar", args=[self.empleado.pk]), {"periodo": "2026-10"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Liquidacion.objects.filter(empleado=self.empleado).count(), 0)

    def test_editar_empleado_sigue_disponible_aunque_venza(self):
        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("empleado-editar", args=[self.empleado.pk]))
        self.assertEqual(r.status_code, 200)


class EmpleadoTipoContratoTests(TestCase):
    """Un contrato indefinido no tiene fecha de término; uno a plazo fijo sí
    la necesita. Al editar un empleado de plazo fijo a indefinido (lo que
    pasa en la práctica cuando se renueva y queda fijo), la fecha de
    término se limpia sola."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Tipo Contrato", plan="premium", pagado_hasta=_pagado_hasta_al_dia())
        cls.afp = Afp.objects.create(nombre="Test AFP", tasa_total_pct=Decimal("11.44"))

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="tipo_admon")

    def _datos_base(self, **overrides):
        datos = {
            "nombre": "Pedro Soto", "rut": "22.222.222-2", "cargo": "Aseo",
            "fecha_ingreso": "2026-01-01", "afp": self.afp.pk, "sistema_salud": "fonasa",
            "sueldo_base": "450000", "asignacion_colacion": "0", "asignacion_movilizacion": "0",
        }
        datos.update(overrides)
        return datos

    def test_indefinido_no_exige_fecha_termino(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("empleado-crear"), self._datos_base(tipo_contrato="indefinido"))
        self.assertEqual(r.status_code, 302)
        empleado = Empleado.objects.get(rut="22.222.222-2")
        self.assertIsNone(empleado.fecha_termino)

    def test_plazo_fijo_exige_fecha_termino(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("empleado-crear"), self._datos_base(tipo_contrato="plazo_fijo"))
        self.assertEqual(r.status_code, 200)  # vuelve a mostrar el form con el error
        self.assertFalse(Empleado.objects.filter(rut="22.222.222-2").exists())

    def test_plazo_fijo_con_fecha_termino_se_guarda(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("empleado-crear"), self._datos_base(tipo_contrato="plazo_fijo", fecha_termino="2027-01-01"))
        self.assertEqual(r.status_code, 302)
        empleado = Empleado.objects.get(rut="22.222.222-2")
        self.assertEqual(str(empleado.fecha_termino), "2027-01-01")

    def test_pasar_de_plazo_fijo_a_indefinido_limpia_la_fecha_de_termino(self):
        empleado = Empleado.objects.create(
            condominio=self.condominio, nombre="Pedro Soto", rut="22.222.222-2", cargo="Aseo",
            tipo_contrato="plazo_fijo", fecha_ingreso="2026-01-01", fecha_termino="2027-01-01",
            afp=self.afp, sistema_salud="fonasa", sueldo_base=450000,
        )
        self.client.force_login(self.administracion.user)
        # el admin cambia el tipo de contrato a indefinido, pero el campo de fecha
        # sigue mandándose en el POST (el navegador no lo vacía solo) -- el form
        # tiene que ignorarlo y limpiarlo igual
        r = self.client.post(
            reverse("empleado-editar", args=[empleado.pk]),
            self._datos_base(tipo_contrato="indefinido", fecha_termino="2027-01-01"),
        )
        self.assertEqual(r.status_code, 302)
        empleado.refresh_from_db()
        self.assertEqual(empleado.tipo_contrato, "indefinido")
        self.assertIsNone(empleado.fecha_termino)


class LiquidacionGenerarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Liquidaciones", plan="premium", pagado_hasta=_pagado_hasta_al_dia())
        cls.afp = Afp.objects.create(nombre="Test AFP", tasa_total_pct=Decimal("11.44"))
        cls.empleado = Empleado.objects.create(
            condominio=cls.condominio, nombre="Juan Pérez", rut="11.111.111-1", cargo="Conserje",
            tipo_contrato="indefinido", fecha_ingreso="2026-01-01", afp=cls.afp,
            sistema_salud="fonasa", sueldo_base=500000, email="juan@example.com",
        )
        TramoImpuestoUnico.objects.bulk_create(_tramos())

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="liq_admon")

    def test_sin_ningun_periodo_previo_pide_cargar_el_primero_a_mano(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("liquidacion-generar", args=[self.empleado.pk]), {"periodo": "2099-01"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Liquidacion.objects.count(), 0)

    def test_periodo_nuevo_hereda_parametros_y_consulta_utm_uf_solo(self):
        from unittest.mock import patch

        ParametrosPeriodo.objects.create(
            periodo="2026-09", valor_utm=Decimal("65000"), valor_uf=Decimal("38000"),
            ingreso_minimo_mensual=500000, tope_imponible_afp_salud_uf=Decimal("87.8"), tope_imponible_cesantia_uf=Decimal("131.8"),
        )
        self.client.force_login(self.administracion.user)
        with patch("personal.indicadores.obtener_utm", return_value=Decimal("72151")) as mock_utm, \
             patch("personal.indicadores.obtener_uf", return_value=Decimal("41130")) as mock_uf:
            r = self.client.post(reverse("liquidacion-generar", args=[self.empleado.pk]), {"periodo": "2026-10"})

        self.assertEqual(r.status_code, 302)
        mock_utm.assert_called_once_with("2026-10")
        mock_uf.assert_called_once_with("2026-10")
        parametros = ParametrosPeriodo.objects.get(periodo="2026-10")
        self.assertEqual(parametros.valor_utm, Decimal("72151"))
        self.assertEqual(parametros.valor_uf, Decimal("41130"))
        # heredado del periodo anterior, no se volvió a pedir
        self.assertEqual(parametros.ingreso_minimo_mensual, 500000)
        self.assertEqual(parametros.tope_imponible_afp_salud_uf, Decimal("87.8"))
        self.assertEqual(parametros.tope_imponible_cesantia_uf, Decimal("131.8"))
        self.assertTrue(Liquidacion.objects.filter(empleado=self.empleado, periodo="2026-10").exists())

    def test_genera_liquidacion_y_manda_correo_si_se_indica(self):
        from django.core import mail

        ParametrosPeriodo.objects.create(
            periodo="2026-10", valor_utm=Decimal("65000"), valor_uf=Decimal("38000"),
            ingreso_minimo_mensual=500000, tope_imponible_afp_salud_uf=Decimal("87.8"), tope_imponible_cesantia_uf=Decimal("131.8"),
        )
        self.client.force_login(self.administracion.user)
        r = self.client.post(
            reverse("liquidacion-generar", args=[self.empleado.pk]),
            {"periodo": "2026-10", "correo_destino": "juan@example.com"},
        )
        self.assertEqual(r.status_code, 302)
        liquidacion = Liquidacion.objects.get(empleado=self.empleado, periodo="2026-10")
        # mismo sueldo_base que el caso 1 de CalculoLiquidacionTests, pero sin
        # asignación de colación/movilización (no se setearon en este empleado)
        self.assertEqual(liquidacion.liquido_a_pagar, 404800)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["juan@example.com"])
        self.assertEqual(len(mail.outbox[0].attachments), 1)
        self.assertTrue(mail.outbox[0].attachments[0][1].startswith(b"%PDF"))

    def test_no_permite_duplicar_liquidacion_del_mismo_periodo(self):
        ParametrosPeriodo.objects.create(
            periodo="2026-10", valor_utm=Decimal("65000"), valor_uf=Decimal("38000"),
            ingreso_minimo_mensual=500000, tope_imponible_afp_salud_uf=Decimal("87.8"), tope_imponible_cesantia_uf=Decimal("131.8"),
        )
        self.client.force_login(self.administracion.user)
        self.client.post(reverse("liquidacion-generar", args=[self.empleado.pk]), {"periodo": "2026-10"})
        self.client.post(reverse("liquidacion-generar", args=[self.empleado.pk]), {"periodo": "2026-10"})
        self.assertEqual(Liquidacion.objects.filter(empleado=self.empleado, periodo="2026-10").count(), 1)

    def test_pdf_descargable_despues_de_generar(self):
        ParametrosPeriodo.objects.create(
            periodo="2026-10", valor_utm=Decimal("65000"), valor_uf=Decimal("38000"),
            ingreso_minimo_mensual=500000, tope_imponible_afp_salud_uf=Decimal("87.8"), tope_imponible_cesantia_uf=Decimal("131.8"),
        )
        self.client.force_login(self.administracion.user)
        self.client.post(reverse("liquidacion-generar", args=[self.empleado.pk]), {"periodo": "2026-10"})
        liquidacion = Liquidacion.objects.get(empleado=self.empleado, periodo="2026-10")

        r = self.client.get(reverse("liquidacion-pdf", args=[liquidacion.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")


class EmpleadoAdminTests(TestCase):
    """Filtro de condominio como desplegable con buscador (ver EmpleadoAdmin)
    -- confirma que el changelist sigue renderizando bien."""

    def test_changelist_renderiza_ok(self):
        condominio = Condominio.objects.create(nombre="Test Admin Empleado", plan="premium")
        afp = Afp.objects.create(nombre="Test AFP Admin", tasa_total_pct=Decimal("11.44"))
        Empleado.objects.create(
            condominio=condominio, nombre="Pedro Soto", rut="22.222.222-2", cargo="Aseo",
            tipo_contrato="indefinido", fecha_ingreso="2026-01-01", afp=afp,
            sistema_salud="fonasa", sueldo_base=450000,
        )
        staff = User.objects.create_superuser(username="admin_empleado_staff", password="x", email="admin_empleado_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/personal/empleado/")
        self.assertEqual(r.status_code, 200)


class LiquidacionAdminTests(TestCase):
    """Filtro de condominio (vía empleado__condominio) como desplegable con
    buscador -- antes solo filtraba por periodo, sin forma rápida de ver
    todas las liquidaciones de un condominio en particular."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Admin Liquidacion", plan="premium")
        afp = Afp.objects.create(nombre="Test AFP Liquidacion", tasa_total_pct=Decimal("11.44"))
        cls.empleado = Empleado.objects.create(
            condominio=cls.condominio, nombre="Ana Pérez", rut="11.111.111-1", cargo="Conserje",
            tipo_contrato="indefinido", fecha_ingreso="2026-01-01", afp=afp,
            sistema_salud="fonasa", sueldo_base=500000,
        )
        cls.liquidacion = Liquidacion.objects.create(
            empleado=cls.empleado, periodo="2026-09",
            sueldo_base=500000, total_imponible=500000, total_haberes=500000,
            descuento_afp=57200, descuento_salud=35000, descuento_cesantia=3000,
            impuesto_unico=0, total_descuentos=95200, liquido_a_pagar=404800,
            utm_usada=Decimal("65000.00"), afp_nombre_usada="Test AFP Liquidacion", afp_tasa_usada=Decimal("11.44"),
        )

    def test_changelist_renderiza_ok(self):
        staff = User.objects.create_superuser(username="admin_liquidacion_staff", password="x")
        self.client.force_login(staff)
        r = self.client.get("/admin/personal/liquidacion/")
        self.assertEqual(r.status_code, 200)

    def test_filtro_por_condominio_funciona(self):
        otro_condominio = Condominio.objects.create(nombre="Otro Condominio Liquidacion", plan="premium")
        staff = User.objects.create_superuser(username="filtro_liquidacion_staff", password="x")
        self.client.force_login(staff)
        r = self.client.get(f"/admin/personal/liquidacion/?empleado__condominio__id__exact={self.condominio.pk}")
        self.assertContains(r, "Ana Pérez")

        r2 = self.client.get(f"/admin/personal/liquidacion/?empleado__condominio__id__exact={otro_condominio.pk}")
        self.assertNotContains(r2, "Ana Pérez")
