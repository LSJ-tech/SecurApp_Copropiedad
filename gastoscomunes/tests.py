import datetime
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia, Unidad

from .models import CuotaUnidad, GastoComun


def crear_membresia(condominio, rol, unidad=None, **user_kwargs):
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(user=user, condominio=condominio, rol=rol, unidad=unidad, terminos_aceptados_en=timezone.now())


class GenerarGastoComunPermisosTests(TestCase):
    """Generar un gasto común (fijar el monto del periodo) quedó exclusivo
    de administración -- ni siquiera directiva puede, a pedido explícito del
    usuario (distinto del resto de gastos comunes, que sigue abierto a
    ambas: ver EsDirectivaOAdministracionMixin en GastoComunListView)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre="Test Gasto Permisos", plan="premium",
            pagado_hasta=timezone.localdate() + datetime.timedelta(days=30),
        )

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="gasto_admon")
        self.directiva = crear_membresia(self.condominio, "directiva", username="gasto_directiva")

    def test_administracion_puede_generar_gasto_comun(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("gastos-comunes-crear"), {
            "periodo": "2026-11", "modo": "total", "monto_total": "240000",
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(GastoComun.objects.filter(condominio=self.condominio, periodo="2026-11").exists())

    def test_directiva_no_puede_generar_gasto_comun(self):
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("gastos-comunes-crear"))
        self.assertEqual(r.status_code, 302)
        r = self.client.post(reverse("gastos-comunes-crear"), {
            "periodo": "2026-11", "modo": "total", "monto_total": "240000",
        })
        self.assertEqual(r.status_code, 302)
        self.assertFalse(GastoComun.objects.filter(condominio=self.condominio, periodo="2026-11").exists())

    def test_directiva_sigue_viendo_la_lista_sin_boton_de_crear(self):
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("gastos-comunes-list"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(reverse("gastos-comunes-crear").encode(), r.content)


class GenerarGastoComunSuscripcionTests(TestCase):
    """Generar un gasto común nuevo exige suscripción al día (SuscripcionActivaMixin)
    -- el resto de gastos comunes (ver, marcar pagado) sigue disponible aunque venza."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Gasto Suscripcion", plan="premium", pagado_hasta=None)

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="gasto_susc_admon")

    def test_bloqueado_si_la_suscripcion_no_esta_al_dia(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("gastos-comunes-crear"), {
            "periodo": "2026-11", "modo": "total", "monto_total": "240000",
        })
        self.assertEqual(r.status_code, 302)
        self.assertFalse(GastoComun.objects.filter(condominio=self.condominio, periodo="2026-11").exists())

    def test_la_lista_sigue_disponible_aunque_venza(self):
        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("gastos-comunes-list"))
        self.assertEqual(r.status_code, 200)


class DatosTransferenciaPermisosTests(TestCase):
    """Los datos de transferencia (banco/cuenta/RUT para pagar gastos
    comunes) quedaron exclusivos de administración -- antes vivían en "Mi
    condominio" (exclusivo directiva), ahora ni directiva puede editarlos."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Transferencia Permisos", plan="premium")

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="transf_admon")
        self.directiva = crear_membresia(self.condominio, "directiva", username="transf_directiva")

    def test_administracion_puede_editar_datos_transferencia(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("datos-transferencia"), {"datos_transferencia": "Banco Estado, cta 123, RUT 11.111.111-1"})
        self.assertEqual(r.status_code, 302)
        self.condominio.refresh_from_db()
        self.assertIn("Banco Estado", self.condominio.datos_transferencia)

    def test_directiva_no_puede_editar_datos_transferencia(self):
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("datos-transferencia"))
        self.assertEqual(r.status_code, 302)
        r = self.client.post(reverse("datos-transferencia"), {"datos_transferencia": "Intento de directiva"})
        self.assertEqual(r.status_code, 302)
        self.condominio.refresh_from_db()
        self.assertNotIn("Intento de directiva", self.condominio.datos_transferencia or "")

    def test_mi_condominio_ya_no_tiene_el_form_de_transferencia(self):
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("mi-condominio"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"datos_transferencia", r.content)


class BoucherPDFPermisosTests(TestCase):
    """Comprobante de pago descargable (reemplaza el talonario de papel que
    llenaba a mano quien cobraba) -- solo visible para el dueño de la unidad
    o para directiva/administración, y solo si la cuota ya está pagada."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Boucher", plan="premium")
        cls.unidad_propia = Unidad.objects.create(condominio=cls.condominio, numero="101")
        cls.unidad_ajena = Unidad.objects.create(condominio=cls.condominio, numero="102")
        cls.gasto = GastoComun.objects.create(condominio=cls.condominio, periodo="2026-11", monto_total=0, fecha_vencimiento="2026-11-30")
        cls.cuota_pagada = CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad_propia, monto=19990, estado="pagado", fecha_pago="2026-11-05")
        cls.cuota_pendiente = CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad_ajena, monto=19990, estado="pendiente")

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="boucher_admon")
        self.residente = crear_membresia(self.condominio, "residente", username="boucher_residente", unidad=self.unidad_propia)
        self.otro_residente = crear_membresia(self.condominio, "residente", username="boucher_otro", unidad=self.unidad_ajena)

    def test_residente_descarga_su_propio_comprobante_pagado(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("cuota-boucher", args=[self.cuota_pagada.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_residente_no_puede_ver_comprobante_de_otra_unidad(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("cuota-boucher", args=[self.cuota_pendiente.pk]))
        self.assertEqual(r.status_code, 302)

    def test_administracion_puede_ver_comprobante_de_cualquier_unidad(self):
        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("cuota-boucher", args=[self.cuota_pagada.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_no_se_puede_descargar_comprobante_de_cuota_sin_pagar(self):
        self.client.force_login(self.otro_residente.user)
        r = self.client.get(reverse("cuota-boucher", args=[self.cuota_pendiente.pk]))
        self.assertEqual(r.status_code, 302)


class MarcarCuotaPagadaEnviaBoucherTests(TestCase):
    """Al marcar una cuota como pagada, el comprobante SOLO se manda si quien
    la marca eligió un correo de destino -- a propósito no se manda solo a
    todos los residentes de la unidad (puede haber más de una cuenta por
    depto, incluida la de un menor de edad). La lista de cuotas sugiere el
    correo del residente cuando hay uno solo, pero es editable."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Boucher Correo", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="201")
        cls.unidad_dos_residentes = Unidad.objects.create(condominio=cls.condominio, numero="202")
        cls.gasto = GastoComun.objects.create(condominio=cls.condominio, periodo="2026-12", monto_total=0, fecha_vencimiento="2026-12-31")
        cls.cuota = CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad, monto=19990)
        cls.cuota_dos_residentes = CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad_dos_residentes, monto=19990)

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="marcar_admon")
        crear_membresia(self.condominio, "residente", username="marcar_residente", unidad=self.unidad, email="vecino@example.com")
        crear_membresia(self.condominio, "residente", username="marcar_padre", unidad=self.unidad_dos_residentes, email="padre@example.com")
        crear_membresia(self.condominio, "residente", username="marcar_hijo_menor", unidad=self.unidad_dos_residentes, email="hijo@example.com")

    def test_marcar_pagada_con_correo_destino_manda_el_comprobante(self):
        from django.core import mail

        self.client.force_login(self.administracion.user)
        self.client.post(reverse("cuota-marcar-pagada", args=[self.cuota.pk]), {"correo_destino": "vecino@example.com"})

        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["vecino@example.com"])
        self.assertEqual(len(correo.attachments), 1)
        nombre, contenido, tipo = correo.attachments[0]
        self.assertEqual(tipo, "application/pdf")
        self.assertTrue(contenido.startswith(b"%PDF"))

    def test_marcar_pagada_sin_correo_destino_no_manda_nada(self):
        from django.core import mail

        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("cuota-marcar-pagada", args=[self.cuota.pk]))

        self.assertEqual(r.status_code, 302)
        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.estado, "pagado")
        self.assertEqual(len(mail.outbox), 0)

    def test_marcar_pagada_con_correo_invalido_no_manda_nada_pero_igual_marca_pagada(self):
        """correo_destino es un input de texto libre -- validate_email lo
        descarta en vez de reventar si alguien manda algo que no es un email
        real (incluido un intento de inyectar saltos de línea)."""
        from django.core import mail

        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("cuota-marcar-pagada", args=[self.cuota.pk]), {"correo_destino": "no-es-un-correo\nInyectado: true"})

        self.assertEqual(r.status_code, 302)
        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.estado, "pagado")
        self.assertEqual(len(mail.outbox), 0)

    def test_lista_de_cuotas_sugiere_el_correo_cuando_hay_un_solo_residente(self):
        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("gastos-comunes-cuotas", args=[self.gasto.pk]))
        self.assertIn(b'value="vecino@example.com"', r.content)

    def test_lista_de_cuotas_no_sugiere_nada_si_hay_mas_de_un_residente(self):
        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("gastos-comunes-cuotas", args=[self.gasto.pk]))
        contenido = r.content.decode()
        # el input de la cuota 2 (dos residentes) no debe traer un "value" precargado
        self.assertIn('placeholder="Correo del comprobante (opcional)"\n                           >', contenido)
        # pero ambos correos sí aparecen como sugerencias del datalist
        self.assertIn('<option value="padre@example.com">', contenido)
        self.assertIn('<option value="hijo@example.com">', contenido)


class GenerarCuotasModelTests(TestCase):
    """GastoComun.generar_cuotas() en sí -- los tests de arriba crean el
    gasto común vía la vista pero sin ninguna Unidad en el condominio, así
    que nunca llegan al cuerpo real del prorrateo (solo al "no hay unidades,
    no hace nada")."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Generar Cuotas", plan="premium")

    def test_sin_unidades_no_crea_cuotas(self):
        gasto = GastoComun.objects.create(condominio=self.condominio, periodo="2026-01", monto_total=100000, fecha_vencimiento=datetime.date(2026, 1, 31))
        gasto.generar_cuotas()
        self.assertFalse(CuotaUnidad.objects.filter(gasto_comun=gasto).exists())

    def test_monto_por_unidad_da_el_mismo_valor_fijo_a_todas(self):
        Unidad.objects.create(condominio=self.condominio, numero="1")
        Unidad.objects.create(condominio=self.condominio, numero="2")
        gasto = GastoComun.objects.create(
            condominio=self.condominio, periodo="2026-02", monto_total=24000, monto_por_unidad=12000,
            fecha_vencimiento=datetime.date(2026, 2, 28),
        )
        gasto.generar_cuotas()
        cuotas = CuotaUnidad.objects.filter(gasto_comun=gasto)
        self.assertEqual(cuotas.count(), 2)
        self.assertTrue(all(c.monto == 12000 for c in cuotas))

    def test_prorratea_por_alicuota_si_no_hay_monto_fijo(self):
        Unidad.objects.create(condominio=self.condominio, numero="1", alicuota="0.75")
        Unidad.objects.create(condominio=self.condominio, numero="2", alicuota="0.25")
        gasto = GastoComun.objects.create(condominio=self.condominio, periodo="2026-03", monto_total=100000, fecha_vencimiento=datetime.date(2026, 3, 31))
        gasto.generar_cuotas()
        cuota_1 = CuotaUnidad.objects.get(gasto_comun=gasto, unidad__numero="1")
        cuota_2 = CuotaUnidad.objects.get(gasto_comun=gasto, unidad__numero="2")
        self.assertEqual(cuota_1.monto, 75000)
        self.assertEqual(cuota_2.monto, 25000)

    def test_reparte_parejo_si_ninguna_unidad_tiene_alicuota(self):
        Unidad.objects.create(condominio=self.condominio, numero="1")
        Unidad.objects.create(condominio=self.condominio, numero="2")
        Unidad.objects.create(condominio=self.condominio, numero="3")
        gasto = GastoComun.objects.create(condominio=self.condominio, periodo="2026-04", monto_total=30000, fecha_vencimiento=datetime.date(2026, 4, 30))
        gasto.generar_cuotas()
        cuotas = CuotaUnidad.objects.filter(gasto_comun=gasto)
        self.assertEqual(cuotas.count(), 3)
        self.assertTrue(all(c.monto == 10000 for c in cuotas))

    def test_no_duplica_cuotas_ya_generadas(self):
        Unidad.objects.create(condominio=self.condominio, numero="1")
        gasto = GastoComun.objects.create(condominio=self.condominio, periodo="2026-05", monto_total=10000, fecha_vencimiento=datetime.date(2026, 5, 31))
        gasto.generar_cuotas()
        gasto.generar_cuotas()
        self.assertEqual(CuotaUnidad.objects.filter(gasto_comun=gasto).count(), 1)

    def test_str_de_gasto_comun_y_cuota(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        gasto = GastoComun.objects.create(condominio=self.condominio, periodo="2026-06", monto_total=10000, fecha_vencimiento=datetime.date(2026, 6, 30))
        cuota = CuotaUnidad.objects.create(gasto_comun=gasto, unidad=unidad, monto=10000)
        self.assertIn("2026-06", str(gasto))
        self.assertIn("Pendiente", str(cuota))


class CuotaUnidadApiTests(TestCase):
    """CuotaUnidadViewSet (solo lectura) -- un residente solo ve sus propias
    cuotas, directiva/administración ven las de todo el condominio."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Cuota Api", plan="premium")
        cls.unidad_propia = Unidad.objects.create(condominio=cls.condominio, numero="10")
        cls.unidad_ajena = Unidad.objects.create(condominio=cls.condominio, numero="20")
        cls.gasto = GastoComun.objects.create(condominio=cls.condominio, periodo="2026-07", monto_total=20000, fecha_vencimiento=datetime.date(2026, 7, 31))
        cls.cuota_propia = CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad_propia, monto=10000)
        cls.cuota_ajena = CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad_ajena, monto=10000)

    def test_residente_solo_ve_las_cuotas_de_su_propia_unidad(self):
        residente = crear_membresia(self.condominio, "residente", unidad=self.unidad_propia, username="cuota_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("cuota-unidad-list"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        resultados = datos["results"] if isinstance(datos, dict) else datos
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["unidad_numero"], "10")

    def test_administracion_ve_todas_las_cuotas_del_condominio(self):
        administracion = crear_membresia(self.condominio, "administracion", username="cuota_api_admon")
        self.client.force_login(administracion.user)
        r = self.client.get(reverse("cuota-unidad-list"))
        datos = r.json()
        resultados = datos["results"] if isinstance(datos, dict) else datos
        self.assertEqual(len(resultados), 2)

    def test_sin_autenticar_no_puede_listar(self):
        r = self.client.get(reverse("cuota-unidad-list"))
        self.assertEqual(r.status_code, 401)


class ExportarCuotasTests(TestCase):
    """Exportar el listado de cuotas de un periodo a Excel/PDF -- mismo
    permiso que verlo en pantalla (EsDirectivaOAdministracionMixin), un
    residente no debería poder descargarlo."""

    @classmethod
    def setUpTestData(cls):
        from core.models import Torre

        cls.condominio = Condominio.objects.create(nombre="Test Exportar Cuotas", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="5")
        cls.unidad_pagada = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="501")
        cls.unidad_pendiente = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="502")
        cls.gasto = GastoComun.objects.create(condominio=cls.condominio, periodo="2026-08", monto_total=24000, fecha_vencimiento=datetime.date(2026, 8, 31))
        CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad_pagada, monto=12000, estado="pagado", fecha_pago=datetime.date(2026, 8, 5))
        CuotaUnidad.objects.create(gasto_comun=cls.gasto, unidad=cls.unidad_pendiente, monto=12000)

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="exportar_admon")
        self.residente = crear_membresia(self.condominio, "residente", unidad=self.unidad_pagada, username="exportar_residente")

    def test_administracion_puede_descargar_excel(self):
        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("gastos-comunes-cuotas-excel", args=[self.gasto.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertIn("gastos_comunes_2026-08.xlsx", r["Content-Disposition"])

    def test_administracion_puede_descargar_pdf(self):
        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("gastos-comunes-cuotas-pdf", args=[self.gasto.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("gastos_comunes_2026-08.pdf", r["Content-Disposition"])

    def test_residente_no_puede_descargar(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("gastos-comunes-cuotas-excel", args=[self.gasto.pk]))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(reverse("gastos-comunes-cuotas-pdf", args=[self.gasto.pk]))
        self.assertEqual(r.status_code, 302)

    def test_excel_contiene_las_cifras_correctas(self):
        from openpyxl import load_workbook

        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("gastos-comunes-cuotas-excel", args=[self.gasto.pk]))
        wb = load_workbook(BytesIO(r.content))
        ws = wb.active
        valores = [celda.value for fila in ws.iter_rows() for celda in fila if celda.value is not None]
        self.assertIn("501", valores)
        self.assertIn("502", valores)
        self.assertIn(12000, valores)
        self.assertIn("Total recaudado", valores)
        self.assertIn("Total pendiente", valores)

    def test_filtro_por_torre_tambien_aplica_al_exportar(self):
        from core.models import Torre

        otra_torre = Torre.objects.create(condominio=self.condominio, nombre="9")
        unidad_otra_torre = Unidad.objects.create(condominio=self.condominio, torre=otra_torre, numero="901")
        CuotaUnidad.objects.create(gasto_comun=self.gasto, unidad=unidad_otra_torre, monto=12000)

        self.client.force_login(self.administracion.user)
        r = self.client.get(reverse("gastos-comunes-cuotas-excel", args=[self.gasto.pk]), {"torre": self.torre.pk})
        from openpyxl import load_workbook

        wb = load_workbook(BytesIO(r.content))
        ws = wb.active
        valores = [celda.value for fila in ws.iter_rows() for celda in fila if celda.value is not None]
        self.assertIn("501", valores)
        self.assertNotIn("901", valores)
