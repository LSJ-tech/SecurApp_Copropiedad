from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Condominio, Torre, Unidad


class AdminUtilsPermisosTests(TestCase):
    """Las 4 vistas de /admin-utils/ son @staff_member_required -- nadie más
    debería poder llegar, ni siquiera un usuario autenticado normal."""

    def setUp(self):
        self.staff = User.objects.create_user(username="util_staff", is_staff=True)
        self.normal = User.objects.create_user(username="util_normal")

    def test_anonimo_no_puede_entrar(self):
        for nombre in ("probar-correo", "listar-condominios", "cargar-torres-empart", "agregar-departamentos-1-2-empart"):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)

    def test_usuario_normal_no_puede_entrar(self):
        self.client.force_login(self.normal)
        for nombre in ("probar-correo", "listar-condominios", "cargar-torres-empart", "agregar-departamentos-1-2-empart"):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)


class ProbarCorreoTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="pc_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_destino_devuelve_400(self):
        r = self.client.get(reverse("probar-correo"))
        self.assertEqual(r.status_code, 400)

    def test_destino_invalido_devuelve_400(self):
        r = self.client.get(reverse("probar-correo"), {"destino": "no-es-un-correo"})
        self.assertEqual(r.status_code, 400)

    def test_destino_valido_manda_el_correo(self):
        from django.core import mail

        r = self.client.get(reverse("probar-correo"), {"destino": "prueba@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["prueba@example.com"])


class ListarCondominiosTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="lc_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_condominios(self):
        r = self.client.get(reverse("listar-condominios"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("No hay condominios", r.content.decode())

    def test_lista_condominios_con_sus_conteos(self):
        condominio = Condominio.objects.create(nombre="Test Listar", plan="premium")
        torre = Torre.objects.create(condominio=condominio, nombre="1")
        Unidad.objects.create(condominio=condominio, torre=torre, numero="101")
        r = self.client.get(reverse("listar-condominios"))
        contenido = r.content.decode()
        self.assertIn("Test Listar", contenido)
        self.assertIn("torres=1", contenido)
        self.assertIn("unidades=1", contenido)


class CargarTorresEmpartTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="cte_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_condominio_empart_devuelve_404(self):
        r = self.client.get(reverse("cargar-torres-empart"))
        self.assertEqual(r.status_code, 404)

    def test_mas_de_un_condominio_empart_devuelve_409(self):
        Condominio.objects.create(nombre="Condominio EMPART", plan="premium")
        Condominio.objects.create(nombre="Población EMPART", plan="premium")
        r = self.client.get(reverse("cargar-torres-empart"))
        self.assertEqual(r.status_code, 409)

    def test_crea_las_16_torres_y_320_unidades_y_es_idempotente(self):
        Condominio.objects.create(nombre="Población Empart", plan="premium")
        r = self.client.get(reverse("cargar-torres-empart"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Torres nuevas: 16", r.content.decode())
        self.assertEqual(Torre.objects.count(), 16)
        self.assertEqual(Unidad.objects.count(), 320)

        r2 = self.client.get(reverse("cargar-torres-empart"))
        self.assertIn("Torres nuevas: 0", r2.content.decode())
        self.assertEqual(Torre.objects.count(), 16)
        self.assertEqual(Unidad.objects.count(), 320)


class AgregarDepartamentos12EmpartTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="ad_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_condominio_empart_devuelve_404(self):
        r = self.client.get(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 404)

    def test_mas_de_un_condominio_empart_devuelve_409(self):
        Condominio.objects.create(nombre="Condominio EMPART", plan="premium")
        Condominio.objects.create(nombre="Población EMPART", plan="premium")
        r = self.client.get(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 409)

    def test_sin_torres_todavia_devuelve_400(self):
        Condominio.objects.create(nombre="Población Empart", plan="premium")
        r = self.client.get(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 400)

    def test_agrega_1_y_2_a_cada_torre_y_es_idempotente(self):
        condominio = Condominio.objects.create(nombre="Población Empart", plan="premium")
        Torre.objects.create(condominio=condominio, nombre="1")
        Torre.objects.create(condominio=condominio, nombre="2")
        r = self.client.get(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Departamentos nuevos: 4", r.content.decode())
        self.assertEqual(Unidad.objects.filter(numero__in=["1", "2"]).count(), 4)

        r2 = self.client.get(reverse("agregar-departamentos-1-2-empart"))
        self.assertIn("Departamentos nuevos: 0", r2.content.decode())
        self.assertEqual(Unidad.objects.filter(numero__in=["1", "2"]).count(), 4)
