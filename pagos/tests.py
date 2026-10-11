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

from .mercadopago_client import crear_preferencia_pago, obtener_pago_mercadopago
from .models import Pago


def crear_membresia(condominio, rol, unidad=None, **user_kwargs):
    """Sin password: los tests se autentican con force_login."""
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(
        user=user, condominio=condominio, rol=rol, unidad=unidad, terminos_aceptados_en=timezone.now(),
    )


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
class DonarViewTests(TestCase):
    """Cualquier miembro puede donar (commit 6e4a108) -- sin tocar la red real
    de Mercado Pago, se mockea crear_preferencia_pago."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Donar", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="5")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="502")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="don_residente")
        self.client.force_login(self.residente.user)

    @patch("pagos.views.crear_preferencia_pago", return_value="https://fake-mp.test/pagar/1")
    def test_residente_puede_donar(self, mock_pref):
        r = self.client.post(reverse("donar"), {"monto": "3000"})
        self.assertEqual(r.status_code, 302)
        pago = Pago.objects.get(condominio=self.condominio, tipo="donacion")
        self.assertEqual(pago.membresia_id, self.residente.pk)
        self.assertEqual(pago.monto, Decimal("3000"))
        self.assertEqual(pago.plan, "")

    def test_monto_invalido_no_crea_pago(self):
        r = self.client.post(reverse("donar"), {"monto": "no-es-numero"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Pago.objects.filter(condominio=self.condominio).exists())

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="")
    def test_sin_token_configurado_no_crea_pago(self):
        r = self.client.post(reverse("donar"), {"monto": "3000"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Pago.objects.filter(condominio=self.condominio).exists())

    def test_usuario_sin_membresia_no_puede_donar(self):
        sin_membresia = User.objects.create_user(username="sin_membresia")
        self.client.logout()
        self.client.force_login(sin_membresia)
        r = self.client.post(reverse("donar"), {"monto": "3000"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Pago.objects.exists())


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
class SuscripcionPagarViewTests(TestCase):
    """Solo directiva/administración pagan la suscripción (monto fijo, no lo
    elige quien paga), y se bloquea si el mes ya está pagado -- para no
    duplicar el cobro."""

    @classmethod
    def setUpTestData(cls):
        # pagado_hasta=None a propósito -- Condominio ahora trae 20 días de
        # prueba gratis por defecto (ver _pagado_hasta_prueba_gratis), pero
        # estos tests quieren probar el caso de "todavía no está pagado".
        cls.condominio = Condominio.objects.create(nombre="Test Suscripcion", plan="premium", pagado_hasta=None)

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="susc_admon")
        self.directiva = crear_membresia(self.condominio, "directiva", username="susc_directiva")
        self.residente = crear_membresia(self.condominio, "residente", username="susc_residente")

    @patch("pagos.views.crear_preferencia_pago", return_value="https://fake-mp.test/pagar/1")
    def test_administracion_puede_pagar_la_suscripcion(self, mock_pref):
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        pago = Pago.objects.get(condominio=self.condominio, tipo="suscripcion")
        self.assertEqual(pago.monto, Decimal("19990"))
        self.assertEqual(pago.plan, "premium")
        self.assertEqual(pago.membresia_id, self.administracion.pk)

    @patch("pagos.views.crear_preferencia_pago", return_value="https://fake-mp.test/pagar/1")
    def test_directiva_tambien_puede_pagar(self, mock_pref):
        self.client.force_login(self.directiva.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Pago.objects.filter(condominio=self.condominio, tipo="suscripcion").exists())

    def test_residente_no_puede_pagar_la_suscripcion(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Pago.objects.filter(condominio=self.condominio, tipo="suscripcion").exists())

    def test_no_deja_pagar_de_nuevo_si_el_mes_ya_esta_pagado(self):
        self.condominio.pagado_hasta = timezone.localdate() + datetime.timedelta(days=10)
        self.condominio.save(update_fields=["pagado_hasta"])
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Pago.objects.filter(condominio=self.condominio, tipo="suscripcion").exists())

    @patch("pagos.views.crear_preferencia_pago", return_value="https://fake-mp.test/pagar/1")
    def test_si_la_suscripcion_vencida_si_deja_pagar_de_nuevo(self, mock_pref):
        self.condominio.pagado_hasta = timezone.localdate() - datetime.timedelta(days=1)
        self.condominio.save(update_fields=["pagado_hasta"])
        self.client.force_login(self.administracion.user)
        r = self.client.post(reverse("pagar-suscripcion"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Pago.objects.filter(condominio=self.condominio, tipo="suscripcion").exists())


class WebhookMercadoPagoTests(TestCase):
    """La donación aprobada NO debe tocar pagado_hasta/plan del condominio --
    eso es exclusivo de un pago de tipo 'suscripcion' (commit c8c030c)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Webhook", plan="free", pagado_hasta=None)

    def _simular_webhook(self, pago, estado_mp="approved"):
        with patch(
            "pagos.views.obtener_pago_mercadopago",
            return_value={"status": estado_mp, "external_reference": str(pago.pk)},
        ):
            return self.client.post(
                reverse("pago-webhook"), data=json.dumps({"data": {"id": "999"}}), content_type="application/json",
            )

    def test_donacion_aprobada_no_extiende_plan_ni_vencimiento(self):
        pago = Pago.objects.create(condominio=self.condominio, tipo="donacion", monto=Decimal("5000"))
        self._simular_webhook(pago)
        pago.refresh_from_db()
        self.condominio.refresh_from_db()
        self.assertEqual(pago.estado, "aprobado")
        self.assertIsNone(self.condominio.pagado_hasta)
        self.assertEqual(self.condominio.plan, "free")

    def test_suscripcion_aprobada_si_extiende_plan_y_vencimiento(self):
        pago = Pago.objects.create(condominio=self.condominio, tipo="suscripcion", monto=Decimal("9990"), plan="premium")
        self._simular_webhook(pago)
        pago.refresh_from_db()
        self.condominio.refresh_from_db()
        self.assertEqual(pago.estado, "aprobado")
        self.assertIsNotNone(self.condominio.pagado_hasta)
        self.assertEqual(self.condominio.plan, "premium")

    def test_pago_rechazado_queda_marcado(self):
        pago = Pago.objects.create(condominio=self.condominio, tipo="donacion", monto=Decimal("1000"))
        self._simular_webhook(pago, estado_mp="rejected")
        pago.refresh_from_db()
        self.assertEqual(pago.estado, "rechazado")


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
class MercadoPagoClientTests(TestCase):
    """Tests directos de pagos/mercadopago_client.py -- el resto de los
    tests de esta app mockean crear_preferencia_pago/obtener_pago_mercadopago
    a nivel de vista a propósito (sin tocar la red real de Mercado Pago), así
    que este módulo (el único que arma la preferencia de verdad) se quedaba
    sin ningún test propio."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test MP Client", plan="premium")

    def _request(self):
        return RequestFactory().get("/")

    def _pago(self, **kwargs):
        kwargs.setdefault("condominio", self.condominio)
        kwargs.setdefault("tipo", "donacion")
        kwargs.setdefault("monto", Decimal("5000"))
        return Pago.objects.create(**kwargs)

    @patch("pagos.mercadopago_client._sdk")
    def test_donacion_sin_unidad_usa_nombre_del_condominio_como_origen(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = MPResponse(
            {"status": 201, "response": {"id": "pref-1", "init_point": "https://fake-mp.test/pagar/1"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        pago = self._pago()
        url = crear_preferencia_pago(pago, self._request())
        self.assertEqual(url, "https://fake-mp.test/pagar/1")
        titulo = mock_sdk.preference.return_value.create.call_args[0][0]["items"][0]["title"]
        self.assertIn(self.condominio.nombre, titulo)
        pago.refresh_from_db()
        self.assertEqual(pago.mercadopago_preference_id, "pref-1")

    @patch("pagos.mercadopago_client._sdk")
    def test_donacion_con_torre_arma_origen_con_torre_y_depto(self, mock_sdk_factory):
        torre = Torre.objects.create(condominio=self.condominio, nombre="3")
        unidad = Unidad.objects.create(condominio=self.condominio, torre=torre, numero="301")
        membresia = crear_membresia(self.condominio, "residente", unidad=unidad, username="mp_con_torre")
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = MPResponse(
            {"status": 201, "response": {"id": "pref-2", "init_point": "https://fake-mp.test/pagar/2"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        pago = self._pago(membresia=membresia)
        crear_preferencia_pago(pago, self._request())
        titulo = mock_sdk.preference.return_value.create.call_args[0][0]["items"][0]["title"]
        self.assertIn("Torre 3", titulo)
        self.assertIn("Depto 301", titulo)

    @patch("pagos.mercadopago_client._sdk")
    def test_donacion_sin_torre_arma_origen_solo_con_depto(self, mock_sdk_factory):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="99")
        membresia = crear_membresia(self.condominio, "residente", unidad=unidad, username="mp_sin_torre")
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = MPResponse(
            {"status": 201, "response": {"id": "pref-3", "init_point": "https://fake-mp.test/pagar/3"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        pago = self._pago(membresia=membresia)
        crear_preferencia_pago(pago, self._request())
        titulo = mock_sdk.preference.return_value.create.call_args[0][0]["items"][0]["title"]
        self.assertIn("Depto 99", titulo)
        self.assertNotIn("Torre", titulo)

    @patch("pagos.mercadopago_client._sdk")
    def test_suscripcion_usa_titulo_distinto_al_de_donacion(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = MPResponse(
            {"status": 201, "response": {"id": "pref-4", "init_point": "https://fake-mp.test/pagar/4"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        pago = self._pago(tipo="suscripcion", monto=Decimal("19990"), plan="premium")
        crear_preferencia_pago(pago, self._request())
        titulo = mock_sdk.preference.return_value.create.call_args[0][0]["items"][0]["title"]
        self.assertIn("Suscripción", titulo)
        self.assertNotIn("Donación", titulo)

    @patch("pagos.mercadopago_client._sdk")
    def test_mercadopago_rechaza_la_preferencia_devuelve_none(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = MPResponse(
            {"status": 400, "response": {"message": "bad request"}}
        )
        mock_sdk_factory.return_value = mock_sdk
        pago = self._pago()
        url = crear_preferencia_pago(pago, self._request())
        self.assertIsNone(url)
        pago.refresh_from_db()
        self.assertEqual(pago.mercadopago_preference_id, "")

    @patch("pagos.mercadopago_client._sdk")
    def test_credencial_de_prueba_usa_sandbox_init_point(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = MPResponse({
            "status": 201,
            "response": {
                "id": "pref-5",
                "init_point": "https://fake-mp.test/prod",
                "sandbox_init_point": "https://fake-mp.test/sandbox",
            },
        })
        mock_sdk_factory.return_value = mock_sdk
        pago = self._pago()
        url = crear_preferencia_pago(pago, self._request())
        self.assertEqual(url, "https://fake-mp.test/sandbox")

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="APP_USR-prod-token")
    @patch("pagos.mercadopago_client._sdk")
    def test_credencial_de_produccion_usa_init_point_aunque_haya_sandbox(self, mock_sdk_factory):
        mock_sdk = MagicMock()
        mock_sdk.preference.return_value.create.return_value = MPResponse({
            "status": 201,
            "response": {
                "id": "pref-6",
                "init_point": "https://fake-mp.test/prod",
                "sandbox_init_point": "https://fake-mp.test/sandbox",
            },
        })
        mock_sdk_factory.return_value = mock_sdk
        pago = self._pago()
        url = crear_preferencia_pago(pago, self._request())
        self.assertEqual(url, "https://fake-mp.test/prod")

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


class DonarViewRamasFaltantesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Donar Ramas", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="donar_ramas_residente")
        self.client.force_login(self.residente.user)

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
    @patch("pagos.views.crear_preferencia_pago", return_value=None)
    def test_mercadopago_no_devuelve_url_no_crea_preferencia_utilizable(self, mock_pref):
        r = self.client.post(reverse("donar"), {"monto": "3000"}, follow=True)
        self.assertContains(r, "No pudimos iniciar la donación")
        self.assertEqual(Pago.objects.filter(condominio=self.condominio).count(), 1)


class SuscripcionPagarViewRamasFaltantesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Suscripcion Ramas", plan="premium", pagado_hasta=None)

    def test_sin_membresia_redirige_a_login(self):
        user = User.objects.create_user(username="susc_sin_membresia")
        self.client.force_login(user)
        r = self.client.post(reverse("pagar-suscripcion"), follow=True)
        self.assertContains(r, "no está vinculada a ningún condominio")

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="")
    def test_sin_token_configurado_no_crea_pago(self):
        administracion = crear_membresia(self.condominio, "administracion", username="susc_sin_token")
        self.client.force_login(administracion.user)
        r = self.client.post(reverse("pagar-suscripcion"), follow=True)
        self.assertContains(r, "todavía no está disponible")
        self.assertFalse(Pago.objects.filter(condominio=self.condominio).exists())

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-fake-token")
    @patch("pagos.views.crear_preferencia_pago", return_value=None)
    def test_mercadopago_no_devuelve_url_no_bloquea_reintentar(self, mock_pref):
        administracion = crear_membresia(self.condominio, "administracion", username="susc_sin_url")
        self.client.force_login(administracion.user)
        r = self.client.post(reverse("pagar-suscripcion"), follow=True)
        self.assertContains(r, "No pudimos iniciar el pago")


class PagoResultadoViewTests(TestCase):
    def test_muestra_el_estado_que_viene_en_la_url(self):
        condominio = Condominio.objects.create(nombre="Test Pago Resultado", plan="premium")
        membresia = crear_membresia(condominio, "residente", username="resultado_residente")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("pago-resultado") + "?status=approved")
        self.assertEqual(r.context["estado"], "approved")


class WebhookMercadoPagoRamasFaltantesTests(TestCase):
    """Las ramas de salida temprana del webhook -- nunca se confía en el
    cuerpo del POST, así que cualquiera de estos casos debe responder 200/400
    sin tocar ningún Pago."""

    def test_body_invalido_devuelve_400(self):
        r = self.client.post(reverse("pago-webhook"), data="esto no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_sin_payment_id_devuelve_200_sin_hacer_nada(self):
        r = self.client.post(reverse("pago-webhook"), data=json.dumps({"data": {}}), content_type="application/json")
        self.assertEqual(r.status_code, 200)

    @patch("pagos.views.obtener_pago_mercadopago", return_value=None)
    def test_mercadopago_no_devuelve_el_pago_devuelve_200(self, mock_obtener):
        r = self.client.post(reverse("pago-webhook"), data=json.dumps({"data": {"id": "999"}}), content_type="application/json")
        self.assertEqual(r.status_code, 200)

    @patch("pagos.views.obtener_pago_mercadopago", return_value={"status": "approved", "external_reference": "99999"})
    def test_pago_inexistente_devuelve_200(self, mock_obtener):
        r = self.client.post(reverse("pago-webhook"), data=json.dumps({"data": {"id": "999"}}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
