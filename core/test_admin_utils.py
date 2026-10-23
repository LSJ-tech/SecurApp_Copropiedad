from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Condominio, Torre, Unidad


NOMBRES_SOLO_LECTURA = ("listar-condominios", "buscar-borrados")
NOMBRES_QUE_MUTAN = ("probar-correo", "normalizar-nombres", "corregir-etiqueta-unidad-empart", "cargar-torres-empart", "agregar-departamentos-1-2-empart")


class AdminUtilsPermisosTests(TestCase):
    """Las 7 vistas de /admin-utils/ son @staff_member_required -- nadie más
    debería poder llegar, ni siquiera un usuario autenticado normal."""

    def setUp(self):
        self.staff = User.objects.create_user(username="util_staff", is_staff=True)
        self.normal = User.objects.create_user(username="util_normal")

    def test_anonimo_no_puede_entrar(self):
        for nombre in NOMBRES_SOLO_LECTURA:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
        for nombre in NOMBRES_QUE_MUTAN:
            r = self.client.post(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)

    def test_usuario_normal_no_puede_entrar(self):
        self.client.force_login(self.normal)
        for nombre in NOMBRES_SOLO_LECTURA:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
        for nombre in NOMBRES_QUE_MUTAN:
            r = self.client.post(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)

    def test_las_que_mutan_datos_rechazan_get_aunque_sea_staff(self):
        """Hallazgo de seguridad real: estas vistas cambian datos (o mandan
        un correo a quien sea) pero vivían detrás de un GET -- el middleware
        de CSRF de Django nunca revisa GET, así que bastaba con que un
        devquad logueado abriera un link/imagen armado por un atacante para
        disparar la acción sin que él lo pidiera (CSRF). Exigir POST las
        vuelve a dejar protegidas por el CSRF normal."""
        self.client.force_login(self.staff)
        for nombre in NOMBRES_QUE_MUTAN:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 405, nombre)


class ProbarCorreoTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="pc_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_destino_devuelve_400(self):
        r = self.client.post(reverse("probar-correo"))
        self.assertEqual(r.status_code, 400)

    def test_destino_invalido_devuelve_400(self):
        r = self.client.post(reverse("probar-correo"), {"destino": "no-es-un-correo"})
        self.assertEqual(r.status_code, 400)

    def test_destino_valido_manda_el_correo(self):
        from django.core import mail

        r = self.client.post(reverse("probar-correo"), {"destino": "prueba@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["prueba@example.com"])

    def test_rechaza_get_aunque_sea_staff(self):
        """Hallazgo de seguridad real: esta vista manda un correo a quien
        sea en ?destino= pero vivía detrás de un GET -- el middleware de
        CSRF de Django nunca revisa GET, así que un link/imagen armado por
        un atacante podía hacer que la plataforma le mandara spam a
        cualquier dirección, con la sesión de un devquad logueado."""
        r = self.client.get(reverse("probar-correo"), {"destino": "prueba@example.com"})
        self.assertEqual(r.status_code, 405)


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


class BuscarBorradosTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="bb_staff", is_staff=True)
        self.client.force_login(self.staff)

    def _crear_logentry_borrado(self, object_repr, model="membresia"):
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get(app_label="core", model=model)
        return LogEntry.objects.create(
            user=self.staff, content_type=content_type, object_id="1",
            object_repr=object_repr, action_flag=3, change_message="Borrado.",
        )

    def test_sin_borrados_devuelve_mensaje_claro(self):
        r = self.client.get(reverse("buscar-borrados"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Sin borrados registrados", r.content.decode())

    def test_lista_el_borrado_con_quien_y_que_modelo(self):
        self._crear_logentry_borrado("jlroman (Residente de Población Empart)")
        r = self.client.get(reverse("buscar-borrados"))
        contenido = r.content.decode()
        self.assertIn("jlroman", contenido)
        self.assertIn("modelo=membresia", contenido)
        self.assertIn("borrado_por=bb_staff", contenido)

    def test_filtra_por_q_y_no_mezcla_con_otros_borrados(self):
        self._crear_logentry_borrado("jlroman (Residente de Población Empart)")
        self._crear_logentry_borrado("Otra Persona (Residente de Población Empart)")
        r = self.client.get(reverse("buscar-borrados"), {"q": "roman"})
        contenido = r.content.decode()
        self.assertIn("jlroman", contenido)
        self.assertNotIn("Otra Persona", contenido)

    def test_q_sin_coincidencias_se_devuelve_escapado_no_crudo(self):
        r = self.client.get(reverse("buscar-borrados"), {"q": "<script>alert(1)</script>"})
        contenido = r.content.decode()
        self.assertNotIn("<script>", contenido)
        self.assertIn("&lt;script&gt;", contenido)

    def test_no_muestra_borrados_de_otro_tipo_de_accion(self):
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get(app_label="core", model="membresia")
        LogEntry.objects.create(
            user=self.staff, content_type=content_type, object_id="1",
            object_repr="No debería aparecer", action_flag=2, change_message="Editado, no borrado.",
        )
        r = self.client.get(reverse("buscar-borrados"))
        self.assertNotIn("No debería aparecer", r.content.decode())


class CorregirEtiquetaUnidadEmpartTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="ceue_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_condominio_empart_devuelve_404(self):
        r = self.client.post(reverse("corregir-etiqueta-unidad-empart"))
        self.assertEqual(r.status_code, 404)

    def test_mas_de_un_condominio_empart_devuelve_409(self):
        Condominio.objects.create(nombre="Condominio EMPART", plan="premium")
        Condominio.objects.create(nombre="Población EMPART", plan="premium")
        r = self.client.post(reverse("corregir-etiqueta-unidad-empart"))
        self.assertEqual(r.status_code, 409)

    def test_corrige_el_plural_a_singular(self):
        condominio = Condominio.objects.create(nombre="Población Empart", plan="premium", etiqueta_unidad="Departamentos")
        r = self.client.post(reverse("corregir-etiqueta-unidad-empart"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("'Departamentos' -> 'Departamento'", r.content.decode())
        condominio.refresh_from_db()
        self.assertEqual(condominio.etiqueta_unidad, "Departamento")

    def test_es_idempotente(self):
        Condominio.objects.create(nombre="Población Empart", plan="premium", etiqueta_unidad="Departamentos")
        self.client.post(reverse("corregir-etiqueta-unidad-empart"))
        r2 = self.client.post(reverse("corregir-etiqueta-unidad-empart"))
        self.assertIn("ya es 'Departamento', no se tocó nada", r2.content.decode())


class CargarTorresEmpartTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="cte_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_condominio_empart_devuelve_404(self):
        r = self.client.post(reverse("cargar-torres-empart"))
        self.assertEqual(r.status_code, 404)

    def test_mas_de_un_condominio_empart_devuelve_409(self):
        Condominio.objects.create(nombre="Condominio EMPART", plan="premium")
        Condominio.objects.create(nombre="Población EMPART", plan="premium")
        r = self.client.post(reverse("cargar-torres-empart"))
        self.assertEqual(r.status_code, 409)

    def test_crea_las_16_torres_y_320_unidades_y_es_idempotente(self):
        Condominio.objects.create(nombre="Población Empart", plan="premium")
        r = self.client.post(reverse("cargar-torres-empart"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Torres nuevas: 16", r.content.decode())
        self.assertEqual(Torre.objects.count(), 16)
        self.assertEqual(Unidad.objects.count(), 320)

        r2 = self.client.post(reverse("cargar-torres-empart"))
        self.assertIn("Torres nuevas: 0", r2.content.decode())
        self.assertEqual(Torre.objects.count(), 16)
        self.assertEqual(Unidad.objects.count(), 320)


class AgregarDepartamentos12EmpartTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="ad_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_sin_condominio_empart_devuelve_404(self):
        r = self.client.post(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 404)

    def test_mas_de_un_condominio_empart_devuelve_409(self):
        Condominio.objects.create(nombre="Condominio EMPART", plan="premium")
        Condominio.objects.create(nombre="Población EMPART", plan="premium")
        r = self.client.post(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 409)

    def test_sin_torres_todavia_devuelve_400(self):
        Condominio.objects.create(nombre="Población Empart", plan="premium")
        r = self.client.post(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 400)

    def test_agrega_1_y_2_a_cada_torre_y_es_idempotente(self):
        condominio = Condominio.objects.create(nombre="Población Empart", plan="premium")
        Torre.objects.create(condominio=condominio, nombre="1")
        Torre.objects.create(condominio=condominio, nombre="2")
        r = self.client.post(reverse("agregar-departamentos-1-2-empart"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Departamentos nuevos: 4", r.content.decode())
        self.assertEqual(Unidad.objects.filter(numero__in=["1", "2"]).count(), 4)

        r2 = self.client.post(reverse("agregar-departamentos-1-2-empart"))
        self.assertIn("Departamentos nuevos: 0", r2.content.decode())
        self.assertEqual(Unidad.objects.filter(numero__in=["1", "2"]).count(), 4)
