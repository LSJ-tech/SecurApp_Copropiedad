import re

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import CrearCondominioForm, CrearMiembroForm, RegistroResidenteForm
from .models import Condominio, Membresia, Torre, Unidad
from .views import EMAIL_CONTACTO_DEVQUAD


def crear_membresia(condominio, rol, unidad=None, terminos=True, **user_kwargs):
    """Sin password: los tests se autentican con force_login (no valida
    contraseña, no hay nada que hashear) -- ninguno de estos tests prueba el
    mecanismo de login en sí, solo qué puede ver cada rol una vez adentro."""
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(
        user=user, condominio=condominio, rol=rol, unidad=unidad,
        terminos_aceptados_en=timezone.now() if terminos else None,
    )


class RolesPermisosTests(TestCase):
    """Cada rol debe poder llegar solo a lo que le corresponde -- ver los
    mixins en core/mixins.py. Esto cubre el día a día (miembros/torres/
    unidades/accesos/mi condominio -- exclusivo de devquad, ver
    SoloStaffMixin) y la creación de miembros (CrearMiembroForm)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Roles", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="101")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="roles_residente")
        self.delegado = crear_membresia(self.condominio, "delegado", unidad=self.unidad, username="roles_delegado")

    def _login_devquad(self):
        devquad = crear_devquad(f"roles_devquad_{Membresia.objects.count()}")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_dia_a_dia_devquad_permitido(self):
        self._login_devquad()
        for url_name in ("miembros", "torres", "unidades"):
            r = self.client.get(reverse(url_name))
            self.assertEqual(r.status_code, 200, f"devquad debería poder ver {url_name}")

    def test_dia_a_dia_bloqueado_para_residente_y_delegado(self):
        for membresia in (self.residente, self.delegado):
            self.client.force_login(membresia.user)
            for url_name in ("miembros", "torres", "unidades"):
                r = self.client.get(reverse(url_name))
                self.assertEqual(r.status_code, 302, f"{membresia.rol} NO debería poder ver {url_name}")
            self.client.logout()

    def test_mi_condominio_exclusivo_devquad(self):
        self._login_devquad()
        self.assertEqual(self.client.get(reverse("mi-condominio")).status_code, 200)
        self.client.logout()
        self.client.force_login(self.residente.user)
        self.assertEqual(self.client.get(reverse("mi-condominio")).status_code, 302)

    def test_crear_miembro_form_siempre_ofrece_solo_residente_y_delegado(self):
        """Devquad nunca puede crearse a sí mismo (ni a otro devquad) desde
        este formulario -- esa cuenta es User.is_staff, se da de alta fuera
        del panel. No depende de quién crea: a diferencia del viejo
        CrearMiembroForm (creador_rol), ahora las opciones son fijas."""
        form = CrearMiembroForm(condominio=self.condominio)
        self.assertEqual([c[0] for c in form.fields["rol"].choices], ["residente", "delegado"])

    def test_crear_miembro_residente_exige_unidad(self):
        form = CrearMiembroForm(
            data={"nombre": "Ana", "apellido": "Soto", "email": "ana@example.com", "rol": "residente"},
            condominio=self.condominio,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Selecciona la unidad", str(form.errors))

    def test_crear_miembro_delegado_exige_unidad(self):
        form = CrearMiembroForm(
            data={"nombre": "Ana", "apellido": "Soto", "email": "ana2@example.com", "rol": "delegado"},
            condominio=self.condominio,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Selecciona la unidad", str(form.errors))



class MembresiaValidacionTests(TestCase):
    """Membresia.clean() -- unidad obligatoria para residente, y debe ser del
    mismo condominio que la membresía (regla agregada tras el commit 1f88c69)."""

    @classmethod
    def setUpTestData(cls):
        cls.cond1 = Condominio.objects.create(nombre="Cond 1", plan="premium")
        cls.cond2 = Condominio.objects.create(nombre="Cond 2", plan="premium")
        cls.unidad_cond1 = Unidad.objects.create(condominio=cls.cond1, numero="1")
        cls.unidad_cond2 = Unidad.objects.create(condominio=cls.cond2, numero="99")

    def test_residente_sin_unidad_es_invalido(self):
        user = User.objects.create(username="sin_unidad")
        m = Membresia(user=user, condominio=self.cond1, rol="residente", unidad=None)
        with self.assertRaises(ValidationError):
            m.full_clean()

    def test_residente_con_unidad_de_otro_condominio_es_invalido(self):
        user = User.objects.create(username="unidad_cruzada")
        m = Membresia(user=user, condominio=self.cond1, rol="residente", unidad=self.unidad_cond2)
        with self.assertRaises(ValidationError):
            m.full_clean()

    def test_residente_con_unidad_correcta_es_valido(self):
        user = User.objects.create(username="residente_ok")
        m = Membresia(user=user, condominio=self.cond1, rol="residente", unidad=self.unidad_cond1)
        m.full_clean()  # no debe lanzar

    def test_delegado_sin_unidad_es_invalido(self):
        user = User.objects.create(username="delegado_sin_unidad")
        m = Membresia(user=user, condominio=self.cond1, rol="delegado", unidad=None)
        with self.assertRaises(ValidationError):
            m.full_clean()

    def test_delegado_con_unidad_correcta_es_valido(self):
        user = User.objects.create(username="delegado_ok")
        m = Membresia(user=user, condominio=self.cond1, rol="delegado", unidad=self.unidad_cond1)
        m.full_clean()  # no debe lanzar


class TerminosAceptacionTests(TestCase):
    """El gate de Términos de Uso / Política de Privacidad: nadie debería
    poder usar una página protegida sin haber aceptado, pero tampoco debería
    quedar atrapado sin poder cerrar sesión (commit b58ea4e)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Terminos", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", terminos=False, username="pendiente_terminos")
        self.client.force_login(self.membresia.user)

    def test_inicio_redirige_a_aceptar_terminos(self):
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("aceptar-terminos"))

    def test_cualquier_pagina_protegida_redirige_a_aceptar_terminos(self):
        r = self.client.get(reverse("mi-perfil"))
        self.assertRedirects(r, reverse("aceptar-terminos"))

    def test_pantalla_aceptar_terminos_no_hace_loop(self):
        r = self.client.get(reverse("aceptar-terminos"))
        self.assertEqual(r.status_code, 200)

    def test_logout_funciona_con_terminos_pendientes(self):
        r = self.client.post(reverse("logout"))
        self.assertEqual(r.status_code, 302)

    def test_aceptar_terminos_desbloquea_el_resto(self):
        self.client.post(reverse("aceptar-terminos"), {"acepto": "on"})
        self.membresia.refresh_from_db()
        self.assertIsNotNone(self.membresia.terminos_aceptados_en)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)

    def test_aceptar_terminos_sin_marcar_checkbox_no_avanza(self):
        r = self.client.post(reverse("aceptar-terminos"), {})
        self.membresia.refresh_from_db()
        self.assertIsNone(self.membresia.terminos_aceptados_en)
        self.assertRedirects(r, reverse("aceptar-terminos"))


class ConsentimientoRegistroTests(TestCase):
    """Los dos registros públicos exigen el checkbox de Términos/Privacidad
    (commit b58ea4e)."""

    def test_registro_residente_exige_checkbox(self):
        condominio = Condominio.objects.create(nombre="Test Registro Residente", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        datos = {
            "nombre": "Rosa", "apellido": "Mena", "email": "rosa@example.com", "unidad": unidad.pk,
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123",
        }
        form_sin_checkbox = RegistroResidenteForm(data=datos, condominio=condominio)
        self.assertFalse(form_sin_checkbox.is_valid())

        datos["acepto_terminos"] = True
        form_con_checkbox = RegistroResidenteForm(data=datos, condominio=condominio)
        self.assertTrue(form_con_checkbox.is_valid(), form_con_checkbox.errors)


class CrearCondominioRegionComunaTests(TestCase):
    """region/comuna del nuevo formulario de devquad (DevquadCrearCondominioView)
    son desplegables en cascada según la región (ver comunas_chile.py y
    cascada_region_comuna.js) -- confirma que el form acepta una
    combinación real, rechaza una que no corresponde, y que la página
    carga el JS y los datos para la cascada."""

    def _datos(self, region, comuna, **extra):
        datos = {"nombre": "Condo Region Comuna", "etiqueta_organizacion": "Condominio", "region": region, "comuna": comuna}
        datos.update(extra)
        return datos

    def test_acepta_una_combinacion_real(self):
        form = CrearCondominioForm(data=self._datos("valparaiso", "Valparaíso"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_rechaza_comuna_que_no_es_de_esa_region(self):
        form = CrearCondominioForm(data=self._datos("valparaiso", "Santiago"))
        self.assertFalse(form.is_valid())
        self.assertIn("no pertenece a la región elegida", str(form.errors))

    def test_permite_dejar_region_y_comuna_vacias(self):
        form = CrearCondominioForm(data=self._datos("", ""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_la_pagina_de_crear_condominio_carga_el_js_de_la_cascada(self):
        self.client.force_login(crear_devquad())
        r = self.client.get(reverse("devquad-crear-condominio"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('name="region"', html)
        self.assertIn('name="comuna"', html)
        self.assertIn("cascada_region_comuna.js", html)
        self.assertIn("Valparaíso", html)


class NormalizarNombreTests(TestCase):
    """nombre/apellido quedan con la primera letra de cada palabra en
    mayúscula sin importar cómo los haya tipeado la persona."""

    def test_normalizar_nombre_casos_basicos(self):
        from .forms import _normalizar_nombre

        self.assertEqual(_normalizar_nombre("juan perez"), "Juan Perez")
        self.assertEqual(_normalizar_nombre("JUAN PEREZ"), "Juan Perez")
        self.assertEqual(_normalizar_nombre("  juan   perez  "), "Juan Perez")
        self.assertEqual(_normalizar_nombre("o'higgins"), "O'Higgins")

    def test_registro_residente_normaliza_nombre_y_apellido(self):
        condominio = Condominio.objects.create(nombre="Test Normalizar Residente", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        datos = {
            "nombre": "ROSA", "apellido": "mena soto", "email": "rosa_normaliza@example.com", "unidad": unidad.pk,
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        }
        form = RegistroResidenteForm(data=datos, condominio=condominio)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["nombre"], "Rosa")
        self.assertEqual(form.cleaned_data["apellido"], "Mena Soto")

    def test_crear_miembro_normaliza_nombre_y_apellido(self):
        condominio = Condominio.objects.create(nombre="Test Normalizar Miembro", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        form = CrearMiembroForm(
            data={"nombre": "ana", "apellido": "SOTO", "email": "ana_normaliza@example.com", "rol": "residente", "unidad": unidad.pk},
            condominio=condominio,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["nombre"], "Ana")
        self.assertEqual(form.cleaned_data["apellido"], "Soto")

    def test_mi_perfil_normaliza_nombre_y_apellido(self):
        from .forms import MiPerfilForm

        condominio = Condominio.objects.create(nombre="Test Normalizar Perfil", plan="premium")
        membresia = crear_membresia(condominio, "residente", username="perfil_normaliza", email="perfil_normaliza@example.com")
        form = MiPerfilForm(
            data={"first_name": "pedro", "last_name": "GOMEZ", "email": membresia.user.email},
            instance=membresia.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["first_name"], "Pedro")
        self.assertEqual(form.cleaned_data["last_name"], "Gomez")


class NormalizarNombresExistentesTests(TestCase):
    """Vista de uso único /admin-utils/normalizar-nombres/ -- corrige lo que
    ya quedó mal capitalizado en producción antes de este cambio."""

    def setUp(self):
        self.staff = User.objects.create_user(username="nn_staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_requiere_staff(self):
        self.client.logout()
        normal = User.objects.create_user(username="nn_normal")
        self.client.force_login(normal)
        r = self.client.get(reverse("normalizar-nombres"))
        self.assertEqual(r.status_code, 302)

    def test_corrige_nombres_mal_capitalizados(self):
        user = User.objects.create_user(username="nn_mal", first_name="juan", last_name="PEREZ")
        r = self.client.get(reverse("normalizar-nombres"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("nn_mal", r.content.decode())
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Juan")
        self.assertEqual(user.last_name, "Perez")

    def test_no_toca_lo_que_ya_esta_bien(self):
        User.objects.create_user(username="nn_bien", first_name="Juan", last_name="Perez")
        r = self.client.get(reverse("normalizar-nombres"))
        self.assertIn("Ningún nombre necesitaba normalizarse", r.content.decode())

    def test_es_idempotente(self):
        User.objects.create_user(username="nn_doble", first_name="juan", last_name="perez")
        self.client.get(reverse("normalizar-nombres"))
        r2 = self.client.get(reverse("normalizar-nombres"))
        self.assertIn("Ningún nombre necesitaba normalizarse", r2.content.decode())


class AutoregistroCasasLibresTests(TestCase):
    """Cuando el condominio todavía no tiene ninguna unidad cargada (junta
    de vecinos nueva, sin estructura de torres/pisos -- ej. casas con
    numeración propia), el autoregistro deja escribir el número en vez de
    mostrar un dropdown vacío e imposible de usar. La unidad se crea sola
    (sin block) la primera vez que alguien escribe ese número."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Casas Libres", plan="premium", etiqueta_unidad="Casa")

    def _datos_base(self, **extra):
        datos = {
            "nombre": "Rosa", "apellido": "Mena", "email": "rosa_casas@example.com",
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        }
        datos.update(extra)
        return datos

    def test_form_en_modo_casas_no_exige_ninguno_de_los_dos_por_separado(self):
        """unidad y numero_unidad_libre son opcionales cada uno por su
        cuenta en modo casas -- clean() exige al menos uno de los dos
        (ver test_sin_numero_no_se_puede_registrar), no un campo fijo
        obligatorio, porque el primer vecino no tiene nada que elegir
        todavía y el segundo sí."""
        form = RegistroResidenteForm(condominio=self.condominio)
        self.assertIn("unidad", form.fields)
        self.assertIn("numero_unidad_libre", form.fields)
        self.assertFalse(form.fields["unidad"].required)
        self.assertFalse(form.fields["numero_unidad_libre"].required)

    def test_pagina_de_registro_renderiza_bien_en_modo_casas(self):
        r = self.client.get(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "número de tu casa")

    def test_elegir_una_unidad_existente_no_crea_una_nueva(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="123")
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(unidad=unidad.pk),
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio).count(), 1)
        user = User.objects.get(email="rosa_casas@example.com")
        self.assertEqual(user.membresia.unidad, unidad)

    def test_form_con_torres_tambien_permite_depto_libre(self):
        """La señal de "condominio estructurado" es tener torres cargadas
        (como Empart) -- no solo que exista alguna unidad, porque las
        unidades de un condominio de casas también se van creando solas
        (ver test_dos_personas_con_el_mismo_numero_comparten_la_unidad) y
        eso no debería "trabar" el modo libre para el segundo vecino.

        La torre sí se escribe libre (como calle en casas) pero tiene que
        calzar con una ya creada, ver AutoregistroDeptoLibreConTorresTests."""
        from .models import Torre

        torre = Torre.objects.create(condominio=self.condominio, nombre="1")
        Unidad.objects.create(condominio=self.condominio, torre=torre, numero="1")
        form = RegistroResidenteForm(condominio=self.condominio)
        self.assertIn("unidad", form.fields)
        self.assertIn("numero_unidad_libre", form.fields)
        self.assertIn("torre_unidad_libre", form.fields)
        self.assertNotIn("calle_unidad_libre", form.fields)
        self.assertFalse(form.fields["unidad"].required)
        self.assertFalse(form.fields["numero_unidad_libre"].required)
        self.assertFalse(form.fields["torre_unidad_libre"].required)

    def test_registrarse_con_numero_libre_crea_la_unidad_sin_block(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(calle_unidad_libre="Los Aromos", numero_unidad_libre="123"),
        )
        self.assertEqual(r.status_code, 302)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="123")
        self.assertIsNone(unidad.torre)
        user = User.objects.get(email="rosa_casas@example.com")
        self.assertEqual(user.membresia.unidad, unidad)

    def test_dos_personas_con_el_mismo_numero_comparten_la_unidad(self):
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(calle_unidad_libre="Los Aromos", numero_unidad_libre="123"),
        )
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(
                nombre="Juan", apellido="Mena", email="juan_casas@example.com",
                calle_unidad_libre="Los Aromos", numero_unidad_libre="123",
            ),
        )
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio, numero="123").count(), 1)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="123")
        self.assertEqual(unidad.membresias.count(), 2)

    def test_sin_numero_no_se_puede_registrar(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(calle_unidad_libre="Los Aromos", numero_unidad_libre=""),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="rosa_casas@example.com").exists())

    def test_sin_calle_no_se_puede_crear_una_casa_nueva(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(numero_unidad_libre="88", calle_unidad_libre=""),
        )
        self.assertEqual(r.status_code, 200)  # se queda en el form con el error, no redirige
        self.assertContains(r, "Escribe el nombre de tu calle")
        self.assertFalse(Unidad.objects.filter(condominio=self.condominio, numero="88").exists())
        self.assertFalse(User.objects.filter(email="rosa_casas@example.com").exists())

    def test_registrarse_con_calle_y_numero_guarda_la_calle(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(calle_unidad_libre="los aromos", numero_unidad_libre="45"),
        )
        self.assertEqual(r.status_code, 302)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="45")
        # se normaliza igual que nombre/apellido (primera letra en mayúscula)
        self.assertEqual(unidad.calle, "Los Aromos")

    def test_mismo_numero_en_calles_distintas_son_unidades_distintas(self):
        """El problema real que resuelve la calle: una junta de vecinos
        grande puede tener "Casa 45" repetido en más de una calle -- sin
        la calle, el segundo registro se habría mezclado con el primero."""
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(calle_unidad_libre="Los Aromos", numero_unidad_libre="45"),
        )
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(
                nombre="Juan", apellido="Soto", email="juan_otra_calle@example.com",
                calle_unidad_libre="Los Pinos", numero_unidad_libre="45",
            ),
        )
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio, numero="45").count(), 2)
        self.assertTrue(Unidad.objects.filter(condominio=self.condominio, numero="45", calle="Los Aromos").exists())
        self.assertTrue(Unidad.objects.filter(condominio=self.condominio, numero="45", calle="Los Pinos").exists())

    def test_elegir_unidad_existente_de_la_lista_no_exige_calle(self):
        """calle solo es obligatoria para crear una casa nueva por texto
        libre -- elegir una ya existente del desplegable no debería
        pedirla de nuevo (ya quedó guardada cuando se creó)."""
        unidad = Unidad.objects.create(condominio=self.condominio, numero="123", calle="Los Aromos")
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(unidad=unidad.pk),
        )
        self.assertEqual(r.status_code, 302)


class AutoregistroDeptoLibreConTorresTests(TestCase):
    """Mismo problema que resuelven calle+número en modo casas
    (AutoregistroCasasLibresTests), pero para condominios con torres: el
    depto puede no estar todavía en la lista de Unidad. La torre SÍ se
    escribe libre (igual que calle en casas, con datalist de ayuda) pero
    tiene que calzar con una torre ya creada por administración/DevQuad
    (ver SoloStaffMixin, nombre__iexact en clean()) -- no se crea una
    torre nueva solo porque alguien la escribió."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Torres Depto Libre", plan="premium")
        cls.torre1 = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.torre2 = Torre.objects.create(condominio=cls.condominio, nombre="2")

    def _datos_base(self, **extra):
        datos = {
            "nombre": "Rosa", "apellido": "Mena", "email": "rosa_torres@example.com",
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        }
        datos.update(extra)
        return datos

    def test_registrarse_con_depto_libre_crea_la_unidad_en_la_torre_escrita(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(torre_unidad_libre="1", numero_unidad_libre="302"),
        )
        self.assertEqual(r.status_code, 302)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="302")
        self.assertEqual(unidad.torre, self.torre1)
        user = User.objects.get(email="rosa_torres@example.com")
        self.assertEqual(user.membresia.unidad, unidad)

    def test_la_torre_no_distingue_mayusculas(self):
        torre = Torre.objects.create(condominio=self.condominio, nombre="Norte")
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(torre_unidad_libre="NORTE", numero_unidad_libre="7"),
        )
        self.assertEqual(r.status_code, 302)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="7")
        self.assertEqual(unidad.torre, torre)

    def test_dos_personas_con_el_mismo_numero_en_la_misma_torre_comparten_la_unidad(self):
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(torre_unidad_libre="1", numero_unidad_libre="302"),
        )
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(
                nombre="Juan", apellido="Mena", email="juan_torres@example.com",
                torre_unidad_libre="1", numero_unidad_libre="302",
            ),
        )
        unidad = Unidad.objects.get(condominio=self.condominio, torre=self.torre1, numero="302")
        self.assertEqual(unidad.membresias.count(), 2)

    def test_mismo_numero_en_torres_distintas_son_unidades_distintas(self):
        """El problema real que resuelve la torre: "Depto 302" puede
        repetirse en más de una torre -- sin elegir la torre, el segundo
        registro se habría mezclado con el primero."""
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(torre_unidad_libre="1", numero_unidad_libre="302"),
        )
        self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(
                nombre="Juan", apellido="Soto", email="juan_otra_torre@example.com",
                torre_unidad_libre="2", numero_unidad_libre="302",
            ),
        )
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio, numero="302").count(), 2)
        self.assertTrue(Unidad.objects.filter(condominio=self.condominio, numero="302", torre=self.torre1).exists())
        self.assertTrue(Unidad.objects.filter(condominio=self.condominio, numero="302", torre=self.torre2).exists())

    def test_sin_numero_no_se_puede_registrar(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(torre_unidad_libre="1", numero_unidad_libre=""),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="rosa_torres@example.com").exists())

    def test_sin_torre_no_se_puede_crear_un_depto_nuevo(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(numero_unidad_libre="88", torre_unidad_libre=""),
        )
        self.assertEqual(r.status_code, 200)  # se queda en el form con el error, no redirige
        self.assertContains(r, "Escribe tu")
        self.assertFalse(Unidad.objects.filter(condominio=self.condominio, numero="88").exists())
        self.assertFalse(User.objects.filter(email="rosa_torres@example.com").exists())

    def test_la_torre_libre_debe_ser_una_torre_existente(self):
        """A diferencia de calle en modo casas, acá no se puede inventar
        una torre nueva por typo -- tiene que calzar con una que
        administración/DevQuad ya creó."""
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(numero_unidad_libre="88", torre_unidad_libre="Torre Que No Existe"),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No encontramos esa")
        self.assertFalse(Unidad.objects.filter(condominio=self.condominio, numero="88").exists())
        self.assertFalse(Torre.objects.filter(condominio=self.condominio, nombre="Torre Que No Existe").exists())

    def test_elegir_unidad_existente_de_la_lista_no_exige_torre_libre(self):
        unidad = Unidad.objects.create(condominio=self.condominio, torre=self.torre1, numero="55")
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(unidad=unidad.pk),
        )
        self.assertEqual(r.status_code, 302)

    def test_pagina_de_registro_ofrece_el_depto_libre_y_un_datalist_de_torres(self):
        r = self.client.get(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "si tu unidad no está en la lista")
        self.assertContains(r, 'id="torres-existentes"')
        self.assertContains(r, '<option value="1">')


class CorreoBienvenidaTests(TestCase):
    """El email es obligatorio en ambos formularios de alta (autoregistro y
    CrearMiembroForm) justo para garantizar que siempre llegue el correo de
    bienvenida -- y aun así, que enviarlo nunca bloquee el alta si falla."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Bienvenida", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="1")

    def test_residente_con_email_recibe_bienvenida(self):
        r = self.client.post(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}), {
            "nombre": "Rosa", "apellido": "Mena", "email": "rosa@example.com", "unidad": self.unidad.pk,
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        })
        self.assertEqual(r.status_code, 302)
        user = User.objects.get(email="rosa@example.com")
        self.assertEqual(user.first_name, "Rosa")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["rosa@example.com"])
        self.assertIn("Bienvenido", mail.outbox[0].subject)

    def test_residente_sin_email_no_puede_registrarse(self):
        r = self.client.post(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}), {
            "nombre": "Ana", "apellido": "Soto", "unidad": self.unidad.pk,
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        })
        self.assertEqual(r.status_code, 200)  # se queda en el form con el error, no redirige
        self.assertFalse(User.objects.filter(first_name="Ana").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_crear_miembro_con_email_recibe_bienvenida(self):
        self.client.force_login(crear_devquad("bienvenida_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.post(reverse("crear-miembro"), {
            "nombre": "Juan", "apellido": "Perez", "email": "juan@example.com", "rol": "residente", "unidad": self.unidad.pk,
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["juan@example.com"])

    def test_crear_miembro_sin_email_no_crea_la_cuenta(self):
        self.client.force_login(crear_devquad("bienvenida_devquad3"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.post(reverse("crear-miembro"), {"nombre": "Luis", "apellido": "Rojas", "rol": "residente", "unidad": self.unidad.pk})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(first_name="Luis").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_el_correo_de_bienvenida_nunca_incluye_la_contrasena(self):
        self.client.force_login(crear_devquad("bienvenida_devquad2"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        self.client.post(reverse("crear-miembro"), {
            "nombre": "Pedro", "apellido": "Diaz", "email": "pedro@example.com", "rol": "residente", "unidad": self.unidad.pk,
        })
        user = User.objects.get(email="pedro@example.com")
        self.assertNotIn(user.password, mail.outbox[0].body)
        self.assertNotRegex(mail.outbox[0].body, r"contraseña")


class EmailUnicoTests(TestCase):
    """Un mismo email no puede quedar en dos cuentas -- se usa para el correo
    de bienvenida, comprobantes de pago y a futuro recuperar la contraseña."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Email Unico", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="1")
        cls.unidad2 = Unidad.objects.create(condominio=cls.condominio, numero="2")

    def setUp(self):
        self.existente = User.objects.create_user(username="email_unico_existente", email="repetido@example.com")

    def test_residente_no_puede_autoregistrarse_con_email_repetido(self):
        r = self.client.post(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}), {
            "nombre": "Rosa", "apellido": "Mena", "email": "repetido@example.com", "unidad": self.unidad.pk,
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya existe una cuenta registrada con este email")
        self.assertFalse(User.objects.filter(first_name="Rosa").exists())

    def test_email_repetido_no_distingue_mayusculas(self):
        r = self.client.post(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}), {
            "nombre": "Rosa", "apellido": "Mena", "email": "REPETIDO@example.com", "unidad": self.unidad.pk,
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya existe una cuenta registrada con este email")

    def test_devquad_no_puede_crear_miembro_con_email_repetido(self):
        self.client.force_login(crear_devquad("email_unico_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.post(reverse("crear-miembro"), {
            "nombre": "Juan", "apellido": "Perez", "email": "repetido@example.com", "rol": "residente", "unidad": self.unidad.pk,
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya existe una cuenta registrada con este email")
        self.assertFalse(User.objects.filter(first_name="Juan").exists())

    def test_mi_perfil_no_puede_cambiar_a_un_email_de_otra_cuenta(self):
        membresia = crear_membresia(self.condominio, "residente", unidad=self.unidad2, username="email_unico_yo", email="yo@example.com")
        self.client.force_login(membresia.user)
        r = self.client.post(reverse("mi-perfil"), {
            "first_name": "Yo", "last_name": "Mismo", "email": "repetido@example.com",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya existe una cuenta registrada con este email")
        membresia.user.refresh_from_db()
        self.assertEqual(membresia.user.email, "yo@example.com")

    def test_mi_perfil_puede_guardar_sin_cambiar_su_propio_email(self):
        membresia = crear_membresia(self.condominio, "residente", unidad=self.unidad2, username="email_unico_mismo", email="mismo@example.com")
        self.client.force_login(membresia.user)
        r = self.client.post(reverse("mi-perfil"), {
            "first_name": "Nombre Nuevo", "last_name": "Mismo", "email": "mismo@example.com",
        })
        self.assertRedirects(r, reverse("mi-perfil"))
        membresia.user.refresh_from_db()
        self.assertEqual(membresia.user.first_name, "Nombre Nuevo")


class PruebaGratisTests(TestCase):
    """20 días de prueba gratis del sistema de gestión (gastos comunes y
    personal) para cualquier condominio nuevo, sin importar cómo se crea --
    mismo pagado_hasta que ya usa SuscripcionActivaMixin, sin lógica aparte."""

    def test_condominio_nuevo_trae_20_dias_de_prueba_por_defecto(self):
        condominio = Condominio.objects.create(nombre="Test Prueba Gratis", plan="premium")
        dias_restantes = (condominio.pagado_hasta - timezone.localdate()).days
        self.assertEqual(dias_restantes, 20)

    def test_crear_condominio_desde_devquad_tambien_trae_la_prueba_gratis(self):
        self.client.force_login(crear_devquad())
        r = self.client.post(reverse("devquad-crear-condominio"), {
            "nombre": "Condo Prueba Devquad", "etiqueta_organizacion": "Condominio",
        })
        self.assertEqual(r.status_code, 302)
        condominio = Condominio.objects.get(nombre="Condo Prueba Devquad")
        self.assertIsNotNone(condominio.pagado_hasta)
        self.assertGreaterEqual(condominio.pagado_hasta, timezone.localdate())

    def test_se_puede_crear_sin_prueba_explicitamente(self):
        """Los management commands de alta manual (ej. crear_condominio_empart)
        pueden seguir pasando pagado_hasta=None a propósito si no quieren dar
        el trial -- el default no lo fuerza."""
        condominio = Condominio.objects.create(nombre="Test Sin Prueba", plan="premium", pagado_hasta=None)
        self.assertIsNone(condominio.pagado_hasta)


class DonacionVisibilidadTests(TestCase):
    """La donación es exclusiva de residente/delegado -- devquad no la ve
    (no tiene Membresia propia en el condominio que está operando)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Donacion Visibilidad", plan="premium")

    def test_devquad_no_ve_la_tarjeta_de_donacion(self):
        self.client.force_login(crear_devquad("donvis_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"Apoya el proyecto", r.content)

    def test_residente_si_ve_la_tarjeta_de_donacion(self):
        membresia = crear_membresia(self.condominio, "residente", username="donvis_residente")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Apoya el proyecto", r.content)

    def test_delegado_si_ve_la_tarjeta_de_donacion(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        membresia = crear_membresia(self.condominio, "delegado", unidad=unidad, username="donvis_delegado")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Apoya el proyecto", r.content)


class ApiAuthTests(TestCase):
    """Login/logout/me de la API JWT (core/api_views.py) -- usado por la
    futura app Expo, nunca ejercitado por los tests de la web (que se
    autentican con force_login, sin pasar por este flujo)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Api Auth", plan="premium")

    def setUp(self):
        self.user = User.objects.create_user(username="api_auth_user", password="clave-segura-123")
        self.membresia = Membresia.objects.create(
            user=self.user, condominio=self.condominio, rol="residente", terminos_aceptados_en=timezone.now(),
        )

    def test_login_devuelve_tokens_y_la_membresia(self):
        r = self.client.post(reverse("api-login"), {"username": "api_auth_user", "password": "clave-segura-123"})
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertIn("access", datos)
        self.assertIn("refresh", datos)
        self.assertEqual(datos["membresia"]["rol"], "residente")
        self.assertEqual(datos["membresia"]["condominio"]["nombre"], self.condominio.nombre)

    def test_login_sin_membresia_devuelve_membresia_none(self):
        User.objects.create_user(username="sin_membresia_api", password="clave-segura-123")
        r = self.client.post(reverse("api-login"), {"username": "sin_membresia_api", "password": "clave-segura-123"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["membresia"])

    def test_login_con_clave_incorrecta_falla(self):
        r = self.client.post(reverse("api-login"), {"username": "api_auth_user", "password": "clave-mala"})
        self.assertEqual(r.status_code, 401)

    def test_me_requiere_autenticacion(self):
        r = self.client.get(reverse("api-me"))
        self.assertEqual(r.status_code, 401)

    def test_me_devuelve_la_membresia_del_usuario_autenticado(self):
        login = self.client.post(reverse("api-login"), {"username": "api_auth_user", "password": "clave-segura-123"})
        access = login.json()["access"]
        r = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["rol"], "residente")

    def test_me_sin_membresia_devuelve_409(self):
        User.objects.create_user(username="sin_membresia_me", password="clave-segura-123")
        login = self.client.post(reverse("api-login"), {"username": "sin_membresia_me", "password": "clave-segura-123"})
        access = login.json()["access"]
        r = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(r.status_code, 409)

    def test_logout_invalida_el_refresh_token(self):
        login = self.client.post(reverse("api-login"), {"username": "api_auth_user", "password": "clave-segura-123"})
        access, refresh = login.json()["access"], login.json()["refresh"]
        r = self.client.post(
            reverse("api-logout"), {"refresh": refresh},
            content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(r.status_code, 205)

    def test_logout_sin_refresh_token_devuelve_400(self):
        login = self.client.post(reverse("api-login"), {"username": "api_auth_user", "password": "clave-segura-123"})
        access = login.json()["access"]
        r = self.client.post(
            reverse("api-logout"), {},
            content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(r.status_code, 400)

    def test_logout_requiere_autenticacion(self):
        r = self.client.post(reverse("api-logout"), {}, content_type="application/json")
        self.assertEqual(r.status_code, 401)


class ApiMiPerfilYCambiarContrasenaTests(TestCase):
    """PATCH /auth/me/ (editar perfil) y POST /auth/cambiar-contrasena/ --
    mismas reglas que el panel web (MiPerfilForm/MiCambiarContrasenaForm),
    para que la futura app Expo se comporte igual."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Api Perfil", plan="premium")

    def setUp(self):
        self.user = User.objects.create_user(username="api_perfil_user", password="clave-segura-123", email="yo@example.com")
        Membresia.objects.create(user=self.user, condominio=self.condominio, rol="residente", terminos_aceptados_en=timezone.now())
        login = self.client.post(reverse("api-login"), {"username": "api_perfil_user", "password": "clave-segura-123"})
        self.access = login.json()["access"]

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.access}"}

    def test_actualizar_perfil_requiere_autenticacion(self):
        r = self.client.patch(reverse("api-me"), {"first_name": "Nuevo"}, content_type="application/json")
        self.assertEqual(r.status_code, 401)

    def test_actualizar_nombre_y_email(self):
        r = self.client.patch(
            reverse("api-me"), {"first_name": "Logan", "last_name": "Silva", "email": "nuevo@example.com"},
            content_type="application/json", **self._auth(),
        )
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Logan")
        self.assertEqual(self.user.email, "nuevo@example.com")

    def test_actualizar_perfil_con_email_de_otra_cuenta_falla(self):
        User.objects.create_user(username="api_perfil_otro", email="ocupado@example.com")
        r = self.client.patch(
            reverse("api-me"), {"email": "ocupado@example.com"},
            content_type="application/json", **self._auth(),
        )
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "yo@example.com")

    def test_actualizar_perfil_puede_guardar_sin_cambiar_su_propio_email(self):
        r = self.client.patch(
            reverse("api-me"), {"email": "yo@example.com", "first_name": "Mismo"},
            content_type="application/json", **self._auth(),
        )
        self.assertEqual(r.status_code, 200)

    def test_cambiar_contrasena_requiere_autenticacion(self):
        r = self.client.post(reverse("api-cambiar-contrasena"), {}, content_type="application/json")
        self.assertEqual(r.status_code, 401)

    def test_cambiar_contrasena_exitoso(self):
        r = self.client.post(
            reverse("api-cambiar-contrasena"),
            {"password_actual": "clave-segura-123", "password_nueva1": "otraClaveSegura456", "password_nueva2": "otraClaveSegura456"},
            content_type="application/json", **self._auth(),
        )
        self.assertEqual(r.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("otraClaveSegura456"))

    def test_cambiar_contrasena_actual_incorrecta(self):
        r = self.client.post(
            reverse("api-cambiar-contrasena"),
            {"password_actual": "clave-mala", "password_nueva1": "otraClaveSegura456", "password_nueva2": "otraClaveSegura456"},
            content_type="application/json", **self._auth(),
        )
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("clave-segura-123"))

    def test_cambiar_contrasena_nuevas_no_coinciden(self):
        r = self.client.post(
            reverse("api-cambiar-contrasena"),
            {"password_actual": "clave-segura-123", "password_nueva1": "otraClaveSegura456", "password_nueva2": "distinta789"},
            content_type="application/json", **self._auth(),
        )
        self.assertEqual(r.status_code, 400)

    def test_cambiar_contrasena_nueva_demasiado_debil(self):
        r = self.client.post(
            reverse("api-cambiar-contrasena"),
            {"password_actual": "clave-segura-123", "password_nueva1": "12345678", "password_nueva2": "12345678"},
            content_type="application/json", **self._auth(),
        )
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("clave-segura-123"))


class InicioViewTests(TestCase):
    """Ramas de InicioView no cubiertas por el resto de los tests: staff sin
    membresía ni condominio activo va al selector de condominios de devquad,
    y el resumen de administración (ahora devquad) cuando SÍ hay un gasto
    común del periodo actual."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Inicio Extra", plan="premium")

    def test_staff_sin_membresia_va_al_selector_de_condominios(self):
        staff = User.objects.create_user(username="inicio_staff", is_staff=True)
        self.client.force_login(staff)
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("devquad-condominios"))

    def test_no_staff_sin_membresia_va_al_login_con_mensaje(self):
        user = User.objects.create_user(username="inicio_sin_membresia")
        self.client.force_login(user)
        r = self.client.get(reverse("inicio"), follow=True)
        self.assertContains(r, "no está vinculada a ningún condominio")

    def test_resumen_administracion_para_devquad(self):
        from alertas.models import Alerta

        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        residente = crear_membresia(self.condominio, "residente", unidad=unidad, username="inicio_resumen_residente")
        Alerta.objects.create(condominio=self.condominio, autor=residente, tipo="otro", estado="activa")
        staff = User.objects.create_user(username="inicio_admon_resumen", is_staff=True)
        self.client.force_login(staff)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["total_unidades"], 1)
        self.assertEqual(r.context["total_miembros"], 1)
        self.assertEqual(r.context["alertas_activas_count"], 1)

    def test_muestra_el_boton_de_panico_flotante(self):
        """Regresión: el botón de pánico quedaba muy abajo en el dashboard
        -- se agregó un botón flotante fijo siempre visible, que abre el
        mismo modal #modalPanico."""
        residente = crear_membresia(self.condominio, "residente", username="inicio_panico_flotante")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, 'id="btn-panico-flotante"')
        self.assertContains(r, 'data-bs-target="#modalPanico"')

    def test_sin_perfil_geografico_ofrece_sumarse_a_la_red_vecinal(self):
        residente = crear_membresia(self.condominio, "residente", username="inicio_sin_perfil_geo")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, reverse("vecindario-unirse"))

    def test_con_perfil_geografico_no_ofrece_sumarse_de_nuevo(self):
        from vecindario.models import PerfilGeografico

        residente = crear_membresia(self.condominio, "residente", username="inicio_con_perfil_geo")
        PerfilGeografico.objects.create(
            user=residente.user, direccion_texto="Calle Falsa 123", lat=-33.0, lng=-71.6,
            region="valparaiso", comuna="Valparaíso", geohash="66j5f",
        )
        self.client.force_login(residente.user)
        r = self.client.get(reverse("inicio"))
        self.assertNotContains(r, reverse("vecindario-unirse"))


class EtiquetaOrganizacionTests(TestCase):
    """No todas las organizaciones son "condominio" (ej. juntas de vecinos) --
    confirma que "Mi condominio" en el nav/inicio/ajustes sale de
    etiqueta_organizacion y no está escrito fijo en los templates."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Junta Los Aromos", plan="premium", etiqueta_organizacion="Junta de vecinos")

    def _login_devquad(self, condominio, username):
        self.client.force_login(crear_devquad(username))
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))

    def test_inicio_usa_la_etiqueta_de_la_organizacion(self):
        self._login_devquad(self.condominio, "inicio_devquad_junta")
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "Mi junta de vecinos")
        self.assertNotContains(r, "Mi condominio")

    def test_mi_condominio_usa_la_etiqueta_de_la_organizacion(self):
        self._login_devquad(self.condominio, "mi_condominio_devquad")
        r = self.client.get(reverse("mi-condominio"))
        self.assertContains(r, "Mi junta de vecinos")
        self.assertNotContains(r, "Mi condominio")

    def test_por_defecto_sigue_diciendo_condominio(self):
        condominio_default = Condominio.objects.create(nombre="Condominio Default Test", plan="premium")
        self._login_devquad(condominio_default, "devquad_condominio_default")
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "Mi condominio")


class EstadisticasLandingTests(TestCase):
    """La landing muestra prueba social con números reales calculados en
    vivo (ver InicioView._estadisticas_landing), no testimonios inventados --
    confirma que la sección no aparece vacía y que refleja datos reales."""

    def test_no_muestra_la_seccion_si_no_hay_datos_reales(self):
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.context["stat_organizaciones"], 0)
        self.assertNotContains(r, "Números reales, no de marketing")

    def test_muestra_los_numeros_reales_cuando_hay_datos(self):
        condominio = Condominio.objects.create(nombre="Stats Landing Test", plan="premium")
        Unidad.objects.create(condominio=condominio, numero="1")
        Unidad.objects.create(condominio=condominio, numero="2")
        crear_membresia(condominio, "residente", username="stats_landing_residente")
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "Números reales, no de marketing")
        self.assertEqual(r.context["stat_organizaciones"], 1)
        self.assertEqual(r.context["stat_unidades"], 2)
        self.assertEqual(r.context["stat_miembros"], 1)
        self.assertEqual(r.context["stat_alertas_resueltas"], 0)
        self.assertNotContains(r, "alertas de pánico resueltas")

    def test_muestra_las_alertas_resueltas_solo_si_hay_alguna(self):
        from alertas.models import Alerta

        condominio = Condominio.objects.create(nombre="Stats Alertas Test", plan="premium")
        autor = crear_membresia(condominio, "residente", username="stats_alertas_autor")
        Alerta.objects.create(condominio=condominio, autor=autor, estado="resuelta", resuelta_por=autor)
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "1 alertas de pánico resueltas hasta ahora")


class ServiceWorkerViewTests(TestCase):
    def test_sirve_el_sw_js_con_scope_global(self):
        r = self.client.get(reverse("service-worker"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/javascript")
        self.assertEqual(r["Service-Worker-Allowed"], "/")


class SolicitarEliminacionViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Eliminacion", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", username="elim_residente", email="elim_residente@example.com")
        self.client.force_login(self.membresia.user)

    def test_get_muestra_el_formulario(self):
        r = self.client.get(reverse("solicitar-eliminacion"))
        self.assertEqual(r.status_code, 200)

    def test_post_crea_la_solicitud_y_avisa_por_correo(self):
        from .models import SolicitudEliminacion

        r = self.client.post(reverse("solicitar-eliminacion"), {"motivo": "Ya no vivo aquí"})
        self.assertRedirects(r, reverse("mi-perfil"))
        solicitud = SolicitudEliminacion.objects.get(username="elim_residente")
        self.assertEqual(solicitud.motivo, "Ya no vivo aquí")
        self.assertEqual(solicitud.email, "elim_residente@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [EMAIL_CONTACTO_DEVQUAD])


class MarcarSolicitudEliminacionAtendidaTests(TestCase):
    """Al marcar atendida una SolicitudEliminacion (acción del admin), se le
    avisa a la persona por correo que ya se procesó -- usando el email
    guardado al momento del pedido, no membresia.user.email (que puede ya
    no existir para entonces, ver core/models.py)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Marcar Eliminacion", plan="premium")

    def setUp(self):
        self.staff = User.objects.create_superuser(username="marcar_elim_staff", password="x")
        self.client.force_login(self.staff)

    def _solicitud(self, **kwargs):
        from .models import SolicitudEliminacion
        kwargs.setdefault("nombre", "Ana Soto")
        kwargs.setdefault("username", "ana_elim")
        kwargs.setdefault("email", "ana_elim@example.com")
        kwargs.setdefault("condominio_nombre", self.condominio.nombre)
        return SolicitudEliminacion.objects.create(**kwargs)

    def _marcar_atendida(self, *pks):
        return self.client.post("/admin/core/solicitudeliminacion/", {
            "action": "marcar_atendida",
            "_selected_action": [str(pk) for pk in pks],
        })

    def test_marca_atendida_y_manda_el_correo(self):
        solicitud = self._solicitud()
        self._marcar_atendida(solicitud.pk)
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.atendida)
        self.assertIsNotNone(solicitud.fecha_atencion)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana_elim@example.com"])

    def test_sin_email_guardado_no_falla_y_no_manda_correo(self):
        solicitud = self._solicitud(email="", username="sin_email_elim")
        self._marcar_atendida(solicitud.pk)
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.atendida)
        self.assertEqual(len(mail.outbox), 0)

    def test_repetir_la_accion_no_reenvia_el_correo(self):
        solicitud = self._solicitud()
        self._marcar_atendida(solicitud.pk)
        self._marcar_atendida(solicitud.pk)
        self.assertEqual(len(mail.outbox), 1)


class QRYRegenerarTokenResidentesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test QR Token", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="qr_residente_setup")
        self.client.force_login(self.residente.user)

    def test_qr_devuelve_una_imagen_png(self):
        r = self.client.get(reverse("qr-registro-residentes"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")

    def test_un_residente_tambien_puede_ver_el_qr(self):
        residente = crear_membresia(self.condominio, "residente", username="qr_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("qr-registro-residentes"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")

    def test_regenerar_token_cambia_el_token(self):
        self.client.force_login(crear_devquad("qr_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        token_original = self.condominio.token_registro_residentes
        r = self.client.post(reverse("regenerar-token-residentes"))
        self.assertRedirects(r, reverse("mi-condominio"))
        self.condominio.refresh_from_db()
        self.assertNotEqual(self.condominio.token_registro_residentes, token_original)

    def test_un_residente_no_puede_regenerar_el_token(self):
        residente = crear_membresia(self.condominio, "residente", username="qr_residente_regen")
        self.client.force_login(residente.user)
        token_original = self.condominio.token_registro_residentes
        self.client.post(reverse("regenerar-token-residentes"))
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.token_registro_residentes, token_original)


class MiembroListFiltroRolTests(TestCase):
    def test_filtra_por_rol(self):
        condominio = Condominio.objects.create(nombre="Test Filtro Rol", plan="premium")
        crear_membresia(condominio, "residente", username="filtro_rol_residente")
        self.client.force_login(crear_devquad("filtro_rol_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.get(reverse("miembros") + "?rol=residente")
        self.assertEqual(len(r.context["membresias"]), 1)

    def test_no_muestra_el_nombre_de_usuario(self):
        condominio = Condominio.objects.create(nombre="Test Sin Usuario", plan="premium")
        crear_membresia(condominio, "residente", username="sinusuario_residente_unico", first_name="Rosa", last_name="Mena")
        self.client.force_login(crear_devquad("sinusuario_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.get(reverse("miembros"))
        self.assertNotContains(r, "sinusuario_residente_unico")
        self.assertContains(r, "Rosa Mena")

    def test_ordena_por_block_y_depto_numerico_no_alfabetico(self):
        from .models import Torre

        condominio = Condominio.objects.create(nombre="Test Orden Miembros", plan="premium")
        torre_10 = Torre.objects.create(condominio=condominio, nombre="10")
        torre_2 = Torre.objects.create(condominio=condominio, nombre="2")
        unidad_10 = Unidad.objects.create(condominio=condominio, torre=torre_10, numero="1")
        unidad_2 = Unidad.objects.create(condominio=condominio, torre=torre_2, numero="1")
        crear_membresia(condominio, "residente", unidad=unidad_10, username="orden_miembros_t10")
        crear_membresia(condominio, "residente", unidad=unidad_2, username="orden_miembros_t2")

        self.client.force_login(crear_devquad("orden_miembros_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.get(reverse("miembros"))
        residentes = [m for m in r.context["membresias"] if m.rol == "residente"]
        self.assertEqual([m.unidad.torre.nombre for m in residentes], ["2", "10"])


class DashboardResidenteTests(TestCase):
    """El dashboard de residente ya no ofrece Directorio (ver decisión de
    producto) ni gastos comunes (app retirada) -- sí sigue ofreciendo
    invitar vecinos."""

    def test_residente_no_ve_directorio_pero_si_invitar_vecinos(self):
        condominio = Condominio.objects.create(nombre="Test Dashboard Residente", plan="premium")
        membresia = crear_membresia(condominio, "residente", username="dashboard_residente")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertNotContains(r, reverse("directorio"))
        self.assertContains(r, reverse("compartir-invitacion"))

    def test_residente_no_puede_entrar_directo_al_directorio(self):
        """Regresión: el link desaparece del dashboard, pero la URL en sí
        también debe rechazar a residente, no solo esconder el botón."""
        condominio = Condominio.objects.create(nombre="Test Directorio Bloqueado", plan="premium")
        membresia = crear_membresia(condominio, "residente", username="directorio_bloqueado_residente")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("directorio"), follow=True)
        self.assertRedirects(r, reverse("inicio"))
        self.assertContains(r, "ya no está disponible")

    def test_delegado_si_puede_ver_el_directorio(self):
        condominio = Condominio.objects.create(nombre="Test Directorio Delegado", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        membresia = crear_membresia(condominio, "delegado", unidad=unidad, username="directorio_delegado")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("directorio"))
        self.assertEqual(r.status_code, 200)

    def test_residente_ve_cantidad_de_torres_unidades_y_miembros(self):
        condominio = Condominio.objects.create(nombre="Test Dashboard Residente Conteos", plan="premium")
        torre = Torre.objects.create(condominio=condominio, nombre="1")
        Unidad.objects.create(condominio=condominio, torre=torre, numero="101")
        Unidad.objects.create(condominio=condominio, torre=torre, numero="102")
        membresia = crear_membresia(condominio, "residente", username="dashboard_residente_conteos")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.context["total_torres"], 1)
        self.assertEqual(r.context["total_unidades"], 2)
        self.assertEqual(r.context["total_miembros"], 1)


class CompartirInvitacionTests(TestCase):
    """Cualquier vecino puede entrar a ver/compartir el link y QR de
    autoregistro -- regenerar el link sigue siendo exclusivo de directiva
    (ver QRYRegenerarTokenResidentesTests)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Compartir Invitacion", plan="premium")

    def test_requiere_login(self):
        r = self.client.get(reverse("compartir-invitacion"))
        self.assertEqual(r.status_code, 302)

    def test_cualquier_rol_puede_entrar_y_ve_el_link_y_el_boton_de_whatsapp(self):
        for rol in ("residente", "delegado"):
            membresia = crear_membresia(self.condominio, rol, username=f"invitar_{rol}")
            self.client.force_login(membresia.user)
            r = self.client.get(reverse("compartir-invitacion"))
            self.assertEqual(r.status_code, 200, rol)
            self.assertContains(r, reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}))
            self.assertContains(r, "wa.me")
            self.assertNotContains(r, reverse("regenerar-token-residentes"))

    def test_el_mensaje_de_whatsapp_usa_la_etiqueta_de_la_organizacion(self):
        junta = Condominio.objects.create(nombre="Junta Los Aromos Wsp", plan="premium", etiqueta_organizacion="Junta de vecinos")
        membresia = crear_membresia(junta, "residente", username="invitar_wsp_junta")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("compartir-invitacion"))
        # el mensaje va urlencoded dentro del href de wa.me -- los espacios
        # quedan como %20 (el filtro |urlencode de Django no usa "+").
        self.assertContains(r, "tu%20junta%20de%20vecinos")


class DirectorioVecinosTests(TestCase):
    """Directorio abierto a cualquier rol -- nombre y block/depto, sin
    usuario, email ni rol (eso sigue siendo exclusivo de MiembroListView)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Directorio", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="5")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="501")

    def test_requiere_login(self):
        r = self.client.get(reverse("directorio"))
        self.assertEqual(r.status_code, 302)

    def test_delegado_y_devquad_pueden_entrar(self):
        delegado = crear_membresia(self.condominio, "delegado", unidad=self.unidad, username="directorio_delegado_rol")
        self.client.force_login(delegado.user)
        r = self.client.get(reverse("directorio"))
        self.assertEqual(r.status_code, 200, "delegado")
        self.client.logout()

        self.client.force_login(crear_devquad("directorio_devquad_rol"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.get(reverse("directorio"))
        self.assertEqual(r.status_code, 200, "devquad")

    def test_muestra_nombre_y_depto_pero_no_usuario_ni_email_ni_rol(self):
        vecino = crear_membresia(
            self.condominio, "residente", unidad=self.unidad, username="directorio_vecino_secreto",
            email="vecino_secreto@example.com", first_name="Rosa", last_name="Mena",
        )
        yo = crear_membresia(self.condominio, "delegado", unidad=self.unidad, username="directorio_yo")
        self.client.force_login(yo.user)
        r = self.client.get(reverse("directorio"))
        contenido = r.content.decode()
        self.assertIn("Rosa Mena", contenido)
        self.assertIn("501", contenido)
        self.assertNotIn("directorio_vecino_secreto", contenido)
        self.assertNotIn("vecino_secreto@example.com", contenido)
        self.assertNotIn("Residente", contenido)


class CondominioRequiredMixinRamasTests(TestCase):
    """Ramas de CondominioRequiredMixin.dispatch() no cubiertas vía InicioView
    (que tiene su propia lógica inline, no usa este mixin): staff sin
    membresía ni condominio activo va al selector de condominios (ver
    DevquadCondominiosView/condominio_activo_devquad), y un condominio
    desactivado bloquea el acceso."""

    def test_staff_sin_membresia_va_al_selector_de_condominios(self):
        staff = User.objects.create_user(username="mixin_staff", is_staff=True)
        self.client.force_login(staff)
        r = self.client.get(reverse("miembros"))
        self.assertRedirects(r, reverse("devquad-condominios"))

    def test_condominio_desactivado_redirige_a_cuenta_desactivada(self):
        condominio = Condominio.objects.create(nombre="Test Desactivado", plan="premium", activo=False)
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        membresia = crear_membresia(condominio, "residente", unidad=unidad, username="mixin_desactivado")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("compartir-invitacion"))
        self.assertRedirects(r, reverse("cuenta-desactivada"))


class SoloStaffMixinPermiteStaffTests(TestCase):
    def test_staff_si_puede_crear_torre(self):
        """El caso típico de devquad: is_staff, sin Membresia propia, operando
        un condominio elegido vía el switcher (DevquadEntrarCondominioView)."""
        condominio = Condominio.objects.create(nombre="Test Staff Torre", plan="premium")
        self.client.force_login(crear_devquad("staff_torre"))
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.post(reverse("crear-torre"), {"nombre": "Nueva"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Torre.objects.filter(condominio=condominio, nombre="Nueva").exists())


class LoginConUsuarioOCorreoTests(TestCase):
    """UsuarioOCorreoBackend -- muchos residentes no recuerdan su username
    autogenerado (ej. "jlroman2") pero sí su correo."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Login Backend", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(
            self.condominio, "residente", username="login_residente",
            email="login_residente@example.com", password="ClaveDelUsuario123",
        )
        self.user = self.membresia.user

    def test_entra_con_el_username(self):
        ok = self.client.login(username="login_residente", password="ClaveDelUsuario123")
        self.assertTrue(ok)

    def test_entra_con_el_correo(self):
        ok = self.client.login(username="login_residente@example.com", password="ClaveDelUsuario123")
        self.assertTrue(ok)

    def test_entra_con_el_correo_sin_importar_mayusculas(self):
        ok = self.client.login(username="LOGIN_RESIDENTE@EXAMPLE.COM", password="ClaveDelUsuario123")
        self.assertTrue(ok)

    def test_contrasena_incorrecta_no_entra(self):
        ok = self.client.login(username="login_residente@example.com", password="esta-mal")
        self.assertFalse(ok)

    def test_correo_inexistente_no_entra_y_no_crashea(self):
        ok = self.client.login(username="no-existe@example.com", password="lo-que-sea")
        self.assertFalse(ok)

    def test_formulario_de_login_real_acepta_el_correo(self):
        r = self.client.post(reverse("login"), {"username": "login_residente@example.com", "password": "ClaveDelUsuario123"})
        self.assertRedirects(r, reverse("inicio"))


class RecuperarContrasenaTests(TestCase):
    """Flujo de "olvidé mi contraseña" (Django PasswordReset* + templates
    propias) -- antes no existía ninguna forma de que un vecino recuperara
    el acceso solo, tenía que pedirle a alguien que se la cambiara a mano
    desde el admin de Django."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Reset Contraseña", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(
            self.condominio, "residente", username="reset_residente",
            email="reset_residente@example.com", password="ClaveVieja123",
        )
        self.user = self.membresia.user

    def test_form_get_funciona(self):
        r = self.client.get(reverse("password-reset"))
        self.assertEqual(r.status_code, 200)

    def test_correo_inexistente_no_filtra_informacion(self):
        """Mismo correo de "revisa tu bandeja" exista o no la cuenta -- así
        nadie puede usar este formulario para adivinar qué correos están
        registrados."""
        r = self.client.post(reverse("password-reset"), {"email": "no-existe@example.com"})
        self.assertRedirects(r, reverse("password-reset-enviado"))
        self.assertEqual(len(mail.outbox), 0)

    def test_pedir_recuperacion_manda_un_correo_con_el_link_que_funciona(self):
        """No predice el token esperado con una segunda llamada a
        make_token() -- el generador de Django incluye la marca de tiempo
        en el hash, así que una segunda llamada un instante después del
        request puede dar un token distinto y el assert sería flaky sin
        que el feature esté mal. En vez de eso, extrae el link real del
        correo y confirma que ese, tal cual, funciona."""
        r = self.client.post(reverse("password-reset"), {"email": self.user.email})
        self.assertRedirects(r, reverse("password-reset-enviado"))
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [self.user.email])

        match = re.search(r"/contrasena/recuperar/[\w-]+/[\w-]+/", correo.body)
        self.assertIsNotNone(match)
        link = match.group(0)
        self.assertEqual(correo.alternatives[0][1], "text/html")
        self.assertIn(link, correo.alternatives[0][0])

        r2 = self.client.get(link, follow=True)
        self.assertEqual(r2.status_code, 200)
        self.assertNotContains(r2, "ya no es válido")

    def test_muestra_las_reglas_de_contrasena_sin_escapar(self):
        """ayudas_contrasena se arma en texto plano y se renderiza en un
        <li> por regla -- evita el |safe en el template (ver
        PasswordResetConfirmView)."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url_confirmar = reverse("password-reset-confirmar", kwargs={"uidb64": uid, "token": token})
        r = self.client.get(url_confirmar, follow=True)
        self.assertContains(r, "<li>")
        self.assertNotContains(r, "&lt;ul&gt;")

    def test_el_link_permite_elegir_contrasena_nueva(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url_confirmar = reverse("password-reset-confirmar", kwargs={"uidb64": uid, "token": token})

        r = self.client.get(url_confirmar, follow=True)
        self.assertEqual(r.status_code, 200)
        url_formulario = r.redirect_chain[-1][0]

        r = self.client.post(url_formulario, {"new_password1": "ClaveNuevaSegura123", "new_password2": "ClaveNuevaSegura123"})
        self.assertRedirects(r, reverse("password-reset-listo"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveNuevaSegura123"))

    def test_el_link_ya_usado_no_sirve_dos_veces(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url_confirmar = reverse("password-reset-confirmar", kwargs={"uidb64": uid, "token": token})

        url_formulario = self.client.get(url_confirmar, follow=True).redirect_chain[-1][0]
        self.client.post(url_formulario, {"new_password1": "ClaveNuevaSegura123", "new_password2": "ClaveNuevaSegura123"})

        r = self.client.get(url_confirmar, follow=True)
        self.assertContains(r, "ya no es válido")


class ConteosTorreYUnidadTests(TestCase):
    """Torres muestra cuántos deptos y vecinos registrados tiene cada block,
    y Unidades cuántas personas están registradas en cada depto -- antes
    ninguna de las dos pantallas mostraba esos conteos."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Conteos", plan="premium")
        cls.torre_1 = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.torre_2 = Torre.objects.create(condominio=cls.condominio, nombre="2")
        cls.unidad_1_1 = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre_1, numero="1")
        Unidad.objects.create(condominio=cls.condominio, torre=cls.torre_1, numero="2")
        Unidad.objects.create(condominio=cls.condominio, torre=cls.torre_2, numero="1")

    def setUp(self):
        self.client.force_login(crear_devquad("conteos_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        # dos residentes distintos registrados en la misma unidad (ej. pareja)
        crear_membresia(self.condominio, "residente", unidad=self.unidad_1_1, username="conteos_res1")
        crear_membresia(self.condominio, "residente", unidad=self.unidad_1_1, username="conteos_res2")

    def test_torres_muestra_deptos_y_vecinos_por_block(self):
        r = self.client.get(reverse("torres"))
        self.assertEqual(r.status_code, 200)
        torre_1 = next(t for t in r.context["torres"] if t.nombre == "1")
        torre_2 = next(t for t in r.context["torres"] if t.nombre == "2")
        self.assertEqual(torre_1.unidades_count, 2)
        self.assertEqual(torre_1.miembros_count, 2)
        self.assertEqual(torre_2.unidades_count, 1)
        self.assertEqual(torre_2.miembros_count, 0)

    def test_unidades_muestra_personas_registradas_por_depto(self):
        r = self.client.get(reverse("unidades"))
        self.assertEqual(r.status_code, 200)
        unidad = next(u for u in r.context["unidades"] if u.pk == self.unidad_1_1.pk)
        self.assertEqual(unidad.miembros_count, 2)

    def test_unidades_muestra_la_calle_cuando_tiene(self):
        Unidad.objects.create(condominio=self.condominio, numero="99", calle="Los Aromos")
        r = self.client.get(reverse("unidades"))
        self.assertContains(r, "Los Aromos")


class ComoInstalarTests(TestCase):
    """Página de instrucciones de instalación -- abierta sin login (como
    Privacidad/Términos) para poder mandar el link directo por WhatsApp."""

    def test_accesible_sin_login(self):
        r = self.client.get(reverse("como-instalar"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Agregar a pantalla de inicio")
        self.assertContains(r, "iPhone")

    def test_link_visible_para_un_usuario_logueado(self):
        condominio = Condominio.objects.create(nombre="Test Como Instalar", plan="premium")
        membresia = crear_membresia(condominio, "residente", username="como_instalar_residente")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, reverse("como-instalar"))


class PaginasPublicasRenderizanTests(TestCase):
    """Landing, Términos y Privacidad no tenían ningún test que las
    renderizara -- un error de sintaxis en la plantilla solo se habría
    notado en producción. Confirma 200 y que el listado de funciones esté
    al día con lo que existe hoy (ver landing.html)."""

    def test_landing_sin_login_lista_las_funciones_actuales(self):
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Números de emergencia")

    def test_terminos_renderiza(self):
        r = self.client.get(reverse("terminos"))
        self.assertEqual(r.status_code, 200)

    def test_privacidad_renderiza(self):
        r = self.client.get(reverse("privacidad"))
        self.assertEqual(r.status_code, 200)


def crear_devquad(username="devquad_test"):
    """Cuenta devquad -- is_staff, sin Membresia (ver DEVQUAD_CONDOMINIO_SESSION_KEY/condominio_activo_devquad)."""
    return User.objects.create_user(username=username, is_staff=True)


class DevquadCondominiosViewTests(TestCase):
    """Panel de devquad -- lista todos los condominios, sin filtrar por
    tenant (a propósito: devquad opera todos, no uno solo)."""

    def test_sin_login_redirige(self):
        r = self.client.get(reverse("devquad-condominios"))
        self.assertEqual(r.status_code, 302)

    def test_sin_is_staff_es_rechazado(self):
        condominio = Condominio.objects.create(nombre="Rechazo No Staff", plan="premium")
        membresia = crear_membresia(condominio, "residente", unidad=Unidad.objects.create(condominio=condominio, numero="1"))
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("devquad-condominios"), follow=True)
        self.assertRedirects(r, reverse("inicio"))

    def test_is_staff_ve_todos_los_condominios(self):
        Condominio.objects.create(nombre="Condominio Uno Devquad", plan="premium")
        Condominio.objects.create(nombre="Condominio Dos Devquad", plan="premium")
        self.client.force_login(crear_devquad())
        r = self.client.get(reverse("devquad-condominios"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Condominio Uno Devquad")
        self.assertContains(r, "Condominio Dos Devquad")


class DevquadEntrarCondominioViewTests(TestCase):
    """Entrar/salir de un condominio como devquad -- guarda/limpia la
    sesión que CondominioRequiredMixin usa para resolver self.condominio."""

    def test_entrar_guarda_el_condominio_en_sesion_y_redirige_a_inicio(self):
        condominio = Condominio.objects.create(nombre="Entrar Devquad", plan="premium")
        self.client.force_login(crear_devquad())
        r = self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        self.assertRedirects(r, reverse("inicio"))
        self.assertEqual(self.client.session["devquad_condominio_id"], condominio.pk)

    def test_inicio_sin_condominio_activo_redirige_al_listado(self):
        self.client.force_login(crear_devquad())
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("devquad-condominios"))

    def test_inicio_con_condominio_activo_muestra_el_dashboard(self):
        condominio = Condominio.objects.create(nombre="Dashboard Devquad", plan="premium")
        self.client.force_login(crear_devquad())
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Dashboard Devquad")

    def test_aislamiento_entre_condominios(self):
        """Devquad operando en el condominio A no ve datos del condominio B
        hasta cambiar -- ver DevquadCondominiosView/condominio_activo_devquad."""
        a = Condominio.objects.create(nombre="Condominio A Devquad", plan="premium")
        b = Condominio.objects.create(nombre="Condominio B Devquad", plan="premium")
        Torre.objects.create(condominio=a, nombre="Torre A")
        Torre.objects.create(condominio=b, nombre="Torre B")
        self.client.force_login(crear_devquad())

        self.client.get(reverse("devquad-entrar-condominio", args=[a.pk]))
        r = self.client.get(reverse("torres"))
        self.assertContains(r, "Torre A")
        self.assertNotContains(r, "Torre B")

        self.client.get(reverse("devquad-entrar-condominio", args=[b.pk]))
        r = self.client.get(reverse("torres"))
        self.assertContains(r, "Torre B")
        self.assertNotContains(r, "Torre A")

    def test_salir_limpia_la_sesion_y_vuelve_al_listado(self):
        condominio = Condominio.objects.create(nombre="Salir Devquad", plan="premium")
        self.client.force_login(crear_devquad())
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.get(reverse("devquad-salir-condominio"))
        self.assertRedirects(r, reverse("devquad-condominios"))
        self.assertNotIn("devquad_condominio_id", self.client.session)

    def test_condominio_desactivado_redirige_a_cuenta_desactivada(self):
        condominio = Condominio.objects.create(nombre="Desactivado Devquad", plan="premium", activo=False)
        self.client.force_login(crear_devquad())
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("cuenta-desactivada"))


class DevquadCrearCondominioViewTests(TestCase):
    def test_sin_is_staff_no_puede_crear(self):
        condominio = Condominio.objects.create(nombre="No Crear Sin Staff", plan="premium")
        membresia = crear_membresia(condominio, "residente", unidad=Unidad.objects.create(condominio=condominio, numero="1"))
        self.client.force_login(membresia.user)
        r = self.client.post(reverse("devquad-crear-condominio"), {"nombre": "Intento Residente", "etiqueta_organizacion": "Condominio"})
        self.assertFalse(Condominio.objects.filter(nombre="Intento Residente").exists())
        self.assertEqual(r.status_code, 302)

    def test_devquad_crea_un_condominio_y_entra_directo(self):
        self.client.force_login(crear_devquad())
        r = self.client.post(reverse("devquad-crear-condominio"), {
            "nombre": "Nuevo Condominio Devquad", "etiqueta_organizacion": "Condominio",
            "direccion": "Calle Falsa 123", "region": "valparaiso", "comuna": "Valparaíso",
        })
        condominio = Condominio.objects.get(nombre="Nuevo Condominio Devquad")
        self.assertRedirects(r, reverse("devquad-entrar-condominio", args=[condominio.pk]), fetch_redirect_response=False)
