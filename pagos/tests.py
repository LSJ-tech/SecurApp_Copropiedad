import datetime
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from mercadopago.errors.response import MPResponse

from core.models import Condominio, Membresia, Torre, Unidad

from .mercadopago_client import (
    cancelar_suscripcion_recurrente,
    crear_suscripcion_recurrente,
    obtener_pago_mercadopago,
    obtener_preapproval_mercadopago,
)
from .models import Pago, SuscripcionRecurrente


def crear_membresia(condominio, rol, unidad=None, **user_kwargs):
    """Sin password: los tests se autentican con force_login."""
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    email = user_kwargs.pop("email", f"{username}@example.com")
    user = User.objects.create_user(username=username, email=email, **user_kwargs)
    return Membresia.objects.create(
        user=user, condominio=condominio, rol=rol, unidad=unidad, terminos_aceptados_en=timezone.now(),
    )


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
class DonarViewTests(TestCase):
    """Cualquier miembro puede activar una donación mensual automática --
    sin tocar la red real de Mercado Pago, se mockea crear_suscripcion_recurrente."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Donar", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="5")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="502")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="don_residente")
        self.client.force_login(self.residente.user)

    @patch("pagos.views.crear_suscripcion_recurrente", return_value="https://fake-mp.test/autorizar/1")
    def test_residente_puede_activar_donacion_automatica(self, mock_crear):
        r = self.client.post(reverse("donar"))
        self.assertEqual(r.status_code, 302)
        suscripcion = SuscripcionRecurrente.objects.get(condominio=self.condominio, tipo="donacion")
        self.assertEqual(suscripcion.membresia_id, self.residente.pk)
        self.assertEqual(suscripcion.monto, Decimal("2000"))
        mock_crear.assert_called_once()

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="")
    def test_sin_token_configurado_no_crea_suscripcion(self):
        r = self.client.post(reverse("donar"))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(SuscripcionRecurrente.objects.filter(condominio=self.condominio).exists())

    def test_usuario_sin_membresia_no_puede_donar(self):
        sin_membresia = User.objects.create_user(username="sin_membresia")
        self.client.logout()
        self.client.force_login(sin_membresia)
        r = self.client.post(reverse("donar"))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(SuscripcionRecurrente.objects.exists())

    def test_sin_email_no_puede_activar_la_donacion(self):
        self.residente.user.email = ""
        self.residente.user.save(update_fields=["email"])
        r = self.client.post(reverse("donar"), follow=True)
        self.assertContains(r, "Agrega tu email")
        self.assertFalse(SuscripcionRecurrente.objects.exists())

    @patch("pagos.views.crear_suscripcion_recurrente", return_value="https://fake-mp.test/autorizar/1")
    def test_no_deja_activar_una_segunda_donacion_si_ya_hay_una_activa(self, mock_crear):
        SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-1", estado="autorizada",
        )
        r = self.client.post(reverse("donar"), follow=True)
        self.assertContains(r, "Ya tienes una donación automática activa")
        self.assertEqual(SuscripcionRecurrente.objects.filter(condominio=self.condominio, tipo="donacion").count(), 1)


class CancelarDonacionRecurrenteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Cancelar Donacion", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="cancel_don_residente")
        self.client.force_login(self.residente.user)

    @patch("pagos.views.cancelar_suscripcion_recurrente", return_value=True)
    def test_cancela_la_donacion_activa(self, mock_cancelar):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("1000"), mercadopago_preapproval_id="pre-1", estado="autorizada",
        )
        r = self.client.post(reverse("cancelar-donacion"), follow=True)
        self.assertContains(r, "cancelamos tu donación")
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "cancelada")
        self.assertIsNotNone(suscripcion.fecha_cancelacion)

    def test_sin_donacion_activa_muestra_error(self):
        r = self.client.post(reverse("cancelar-donacion"), follow=True)
        self.assertContains(r, "No tienes ninguna donación automática activa")

    @patch("pagos.views.cancelar_suscripcion_recurrente", return_value=False)
    def test_si_mercadopago_rechaza_la_cancelacion_no_marca_cancelada(self, mock_cancelar):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("1000"), mercadopago_preapproval_id="pre-1", estado="autorizada",
        )
        r = self.client.post(reverse("cancelar-donacion"), follow=True)
        self.assertContains(r, "No pudimos cancelar")
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "autorizada")


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
class SuscripcionPagarViewTests(TestCase):
    """Solo directiva/administración activan el cobro automático de la
    suscripción (monto fijo), y no se puede activar dos veces."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Suscripcion", plan="premium", pagado_hasta=None)

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="susc_admon")
        self.directiva = crear_membresia(self.condominio, "directiva", username="susc_directiva")
        self.residente = crear_membresia(self.condominio, "residente", username="susc_residente")

    @patch("pagos.views.crear_suscripcion_recurrente", return_value="https://fake-mp.test/autorizar/1")
    def test_administracion_puede_activar_la_suscripcion(self, mock_crear):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        suscripcion = SuscripcionRecurrente.objects.get(condominio=self.condominio, tipo="suscripcion")
        self.assertEqual(suscripcion.monto, Decimal("19990"))
        self.assertEqual(suscripcion.membresia_id, self.administracion.pk)

    @patch("pagos.views.crear_suscripcion_recurrente", return_value="https://fake-mp.test/autorizar/1")
    def test_directiva_tambien_puede_activarla(self, mock_crear):
        self.client.force_login(self.directiva.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(SuscripcionRecurrente.objects.filter(condominio=self.condominio, tipo="suscripcion").exists())

    def test_residente_no_puede_activarla(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(SuscripcionRecurrente.objects.filter(condominio=self.condominio, tipo="suscripcion").exists())

    @patch("pagos.views.crear_suscripcion_recurrente", return_value="https://fake-mp.test/autorizar/1")
    def test_no_deja_activar_dos_veces(self, mock_crear):
        self.client.force_login(self.administracion.user)
        self.client.post(reverse("pagar-suscripcion"))
        r = self.client.post(reverse("pagar-suscripcion"), follow=True)
        self.assertContains(r, "Ya existe una suscripción automática activa")
        self.assertEqual(SuscripcionRecurrente.objects.filter(condominio=self.condominio, tipo="suscripcion").count(), 1)

    def test_sin_email_no_puede_activarla(self):
        self.administracion.user.email = ""
        self.administracion.user.save(update_fields=["email"])
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("pagar-suscripcion"), follow=True)
        self.assertContains(r, "Agrega tu email")
        self.assertFalse(SuscripcionRecurrente.objects.exists())


class CancelarSuscripcionRecurrenteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Cancelar Suscripcion", plan="premium")

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="cancel_susc_admon")
        self.residente = crear_membresia(self.condominio, "residente", username="cancel_susc_residente")

    @patch("pagos.views.cancelar_suscripcion_recurrente", return_value=True)
    def test_administracion_cancela_la_suscripcion_activa(self, mock_cancelar):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.administracion, tipo="suscripcion",
            monto=Decimal("19990"), mercadopago_preapproval_id="pre-1", estado="autorizada",
        )
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("cancelar-suscripcion"), follow=True)
        self.assertContains(r, "cancelamos el cobro automático")
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "cancelada")

    def test_residente_no_puede_cancelarla(self):
        SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.administracion, tipo="suscripcion",
            monto=Decimal("19990"), mercadopago_preapproval_id="pre-1", estado="autorizada",
        )
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("cancelar-suscripcion"), follow=True)
        self.assertContains(r, "exclusivo de directiva/administración")

    def test_sin_suscripcion_activa_muestra_error(self):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("cancelar-suscripcion"), follow=True)
        self.assertContains(r, "No hay ninguna suscripción automática activa")


class WebhookMercadoPagoTests(TestCase):
    """La donación aprobada NO debe tocar pagado_hasta/plan del condominio
    -- eso es exclusivo de un cobro de tipo 'suscripcion'."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Webhook", plan="free", pagado_hasta=None)

    def _suscripcion(self, tipo="suscripcion", monto="9990", estado="autorizada", preapproval_id="pre-1"):
        return SuscripcionRecurrente.objects.create(
            condominio=self.condominio, tipo=tipo, monto=Decimal(monto),
            mercadopago_preapproval_id=preapproval_id, estado=estado,
        )

    def _simular_webhook_cobro(self, payment_id, preapproval_id, estado_mp="approved"):
        with patch(
            "pagos.views.obtener_pago_mercadopago",
            return_value={"status": estado_mp, "preapproval_id": preapproval_id},
        ):
            return self.client.post(
                reverse("pago-webhook"),
                data=json.dumps({"type": "payment", "data": {"id": payment_id}}),
                content_type="application/json",
            )

    def test_cobro_de_donacion_aprobado_no_extiende_plan_ni_vencimiento(self):
        suscripcion = self._suscripcion(tipo="donacion", preapproval_id="pre-don")
        self._simular_webhook_cobro("pay-1", "pre-don")
        self.condominio.refresh_from_db()
        self.assertIsNone(self.condominio.pagado_hasta)
        self.assertEqual(self.condominio.plan, "free")
        pago = Pago.objects.get(mercadopago_payment_id="pay-1")
        self.assertEqual(pago.suscripcion_recurrente, suscripcion)
        self.assertEqual(pago.estado, "aprobado")

    def test_cobro_de_suscripcion_aprobado_si_extiende_plan_y_vencimiento(self):
        self._suscripcion(tipo="suscripcion", preapproval_id="pre-susc")
        self._simular_webhook_cobro("pay-2", "pre-susc")
        self.condominio.refresh_from_db()
        self.assertIsNotNone(self.condominio.pagado_hasta)
        self.assertEqual(self.condominio.plan, "premium")

    def test_cobro_no_aprobado_no_crea_pago(self):
        self._suscripcion(tipo="suscripcion", preapproval_id="pre-pend")
        self._simular_webhook_cobro("pay-3", "pre-pend", estado_mp="pending")
        self.assertFalse(Pago.objects.filter(mercadopago_payment_id="pay-3").exists())

    def test_cobro_sin_suscripcion_relacionada_no_crea_pago_ni_falla(self):
        r = self._simular_webhook_cobro("pay-4", "preapproval-inexistente")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Pago.objects.filter(mercadopago_payment_id="pay-4").exists())

    def test_el_mismo_payment_id_no_duplica_el_pago(self):
        self._suscripcion(tipo="suscripcion", preapproval_id="pre-dup")
        self._simular_webhook_cobro("pay-5", "pre-dup")
        self._simular_webhook_cobro("pay-5", "pre-dup")
        self.assertEqual(Pago.objects.filter(mercadopago_payment_id="pay-5").count(), 1)

    def test_cambio_de_estado_de_preapproval_actualiza_la_suscripcion(self):
        suscripcion = self._suscripcion(tipo="suscripcion", estado="pendiente", preapproval_id="pre-estado")
        with patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"}):
            r = self.client.post(
                reverse("pago-webhook"),
                data=json.dumps({"type": "preapproval", "data": {"id": "pre-estado"}}),
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "autorizada")

    def test_preapproval_cancelada_registra_fecha_de_cancelacion(self):
        suscripcion = self._suscripcion(tipo="suscripcion", estado="autorizada", preapproval_id="pre-cancel")
        with patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "cancelled"}):
            self.client.post(
                reverse("pago-webhook"),
                data=json.dumps({"type": "preapproval", "data": {"id": "pre-cancel"}}),
                content_type="application/json",
            )
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "cancelada")
        self.assertIsNotNone(suscripcion.fecha_cancelacion)


class WebhookMercadoPagoRamasFaltantesTests(TestCase):
    """Las ramas de salida temprana del webhook -- nunca se confía en el
    cuerpo del POST, así que cualquiera de estos casos debe responder
    200/400 sin tocar ningún Pago/SuscripcionRecurrente."""

    def test_body_invalido_devuelve_400(self):
        r = self.client.post(reverse("pago-webhook"), data="esto no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_sin_id_devuelve_200_sin_hacer_nada(self):
        r = self.client.post(reverse("pago-webhook"), data=json.dumps({"data": {}}), content_type="application/json")
        self.assertEqual(r.status_code, 200)

    @patch("pagos.views.obtener_pago_mercadopago", return_value=None)
    def test_mercadopago_no_devuelve_el_pago_devuelve_200(self, mock_obtener):
        r = self.client.post(
            reverse("pago-webhook"),
            data=json.dumps({"type": "payment", "data": {"id": "999"}}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value=None)
    def test_mercadopago_no_devuelve_el_preapproval_devuelve_200(self, mock_obtener):
        r = self.client.post(
            reverse("pago-webhook"),
            data=json.dumps({"type": "preapproval", "data": {"id": "999"}}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)


class MercadoPagoClientTests(TestCase):
    """Tests directos de pagos/mercadopago_client.py -- el resto de los
    tests de esta app mockean crear_suscripcion_recurrente/
    cancelar_suscripcion_recurrente/obtener_* a nivel de vista a propósito
    (sin tocar la red real de Mercado Pago), así que este módulo (el único
    que arma la autorización de verdad) se quedaba sin ningún test propio."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test MP Client", plan="premium")

    def _request(self):
        return RequestFactory().get("/")

    def _suscripcion(self, **kwargs):
        kwargs.setdefault("condominio", self.condominio)
        kwargs.setdefault("tipo", "donacion")
        kwargs.setdefault("monto", Decimal("5000"))
        kwargs.setdefault("mercadopago_preapproval_id", "")
        return SuscripcionRecurrente.objects.create(**kwargs)

    @patch("pagos.mercadopago_client._sdk")
    def test_donacion_arma_la_razon_con_nombre_del_condominio(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.create.return_value = MPResponse(
            {"status": 201, "response": {"id": "preap-1", "init_point": "https://fake-mp.test/autorizar/1"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        suscripcion = self._suscripcion()
        url = crear_suscripcion_recurrente(suscripcion, "donante@example.com", self._request())
        self.assertEqual(url, "https://fake-mp.test/autorizar/1")
        cuerpo = mock_sdk.preapproval.return_value.create.call_args[0][0]
        self.assertIn(self.condominio.nombre, cuerpo["reason"])
        self.assertEqual(cuerpo["payer_email"], "donante@example.com")
        self.assertEqual(cuerpo["auto_recurring"]["frequency_type"], "months")
        self.assertEqual(cuerpo["auto_recurring"]["currency_id"], "CLP")
        self.assertNotIn("end_date", cuerpo)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.mercadopago_preapproval_id, "preap-1")

    @patch("pagos.mercadopago_client._sdk")
    def test_la_razon_nunca_pasa_los_60_caracteres(self, mock_sdk_factory):
        """Mercado Pago rechaza el reason si pasa de 60 caracteres (bug real
        encontrado en producción: un condominio con torre/depto largo armaba
        un texto más largo que eso y la API lo rechazaba con 400)."""
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.create.return_value = MPResponse(
            {"status": 201, "response": {"id": "preap-largo", "init_point": "https://fake-mp.test/autorizar/largo"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        condominio_nombre_largo = Condominio.objects.create(nombre="Condominio Con Un Nombre Verdaderamente Larguísimo", plan="premium")
        torre = Torre.objects.create(condominio=condominio_nombre_largo, nombre="Torre Norte Edificio Principal")
        unidad = Unidad.objects.create(condominio=condominio_nombre_largo, torre=torre, numero="1504-B")
        membresia = crear_membresia(condominio_nombre_largo, "residente", unidad=unidad, username="razon_larga_residente")
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=condominio_nombre_largo, membresia=membresia, tipo="donacion", monto=Decimal("2000"),
        )
        crear_suscripcion_recurrente(suscripcion, "donante@example.com", self._request())
        cuerpo = mock_sdk.preapproval.return_value.create.call_args[0][0]
        self.assertLessEqual(len(cuerpo["reason"]), 60)

    @patch("pagos.mercadopago_client._sdk")
    def test_suscripcion_usa_razon_distinta_a_la_de_donacion(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.create.return_value = MPResponse(
            {"status": 201, "response": {"id": "preap-2", "init_point": "https://fake-mp.test/autorizar/2"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        suscripcion = self._suscripcion(tipo="suscripcion", monto=Decimal("19990"))
        crear_suscripcion_recurrente(suscripcion, "admin@example.com", self._request())
        cuerpo = mock_sdk.preapproval.return_value.create.call_args[0][0]
        self.assertIn("Suscripción", cuerpo["reason"])
        self.assertNotIn("Donación", cuerpo["reason"])

    @patch("pagos.mercadopago_client._sdk")
    def test_mercadopago_rechaza_la_solicitud_devuelve_none(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.create.return_value = MPResponse(
            {"status": 400, "response": {"message": "bad request"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        suscripcion = self._suscripcion()
        url = crear_suscripcion_recurrente(suscripcion, "donante@example.com", self._request())
        self.assertIsNone(url)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.mercadopago_preapproval_id, "")

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
    @patch("pagos.mercadopago_client._sdk")
    def test_credencial_de_prueba_usa_sandbox_init_point_si_viene(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.create.return_value = MPResponse({
            "status": 201,
            "response": {"id": "preap-3", "init_point": "https://fake-mp.test/prod", "sandbox_init_point": "https://fake-mp.test/sandbox"},
        })
        mock_sdk_factory.return_value = mock_sdk
        suscripcion = self._suscripcion()
        url = crear_suscripcion_recurrente(suscripcion, "donante@example.com", self._request())
        self.assertEqual(url, "https://fake-mp.test/sandbox")

    @patch("pagos.mercadopago_client._sdk")
    def test_cancelar_suscripcion_exitoso_devuelve_true(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.update.return_value = MPResponse(
            {"status": 200, "response": {"id": "preap-4", "status": "cancelled"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        suscripcion = self._suscripcion(mercadopago_preapproval_id="preap-4")
        self.assertTrue(cancelar_suscripcion_recurrente(suscripcion))
        mock_sdk.preapproval.return_value.update.assert_called_once_with("preap-4", {"status": "cancelled"})

    @patch("pagos.mercadopago_client._sdk")
    def test_cancelar_suscripcion_fallido_devuelve_false(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.update.return_value = MPResponse(
            {"status": 404, "response": {"message": "not found"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        suscripcion = self._suscripcion(mercadopago_preapproval_id="preap-5")
        self.assertFalse(cancelar_suscripcion_recurrente(suscripcion))

    @patch("pagos.mercadopago_client._sdk")
    def test_obtener_preapproval_exitoso_devuelve_el_body(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.get.return_value = MPResponse(
            {"status": 200, "response": {"id": "preap-6", "status": "authorized"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        resultado = obtener_preapproval_mercadopago("preap-6")
        self.assertEqual(resultado["status"], "authorized")

    @patch("pagos.mercadopago_client._sdk")
    def test_obtener_preapproval_fallido_devuelve_none(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preapproval.return_value.get.return_value = MPResponse(
            {"status": 404, "response": {"message": "not found"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        resultado = obtener_preapproval_mercadopago("preap-404")
        self.assertIsNone(resultado)

    @patch("pagos.mercadopago_client._sdk")
    def test_obtener_pago_exitoso_devuelve_el_body(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.payment.return_value.get.return_value = MPResponse(
            {"status": 200, "response": {"id": 999, "status": "approved"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        resultado = obtener_pago_mercadopago("999")
        self.assertEqual(resultado["status"], "approved")

    @patch("pagos.mercadopago_client._sdk")
    def test_obtener_pago_fallido_devuelve_none(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.payment.return_value.get.return_value = MPResponse(
            {"status": 404, "response": {"message": "not found"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        resultado = obtener_pago_mercadopago("999")
        self.assertIsNone(resultado)


class PagoAdminTests(TestCase):
    """Columnas calculadas de PagoAdmin (pagos/admin.py) -- probadas
    directo sobre los métodos, sin pasar por el cliente admin de Django."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Pago Admin", plan="premium")

    def setUp(self):
        from .admin import PagoAdmin
        self.admin = PagoAdmin(Pago, None)

    def test_donante_sin_membresia_muestra_guion(self):
        pago = Pago.objects.create(condominio=self.condominio, tipo="suscripcion", monto=Decimal("19990"))
        self.assertEqual(self.admin.donante(pago), "-")
        self.assertEqual(self.admin.torre(pago), "-")
        self.assertEqual(self.admin.unidad(pago), "-")

    def test_donante_con_membresia_sin_unidad(self):
        membresia = crear_membresia(self.condominio, "residente", username="admin_sin_unidad")
        pago = Pago.objects.create(condominio=self.condominio, tipo="donacion", monto=Decimal("1000"), membresia=membresia)
        self.assertEqual(self.admin.torre(pago), "-")
        self.assertEqual(self.admin.unidad(pago), "-")

    def test_donante_con_torre_y_unidad(self):
        torre = Torre.objects.create(condominio=self.condominio, nombre="7")
        unidad = Unidad.objects.create(condominio=self.condominio, torre=torre, numero="701")
        membresia = crear_membresia(self.condominio, "residente", unidad=unidad, username="admin_con_unidad", first_name="Ana", last_name="Soto")
        pago = Pago.objects.create(condominio=self.condominio, tipo="donacion", monto=Decimal("1000"), membresia=membresia)
        self.assertEqual(self.admin.donante(pago), "Ana Soto")
        self.assertEqual(self.admin.torre(pago), "7")
        self.assertEqual(self.admin.unidad(pago), "701")

    def test_donante_sin_nombre_usa_username(self):
        membresia = crear_membresia(self.condominio, "residente", username="sin_nombre_admin")
        pago = Pago.objects.create(condominio=self.condominio, tipo="donacion", monto=Decimal("1000"), membresia=membresia)
        self.assertEqual(self.admin.donante(pago), "sin_nombre_admin")

    def test_changelist_renderiza_con_la_insignia(self):
        Pago.objects.create(condominio=self.condominio, tipo="suscripcion", plan="premium", monto=19990, estado="aprobado")
        staff = User.objects.create_superuser(username="admin_pago_staff", password="x", email="admin_pago_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/pagos/pago/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Aprobado")


class SuscripcionRecurrenteAdminTests(TestCase):
    """Insignia de color para estado y la acción "cancelar en Mercado Pago"
    (ver pagos/admin.py)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Suscripcion Admin", plan="premium")

    def setUp(self):
        self.staff = User.objects.create_superuser(username="admin_susc_staff", password="x")
        self.client.force_login(self.staff)

    def test_changelist_renderiza_con_la_insignia(self):
        SuscripcionRecurrente.objects.create(
            condominio=self.condominio, tipo="suscripcion", monto=19990,
            mercadopago_preapproval_id="pre-admin-1", estado="autorizada",
        )
        r = self.client.get("/admin/pagos/suscripcionrecurrente/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Autorizada")

    @patch("pagos.admin.cancelar_suscripcion_recurrente", return_value=True)
    def test_accion_cancela_en_mercadopago(self, mock_cancelar):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, tipo="suscripcion", monto=19990,
            mercadopago_preapproval_id="pre-admin-2", estado="autorizada",
        )
        self.client.post("/admin/pagos/suscripcionrecurrente/", {
            "action": "cancelar_en_mercadopago",
            "_selected_action": [str(suscripcion.pk)],
        })
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "cancelada")

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_accion_sincroniza_el_estado_con_mercadopago(self, mock_obtener):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, tipo="suscripcion", monto=19990,
            mercadopago_preapproval_id="pre-admin-sync", estado="pendiente",
        )
        self.client.post("/admin/pagos/suscripcionrecurrente/", {
            "action": "sincronizar_con_mercadopago",
            "_selected_action": [str(suscripcion.pk)],
        })
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "autorizada")
        mock_obtener.assert_called_once_with("pre-admin-sync")

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value=None)
    def test_accion_sincronizar_avisa_si_mercadopago_no_responde(self, mock_obtener):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, tipo="suscripcion", monto=19990,
            mercadopago_preapproval_id="pre-admin-sync-falla", estado="pendiente",
        )
        r = self.client.post("/admin/pagos/suscripcionrecurrente/", {
            "action": "sincronizar_con_mercadopago",
            "_selected_action": [str(suscripcion.pk)],
        }, follow=True)
        self.assertContains(r, "No se pudo consultar la suscripción recurrente")
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "pendiente")


class SincronizarEstadoSuscripcionTests(TestCase):
    """sincronizar_estado_suscripcion (pagos/views.py) -- la misma lógica
    que usa el webhook al recibir un cambio de preapproval, pero como
    función reutilizable que también dispara la acción del admin."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Sync Estado", plan="premium")

    def _suscripcion(self, **kwargs):
        kwargs.setdefault("condominio", self.condominio)
        kwargs.setdefault("tipo", "suscripcion")
        kwargs.setdefault("monto", Decimal("19990"))
        kwargs.setdefault("mercadopago_preapproval_id", "pre-sync")
        kwargs.setdefault("estado", "pendiente")
        return SuscripcionRecurrente.objects.create(**kwargs)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_actualiza_el_estado_cuando_cambia(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion()
        self.assertTrue(sincronizar_estado_suscripcion(suscripcion))
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "autorizada")

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_no_hace_nada_si_el_estado_ya_coincide(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(estado="autorizada")
        with self.assertNumQueries(0):  # no hay que guardar nada si el estado no cambió
            sincronizar_estado_suscripcion(suscripcion)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value=None)
    def test_devuelve_false_si_mercadopago_no_responde(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion()
        self.assertFalse(sincronizar_estado_suscripcion(suscripcion))

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "cancelled"})
    def test_marca_fecha_de_cancelacion(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(estado="autorizada")
        sincronizar_estado_suscripcion(suscripcion)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "cancelada")
        self.assertIsNotNone(suscripcion.fecha_cancelacion)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_crea_el_pago_de_suscripcion_cuando_autoriza_por_primera_vez(self, mock_obtener):
        """Si el webhook nunca avisó el primer cobro, sincronizar a mano no
        debe dejar la suscripción "Autorizada" sin su Pago correspondiente
        (bug real: quedaba Autorizada pero /admin/pagos/pago/ vacío)."""
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion()
        pagado_hasta_antes = self.condominio.pagado_hasta
        sincronizar_estado_suscripcion(suscripcion)

        pago = suscripcion.cobros.get()
        self.assertEqual(pago.estado, "aprobado")
        self.assertEqual(pago.plan, "premium")
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.pagado_hasta, pagado_hasta_antes + datetime.timedelta(days=30))

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_crea_el_pago_de_donacion_sin_tocar_el_plan_del_condominio(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        condominio = Condominio.objects.create(nombre="Test Sync Donacion", plan="basico")
        suscripcion = self._suscripcion(
            condominio=condominio, tipo="donacion", monto=Decimal("2000"), mercadopago_preapproval_id="pre-sync-don",
        )
        pagado_hasta_antes = condominio.pagado_hasta
        sincronizar_estado_suscripcion(suscripcion)

        pago = suscripcion.cobros.get()
        self.assertEqual(pago.tipo, "donacion")
        self.assertEqual(pago.plan, "")
        condominio.refresh_from_db()
        self.assertEqual(condominio.pagado_hasta, pagado_hasta_antes)
        self.assertEqual(condominio.plan, "basico")

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_no_duplica_el_pago_si_ya_hay_uno_registrado(self, mock_obtener):
        """pausada -> autorizada (reactivación) no debe generar un segundo
        Pago fantasma -- solo la transición pendiente -> autorizada lo hace."""
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(estado="pausada")
        Pago.objects.create(
            condominio=self.condominio, suscripcion_recurrente=suscripcion, tipo="suscripcion",
            plan="premium", monto=suscripcion.monto, estado="aprobado", mercadopago_payment_id="ya-existente",
        )
        sincronizar_estado_suscripcion(suscripcion)

        self.assertEqual(suscripcion.cobros.count(), 1)


class PagoResultadoViewTests(TestCase):
    def test_muestra_el_estado_que_viene_en_la_url(self):
        condominio = Condominio.objects.create(nombre="Test Pago Resultado", plan="premium")
        membresia = crear_membresia(condominio, "residente", username="resultado_residente")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("pago-resultado") + "?status=approved")
        self.assertEqual(r.context["estado"], "approved")
