import datetime
import json
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, call, patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
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

    @patch("pagos.views.crear_suscripcion_recurrente", return_value=None)
    def test_si_mercadopago_no_devuelve_url_no_deja_la_suscripcion_a_medias(self, mock_crear):
        """crear_suscripcion_recurrente puede fallar del lado de Mercado
        Pago (red, credenciales, etc.) -- si devuelve None, la
        SuscripcionRecurrente que se había creado para intentarlo se borra,
        no queda una fila huérfana en estado "pendiente" para siempre."""
        r = self.client.post(reverse("donar"), follow=True)
        self.assertContains(r, "No pudimos iniciar la donación automática")
        self.assertFalse(SuscripcionRecurrente.objects.filter(condominio=self.condominio).exists())


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

    def test_usuario_sin_membresia_no_puede_cancelar(self):
        sin_membresia = User.objects.create_user(username="cancel_don_sin_membresia")
        self.client.logout()
        self.client.force_login(sin_membresia)
        r = self.client.post(reverse("cancelar-donacion"), follow=True)
        self.assertContains(r, "Tu cuenta no está vinculada a ningún condominio")

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


class WebhookFirmaTests(TestCase):
    """Hallazgo de seguridad real: el webhook nunca verificó x-signature --
    nunca permitió aprobar un pago falso (siempre se re-consulta a Mercado
    Pago antes, ver _manejar_cobro), pero sí dejaba que cualquiera disparara
    requests reales hacia la API de Mercado Pago (y ruido en los logs de
    error) mandando IDs inventados sin estar autenticado para nada. Esto es
    defensa en profundidad, no la única barrera."""

    def _firma(self, secreto, recurso_id, request_id, ts):
        import hashlib
        import hmac

        manifest = f"id:{recurso_id};request-id:{request_id};ts:{ts};"
        return hmac.new(secreto.encode(), manifest.encode(), hashlib.sha256).hexdigest()

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET="")
    def test_sin_secreto_configurado_sigue_funcionando_igual_que_hoy(self):
        """No romper producción -- la llave todavía no está configurada en
        Render. Mismo comportamiento de siempre: nunca se confía en el
        webhook de todas formas, el secreto es una capa extra, no la única."""
        with patch("pagos.views.obtener_pago_mercadopago", return_value=None):
            r = self.client.post(
                reverse("pago-webhook"),
                data=json.dumps({"type": "payment", "data": {"id": "pay-sin-secreto"}}),
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET="el-secreto-de-prueba")
    def test_firma_valida_deja_pasar(self):
        firma = self._firma("el-secreto-de-prueba", "pay-firma-ok", "req-1", "1700000000")
        with patch("pagos.views.obtener_pago_mercadopago", return_value=None):
            r = self.client.post(
                reverse("pago-webhook") + "?data.id=pay-firma-ok",
                data=json.dumps({"type": "payment", "data": {"id": "pay-firma-ok"}}),
                content_type="application/json",
                headers={"x-signature": f"ts=1700000000,v1={firma}", "x-request-id": "req-1"},
            )
        self.assertEqual(r.status_code, 200)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET="el-secreto-de-prueba")
    def test_firma_invalida_se_rechaza_sin_tocar_nada(self):
        with patch("pagos.views.obtener_pago_mercadopago") as mock_obtener:
            r = self.client.post(
                reverse("pago-webhook") + "?data.id=pay-firma-mala",
                data=json.dumps({"type": "payment", "data": {"id": "pay-firma-mala"}}),
                content_type="application/json",
                headers={"x-signature": "ts=1700000000,v1=firma-inventada", "x-request-id": "req-2"},
            )
        self.assertEqual(r.status_code, 403)
        mock_obtener.assert_not_called()

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET="el-secreto-de-prueba")
    def test_sin_header_de_firma_se_rechaza(self):
        with patch("pagos.views.obtener_pago_mercadopago") as mock_obtener:
            r = self.client.post(
                reverse("pago-webhook") + "?data.id=pay-sin-firma",
                data=json.dumps({"type": "payment", "data": {"id": "pay-sin-firma"}}),
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 403)
        mock_obtener.assert_not_called()


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

    @patch("pagos.admin.obtener_preapproval_mercadopago", return_value={"status": "pending", "init_point": "https://mp.test/autorizar/admin"})
    def test_accion_manda_recordatorio_a_una_donacion_pendiente(self, mock_obtener):
        """Independiente de la ventana automática de 24-48h (ver
        sincronizar_estado_suscripcion) -- para cuando devquad quiere
        mandar el empujón a mano, sin esperar al cron ni a que calce con
        esa ventana."""
        membresia = crear_membresia(self.condominio, "residente", username="admin_recordatorio", first_name="Tomás")
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=membresia, tipo="donacion", monto=2000,
            mercadopago_preapproval_id="pre-admin-recordatorio", estado="pendiente",
        )
        r = self.client.post("/admin/pagos/suscripcionrecurrente/", {
            "action": "enviar_recordatorio_donacion",
            "_selected_action": [str(suscripcion.pk)],
        }, follow=True)
        self.assertContains(r, "Se mandó el recordatorio")
        suscripcion.refresh_from_db()
        self.assertIsNotNone(suscripcion.recordatorio_enviado_en)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [membresia.user.email])
        self.assertIn("Tomás", mail.outbox[0].body)
        self.assertIn("https://mp.test/autorizar/admin", mail.outbox[0].alternatives[0][0])

    def test_accion_ignora_una_suscripcion_que_no_es_donacion(self):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, tipo="suscripcion", monto=19990,
            mercadopago_preapproval_id="pre-admin-recordatorio-susc", estado="pendiente",
        )
        r = self.client.post("/admin/pagos/suscripcionrecurrente/", {
            "action": "enviar_recordatorio_donacion",
            "_selected_action": [str(suscripcion.pk)],
        }, follow=True)
        self.assertContains(r, "se ignoraron")
        self.assertEqual(len(mail.outbox), 0)
        suscripcion.refresh_from_db()
        self.assertIsNone(suscripcion.recordatorio_enviado_en)

    def test_accion_ignora_una_donacion_que_no_esta_pendiente(self):
        membresia = crear_membresia(self.condominio, "residente", username="admin_recordatorio_autorizada")
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=membresia, tipo="donacion", monto=2000,
            mercadopago_preapproval_id="pre-admin-recordatorio-autorizada", estado="autorizada",
        )
        self.client.post("/admin/pagos/suscripcionrecurrente/", {
            "action": "enviar_recordatorio_donacion",
            "_selected_action": [str(suscripcion.pk)],
        })
        self.assertEqual(len(mail.outbox), 0)

    @patch("pagos.admin.obtener_preapproval_mercadopago", return_value=None)
    def test_accion_recordatorio_avisa_si_mercadopago_no_responde(self, mock_obtener):
        membresia = crear_membresia(self.condominio, "residente", username="admin_recordatorio_falla")
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=membresia, tipo="donacion", monto=2000,
            mercadopago_preapproval_id="pre-admin-recordatorio-falla", estado="pendiente",
        )
        r = self.client.post("/admin/pagos/suscripcionrecurrente/", {
            "action": "enviar_recordatorio_donacion",
            "_selected_action": [str(suscripcion.pk)],
        }, follow=True)
        self.assertContains(r, "No se pudo consultar la suscripción recurrente")
        self.assertEqual(len(mail.outbox), 0)
        suscripcion.refresh_from_db()
        self.assertIsNone(suscripcion.recordatorio_enviado_en)


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
    def test_rellena_el_pago_de_una_suscripcion_que_ya_estaba_autorizada_sin_pago(self, mock_obtener):
        """Caso real reportado: una suscripción sincronizada ANTES de este
        fix quedó "Autorizada" en SecurApp pero sin ningún Pago (el cobro
        real en Mercado Pago sí existe -- se vio en la pantalla "Pagaste
        $X"). Sincronizar de nuevo debe rellenar el Pago que falta, aunque
        el estado ya estaba "autorizada" antes de esta llamada."""
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(estado="autorizada")
        self.assertEqual(suscripcion.cobros.count(), 0)
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(suscripcion.cobros.count(), 1)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_no_duplica_el_pago_si_el_estado_ya_coincide_y_ya_tiene_pago(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(estado="autorizada")
        Pago.objects.create(
            condominio=self.condominio, suscripcion_recurrente=suscripcion, tipo="suscripcion",
            plan="premium", monto=suscripcion.monto, estado="aprobado", mercadopago_payment_id="ya-existente",
        )
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(suscripcion.cobros.count(), 1)

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
    def test_manda_un_correo_de_gracias_cuando_se_autoriza_una_donacion(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        condominio = Condominio.objects.create(nombre="Test Sync Donacion Correo", plan="basico")
        membresia = crear_membresia(condominio, "residente", username="gracias_donacion", first_name="Nora")
        suscripcion = self._suscripcion(
            condominio=condominio, tipo="donacion", membresia=membresia,
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-sync-don-correo",
        )
        suscripcion.refresh_from_db()  # monto llega con decimal_places=2 desde la base, igual que en producción
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [membresia.user.email])
        self.assertIn("Nora", mail.outbox[0].body)
        self.assertIn("Gracias", mail.outbox[0].subject)
        self.assertIn("$2000/mes", mail.outbox[0].body)
        self.assertIn("$2000/mes", mail.outbox[0].alternatives[0][0])

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_no_manda_correo_de_gracias_por_una_suscripcion_de_condominio(self, mock_obtener):
        """Solo donaciones (persona -> DevQuad) mandan el agradecimiento --
        la suscripcion SaaS (condominio -> DevQuad) no es una donación."""
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(tipo="suscripcion")
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(len(mail.outbox), 0)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_no_manda_correo_de_gracias_si_la_donacion_no_tiene_membresia(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(tipo="donacion", monto=Decimal("2000"))
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(len(mail.outbox), 0)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_no_repite_el_correo_si_ya_estaba_autorizada(self, mock_obtener):
        """Solo se manda en la TRANSICIÓN a autorizada, no cada vez que se
        sincroniza una donación que ya estaba autorizada de antes (ej. el
        cron periódico, que re-sincroniza todo lo no cancelado)."""
        from pagos.views import sincronizar_estado_suscripcion

        condominio = Condominio.objects.create(nombre="Test Sync Donacion Repite", plan="basico")
        membresia = crear_membresia(condominio, "residente", username="gracias_donacion_repite")
        suscripcion = self._suscripcion(
            condominio=condominio, tipo="donacion", membresia=membresia, estado="autorizada",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-sync-don-repite",
        )
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(len(mail.outbox), 0)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending", "init_point": "https://mp.test/autorizar/abc"})
    def test_una_donacion_pendiente_hace_mas_de_24_horas_manda_recordatorio(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        condominio = Condominio.objects.create(nombre="Test Recordatorio Donacion", plan="basico")
        membresia = crear_membresia(condominio, "residente", username="recordatorio_donacion", first_name="Rosa")
        suscripcion = self._suscripcion(
            condominio=condominio, tipo="donacion", membresia=membresia,
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-recordatorio",
        )
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=25),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        suscripcion.refresh_from_db()
        self.assertIsNotNone(suscripcion.recordatorio_enviado_en)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [membresia.user.email])
        self.assertIn("Rosa", mail.outbox[0].body)
        self.assertIn("https://mp.test/autorizar/abc", mail.outbox[0].alternatives[0][0])
        self.assertIn("$2000/mes", mail.outbox[0].body)
        self.assertIn("$2000/mes", mail.outbox[0].alternatives[0][0])

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending", "init_point": "https://mp.test/autorizar/abc"})
    def test_una_donacion_pendiente_hace_menos_de_24_horas_no_manda_recordatorio(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        condominio = Condominio.objects.create(nombre="Test Recordatorio Donacion Temprano", plan="basico")
        membresia = crear_membresia(condominio, "residente", username="recordatorio_donacion_temprano")
        suscripcion = self._suscripcion(
            condominio=condominio, tipo="donacion", membresia=membresia,
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-recordatorio-temprano",
        )
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=1),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(len(mail.outbox), 0)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending", "init_point": "https://mp.test/autorizar/abc"})
    def test_no_repite_el_recordatorio_si_ya_se_mando(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        condominio = Condominio.objects.create(nombre="Test Recordatorio Donacion Repetido", plan="basico")
        membresia = crear_membresia(condominio, "residente", username="recordatorio_donacion_repetido")
        suscripcion = self._suscripcion(
            condominio=condominio, tipo="donacion", membresia=membresia,
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-recordatorio-repetido",
        )
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=25),
            recordatorio_enviado_en=timezone.now() - datetime.timedelta(hours=1),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(len(mail.outbox), 0)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending", "init_point": "https://mp.test/autorizar/abc"})
    def test_no_manda_recordatorio_de_una_suscripcion_de_condominio(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(tipo="suscripcion")
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=25),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        self.assertEqual(len(mail.outbox), 0)

    @patch("pagos.views.cancelar_suscripcion_recurrente", return_value=True)
    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending"})
    def test_una_donacion_pendiente_hace_mas_de_48_horas_se_cancela_sola(self, mock_obtener, mock_cancelar):
        """Si nadie autorizó NI canceló explícitamente, Mercado Pago deja el
        preapproval en "pending" indefinidamente -- se da por abandonada y
        se cancela de verdad (no solo local, para no dejar un preapproval
        zombie que alguien autorice por sorpresa meses después)."""
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(tipo="donacion", monto=Decimal("2000"))
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=49),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "cancelada")
        self.assertIsNotNone(suscripcion.fecha_cancelacion)
        mock_cancelar.assert_called_once_with(suscripcion)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending"})
    def test_una_donacion_pendiente_hace_menos_de_48_horas_no_se_cancela(self, mock_obtener):
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(tipo="donacion", monto=Decimal("2000"))
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=1),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "pendiente")

    @patch("pagos.views.cancelar_suscripcion_recurrente", return_value=False)
    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending"})
    def test_si_mercadopago_no_confirma_la_cancelacion_sigue_pendiente(self, mock_obtener, mock_cancelar):
        """No se marca "cancelada" local si Mercado Pago no confirmó que
        de verdad se canceló -- dejaría el preapproval vivo del lado de
        Mercado Pago pero "cancelada" acá, mintiendo sobre el estado real."""
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(tipo="donacion", monto=Decimal("2000"))
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=49),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "pendiente")

    @patch("pagos.views.cancelar_suscripcion_recurrente", return_value=True)
    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "pending"})
    def test_una_suscripcion_de_condominio_pendiente_no_se_cancela_sola(self, mock_obtener, mock_cancelar):
        """El auto-vencimiento a las 48h es solo para donaciones -- una
        suscripción SaaS de condominio pendiente es una relación comercial
        real, no se cancela sola sin que nadie la revise."""
        from pagos.views import sincronizar_estado_suscripcion

        suscripcion = self._suscripcion(tipo="suscripcion")
        SuscripcionRecurrente.objects.filter(pk=suscripcion.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(hours=49),
        )
        suscripcion.refresh_from_db()
        sincronizar_estado_suscripcion(suscripcion)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "pendiente")
        mock_cancelar.assert_not_called()

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


class MisDonacionesViewTests(TestCase):
    """Cada miembro ve únicamente su propio historial de donaciones -- ni
    siquiera otros residentes del mismo condominio pueden verlo."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Mis Donaciones", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="misdon_residente")
        self.otro_residente = crear_membresia(self.condominio, "residente", username="misdon_otro")

    def test_sin_donacion_muestra_mensaje_vacio(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("mis-donaciones"))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["donacion_actual"])
        self.assertContains(r, "Activa una donación automática")

    def test_muestra_solo_las_propias(self):
        propia = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-propia", estado="autorizada",
        )
        Pago.objects.create(
            condominio=self.condominio, membresia=self.residente, suscripcion_recurrente=propia,
            tipo="donacion", monto=Decimal("2000"), estado="aprobado", mercadopago_payment_id="pay-propia",
        )
        ajena = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.otro_residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-ajena", estado="autorizada",
        )
        Pago.objects.create(
            condominio=self.condominio, membresia=self.otro_residente, suscripcion_recurrente=ajena,
            tipo="donacion", monto=Decimal("2000"), estado="aprobado", mercadopago_payment_id="pay-ajena",
        )

        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("mis-donaciones"))

        self.assertEqual(r.context["donacion_actual"], propia)
        self.assertEqual(list(r.context["pagos_donacion"]), [Pago.objects.get(mercadopago_payment_id="pay-propia")])
        self.assertEqual(r.context["total_donado"], Decimal("2000"))
        self.assertEqual(r.context["cantidad_aportes"], 1)

    def test_total_donado_no_cuenta_pagos_rechazados(self):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-rechazo", estado="autorizada",
        )
        Pago.objects.create(
            condominio=self.condominio, membresia=self.residente, suscripcion_recurrente=suscripcion,
            tipo="donacion", monto=Decimal("2000"), estado="aprobado", mercadopago_payment_id="pay-ok",
        )
        Pago.objects.create(
            condominio=self.condominio, membresia=self.residente, suscripcion_recurrente=suscripcion,
            tipo="donacion", monto=Decimal("2000"), estado="rechazado", mercadopago_payment_id="pay-mal",
        )

        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("mis-donaciones"))

        self.assertEqual(r.context["total_donado"], Decimal("2000"))
        self.assertEqual(r.context["cantidad_aportes"], 1)


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
class SincronizarSuscripcionesCommandTests(TestCase):
    """Comando sincronizar_suscripciones (pagos/management/commands/) --
    respaldo del webhook pensado para correr periódico (Render Cron Job)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Comando Sync", plan="premium")

    def _suscripcion(self, **kwargs):
        kwargs.setdefault("condominio", self.condominio)
        kwargs.setdefault("tipo", "suscripcion")
        kwargs.setdefault("monto", Decimal("19990"))
        kwargs.setdefault("estado", "pendiente")
        return SuscripcionRecurrente.objects.create(**kwargs)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value={"status": "authorized"})
    def test_sincroniza_todas_las_no_canceladas(self, mock_obtener):
        pendiente = self._suscripcion(mercadopago_preapproval_id="pre-cmd-1")
        pausada = self._suscripcion(mercadopago_preapproval_id="pre-cmd-2", estado="pausada")
        cancelada = self._suscripcion(mercadopago_preapproval_id="pre-cmd-3", estado="cancelada")

        call_command("sincronizar_suscripciones")

        pendiente.refresh_from_db()
        pausada.refresh_from_db()
        self.assertEqual(pendiente.estado, "autorizada")
        self.assertEqual(pausada.estado, "autorizada")
        mock_obtener.assert_any_call("pre-cmd-1")
        mock_obtener.assert_any_call("pre-cmd-2")
        self.assertNotIn(call("pre-cmd-3"), mock_obtener.call_args_list)

    @patch("pagos.views.obtener_preapproval_mercadopago", return_value=None)
    def test_informa_las_que_fallan_sin_frenar_el_resto(self, mock_obtener):
        self._suscripcion(mercadopago_preapproval_id="pre-cmd-falla")
        out = StringIO()
        call_command("sincronizar_suscripciones", stdout=out)
        self.assertIn("No se pudo consultar", out.getvalue())

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="")
    def test_no_hace_nada_sin_token_configurado(self):
        self._suscripcion(mercadopago_preapproval_id="pre-cmd-sin-token")
        out = StringIO()
        call_command("sincronizar_suscripciones", stdout=out)
        self.assertIn("no está configurado", out.getvalue())


class CancelarSuscripcionesCondominiosCommandTests(TestCase):
    """Comando cancelar_suscripciones_condominios -- parte del retiro del
    cobro de suscripción del condominio (ver memoria del proyecto). Nunca
    se ejecuta solo: dry-run por defecto, --aplicar para cancelar de verdad."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Cancelar Suscripciones", plan="premium")

    def _suscripcion(self, **kwargs):
        kwargs.setdefault("condominio", self.condominio)
        kwargs.setdefault("tipo", "suscripcion")
        kwargs.setdefault("monto", Decimal("19990"))
        kwargs.setdefault("estado", "autorizada")
        return SuscripcionRecurrente.objects.create(**kwargs)

    def test_sin_aplicar_no_llama_a_mercado_pago_ni_cambia_nada(self):
        suscripcion = self._suscripcion(mercadopago_preapproval_id="pre-cancel-dry")
        with patch("pagos.management.commands.cancelar_suscripciones_condominios.cancelar_suscripcion_recurrente") as mock_cancelar:
            out = StringIO()
            call_command("cancelar_suscripciones_condominios", stdout=out)
        mock_cancelar.assert_not_called()
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "autorizada")
        self.assertIn("Dry-run", out.getvalue())
        self.assertIn(self.condominio.nombre, out.getvalue())

    @patch("pagos.management.commands.cancelar_suscripciones_condominios.cancelar_suscripcion_recurrente", return_value=True)
    def test_aplicar_cancela_cada_suscripcion_de_condominio_activa(self, mock_cancelar):
        pendiente = self._suscripcion(mercadopago_preapproval_id="pre-cancel-1", estado="pendiente")
        autorizada = self._suscripcion(mercadopago_preapproval_id="pre-cancel-2", estado="autorizada")

        call_command("cancelar_suscripciones_condominios", "--aplicar")

        self.assertEqual(mock_cancelar.call_count, 2)
        pendiente.refresh_from_db()
        autorizada.refresh_from_db()
        self.assertEqual(pendiente.estado, "cancelada")
        self.assertEqual(autorizada.estado, "cancelada")
        self.assertIsNotNone(pendiente.fecha_cancelacion)

    @patch("pagos.management.commands.cancelar_suscripciones_condominios.cancelar_suscripcion_recurrente", return_value=False)
    def test_informa_las_que_fallan_sin_frenar_el_resto(self, mock_cancelar):
        self._suscripcion(mercadopago_preapproval_id="pre-cancel-falla")
        out = StringIO()
        call_command("cancelar_suscripciones_condominios", "--aplicar", stdout=out)
        self.assertIn("No se pudo cancelar", out.getvalue())

    def test_nunca_toca_donaciones(self):
        donacion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, tipo="donacion", monto=Decimal("2000"),
            mercadopago_preapproval_id="pre-cancel-donacion", estado="autorizada",
        )
        with patch("pagos.management.commands.cancelar_suscripciones_condominios.cancelar_suscripcion_recurrente") as mock_cancelar:
            call_command("cancelar_suscripciones_condominios", "--aplicar")
        mock_cancelar.assert_not_called()
        donacion.refresh_from_db()
        self.assertEqual(donacion.estado, "autorizada")

    def test_una_ya_cancelada_queda_excluida(self):
        self._suscripcion(mercadopago_preapproval_id="pre-cancel-ya", estado="cancelada")
        out = StringIO()
        call_command("cancelar_suscripciones_condominios", stdout=out)
        self.assertIn("No hay ninguna suscripción", out.getvalue())


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
class ApiDonacionesTests(TestCase):
    """3 endpoints nuevos bajo /api/v1/pagos/ para que la app móvil (JWT)
    pueda hacer lo mismo que DonarView/CancelarDonacionRecurrenteView/
    MisDonacionesView del panel web (sesión por cookie, no alcanzable
    desde la app) -- Tanda 4 de la Fase 2 de la app móvil."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Api Donaciones", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="api_don_residente")
        self.client.force_login(self.residente.user)

    def test_mi_donacion_sin_donacion_activa_devuelve_null(self):
        r = self.client.get(reverse("api-mi-donacion"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertIsNone(datos["donacion_actual"])
        self.assertEqual(datos["pagos"], [])
        self.assertEqual(datos["total_donado"], "0.00")
        self.assertEqual(datos["cantidad_aportes"], 0)

    def test_mi_donacion_con_donacion_activa_y_pagos(self):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-mi-don-1", estado="autorizada",
        )
        Pago.objects.create(
            condominio=self.condominio, membresia=self.residente, suscripcion_recurrente=suscripcion,
            tipo="donacion", monto=Decimal("2000"), estado="aprobado", mercadopago_payment_id="pay-1",
        )
        r = self.client.get(reverse("api-mi-donacion"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertEqual(datos["donacion_actual"]["estado"], "autorizada")
        self.assertEqual(datos["donacion_actual"]["monto"], "2000.00")
        self.assertEqual(len(datos["pagos"]), 1)
        self.assertEqual(datos["total_donado"], "2000.00")
        self.assertEqual(datos["cantidad_aportes"], 1)

    @patch("pagos.api_views.crear_suscripcion_recurrente", return_value="https://fake-mp.test/autorizar/1")
    def test_donar_crea_la_suscripcion_y_devuelve_la_url(self, mock_crear):
        r = self.client.post(reverse("api-donar"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["url_autorizacion"], "https://fake-mp.test/autorizar/1")
        suscripcion = SuscripcionRecurrente.objects.get(condominio=self.condominio, tipo="donacion")
        self.assertEqual(suscripcion.membresia_id, self.residente.pk)
        self.assertEqual(suscripcion.monto, Decimal("2000"))
        mock_crear.assert_called_once()

    def test_donar_sin_email_devuelve_400(self):
        self.residente.user.email = ""
        self.residente.user.save(update_fields=["email"])
        r = self.client.post(reverse("api-donar"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("Agrega tu email", r.json()["detail"])
        self.assertFalse(SuscripcionRecurrente.objects.exists())

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="")
    def test_donar_sin_access_token_configurada_devuelve_400(self):
        r = self.client.post(reverse("api-donar"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("todavía no está disponible", r.json()["detail"])

    @patch("pagos.api_views.crear_suscripcion_recurrente", return_value="https://fake-mp.test/autorizar/1")
    def test_donar_con_donacion_activa_devuelve_409(self, mock_crear):
        SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-ya-activa", estado="autorizada",
        )
        r = self.client.post(reverse("api-donar"))
        self.assertEqual(r.status_code, 409)
        self.assertIn("Ya tienes una donación automática activa", r.json()["detail"])
        mock_crear.assert_not_called()

    @patch("pagos.api_views.crear_suscripcion_recurrente", return_value=None)
    def test_donar_si_mercadopago_rechaza_no_deja_registro_huerfano(self, mock_crear):
        r = self.client.post(reverse("api-donar"))
        self.assertEqual(r.status_code, 502)
        self.assertFalse(SuscripcionRecurrente.objects.filter(condominio=self.condominio).exists())

    def test_devquad_sin_membresia_recibe_409_en_los_3_endpoints(self):
        devquad = User.objects.create_user(username="api_don_devquad", is_staff=True)
        self.client.logout()
        self.client.force_login(devquad)
        for r in (
            self.client.get(reverse("api-mi-donacion")),
            self.client.post(reverse("api-donar")),
            self.client.post(reverse("api-donar-cancelar")),
        ):
            self.assertEqual(r.status_code, 409)

    def test_cancelar_sin_donacion_activa_devuelve_404(self):
        r = self.client.post(reverse("api-donar-cancelar"))
        self.assertEqual(r.status_code, 404)

    @patch("pagos.api_views.cancelar_suscripcion_recurrente", return_value=True)
    def test_cancelar_una_donacion_activa_la_marca_cancelada(self, mock_cancelar):
        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-cancelar-api", estado="autorizada",
        )
        r = self.client.post(reverse("api-donar-cancelar"))
        self.assertEqual(r.status_code, 200)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, "cancelada")
        mock_cancelar.assert_called_once()

    @patch("pagos.api_views.cancelar_suscripcion_recurrente", return_value=False)
    def test_cancelar_si_mercadopago_rechaza_devuelve_400(self, mock_cancelar):
        SuscripcionRecurrente.objects.create(
            condominio=self.condominio, membresia=self.residente, tipo="donacion",
            monto=Decimal("2000"), mercadopago_preapproval_id="pre-cancelar-falla", estado="autorizada",
        )
        r = self.client.post(reverse("api-donar-cancelar"))
        self.assertEqual(r.status_code, 400)
