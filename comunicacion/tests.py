from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia

from .models import Aviso


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
