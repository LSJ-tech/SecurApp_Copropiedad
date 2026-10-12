from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia, Torre, Unidad

from .models import RegistroIngreso


def crear_membresia(condominio, rol, unidad=None, **user_kwargs):
    """Sin password: los tests se autentican con force_login."""
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(user=user, condominio=condominio, rol=rol, unidad=unidad, terminos_aceptados_en=timezone.now())


class RegistroIngresoPermisosTests(TestCase):
    """Accesos es exclusivo de directiva/administración/conserjería
    (EsDirectivaAdministracionOConserjeMixin) -- un residente no debe poder
    ver ni crear registros de ingreso."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Accesos", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="101")

    def setUp(self):
        self.conserje = crear_membresia(self.condominio, "conserje", username="acc_conserje")
        self.residente = crear_membresia(self.condominio, "residente", username="acc_residente")

    def test_conserje_puede_ver_la_lista(self):
        self.client.force_login(self.conserje.user)
        r = self.client.get(reverse("registro-ingreso-list"))
        self.assertEqual(r.status_code, 200)

    def test_residente_no_puede_ver_la_lista(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("registro-ingreso-list"))
        self.assertEqual(r.status_code, 302)

    def test_conserje_puede_registrar_un_ingreso(self):
        self.client.force_login(self.conserje.user)
        r = self.client.post(reverse("registro-ingreso-crear"), {
            "unidad": self.unidad.pk, "nombre_visitante": "Juan Pérez", "motivo": "visita",
        })
        self.assertEqual(r.status_code, 302)
        registro = RegistroIngreso.objects.get(unidad=self.unidad)
        self.assertEqual(registro.nombre_visitante, "Juan Pérez")
        self.assertEqual(registro.registrado_por, self.conserje)

    def test_residente_no_puede_registrar_un_ingreso(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("registro-ingreso-crear"), {
            "unidad": self.unidad.pk, "nombre_visitante": "Juan Pérez", "motivo": "visita",
        })
        self.assertEqual(r.status_code, 302)
        self.assertFalse(RegistroIngreso.objects.filter(unidad=self.unidad).exists())

    def test_el_formulario_solo_ofrece_unidades_del_propio_condominio(self):
        otro_condominio = Condominio.objects.create(nombre="Otro Condominio Accesos", plan="premium")
        unidad_ajena = Unidad.objects.create(condominio=otro_condominio, numero="999")
        self.client.force_login(self.conserje.user)
        r = self.client.get(reverse("registro-ingreso-crear"))
        self.assertEqual(r.status_code, 200)
        opciones = list(r.context["form"].fields["unidad"].queryset)
        self.assertIn(self.unidad, opciones)
        self.assertNotIn(unidad_ajena, opciones)

    def test_conserje_puede_registrar_la_salida(self):
        registro = RegistroIngreso.objects.create(unidad=self.unidad, nombre_visitante="Ana Soto", registrado_por=self.conserje)
        self.client.force_login(self.conserje.user)
        r = self.client.post(reverse("registro-ingreso-salida", args=[registro.pk]))
        self.assertEqual(r.status_code, 302)
        registro.refresh_from_db()
        self.assertIsNotNone(registro.fecha_salida)

    def test_residente_no_puede_registrar_la_salida(self):
        registro = RegistroIngreso.objects.create(unidad=self.unidad, nombre_visitante="Ana Soto", registrado_por=self.conserje)
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("registro-ingreso-salida", args=[registro.pk]))
        self.assertEqual(r.status_code, 302)
        registro.refresh_from_db()
        self.assertIsNone(registro.fecha_salida)

    def test_no_puede_registrar_salida_de_un_registro_de_otro_condominio(self):
        otro_condominio = Condominio.objects.create(nombre="Otro Condominio Salida", plan="premium")
        unidad_ajena = Unidad.objects.create(condominio=otro_condominio, numero="1")
        conserje_ajeno = crear_membresia(otro_condominio, "conserje", username="acc_conserje_ajeno")
        registro_ajeno = RegistroIngreso.objects.create(unidad=unidad_ajena, nombre_visitante="Externo", registrado_por=conserje_ajeno)
        self.client.force_login(self.conserje.user)
        r = self.client.post(reverse("registro-ingreso-salida", args=[registro_ajeno.pk]))
        self.assertEqual(r.status_code, 404)

    def test_str_del_registro(self):
        registro = RegistroIngreso.objects.create(unidad=self.unidad, nombre_visitante="Ana Soto", registrado_por=self.conserje)
        self.assertIn("Ana Soto", str(registro))


class RegistroIngresoFormOrdenTests(TestCase):
    """El queryset de unidades del form se ordena numéricamente por torre
    (mismo truco de Length() que TorreListView/UnidadForm), no alfabético."""

    def test_torres_se_ordenan_numericamente_no_alfabeticamente(self):
        condominio = Condominio.objects.create(nombre="Test Orden Accesos", plan="premium")
        torre_2 = Torre.objects.create(condominio=condominio, nombre="2")
        torre_10 = Torre.objects.create(condominio=condominio, nombre="10")
        unidad_10 = Unidad.objects.create(condominio=condominio, torre=torre_10, numero="1")
        unidad_2 = Unidad.objects.create(condominio=condominio, torre=torre_2, numero="1")

        from .forms import RegistroIngresoForm
        form = RegistroIngresoForm(condominio=condominio)
        self.assertEqual(list(form.fields["unidad"].queryset), [unidad_2, unidad_10])


class RegistroIngresoAdminTests(TestCase):
    """Filtro de condominio (vía unidad__condominio) como desplegable con
    buscador -- confirma que el changelist sigue renderizando bien."""

    def test_changelist_renderiza_ok(self):
        condominio = Condominio.objects.create(nombre="Test Admin Acceso", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        RegistroIngreso.objects.create(unidad=unidad, nombre_visitante="Juan Pérez", motivo="visita")
        staff = User.objects.create_superuser(username="admin_acceso_staff", password="x", email="admin_acceso_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/accesos/registroingreso/")
        self.assertEqual(r.status_code, 200)
