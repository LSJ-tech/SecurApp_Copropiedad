import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .forms import CrearCondominioForm, CrearMiembroForm, RegistroResidenteForm
from .models import Condominio, Membresia, SolicitudAcceso, Torre, Unidad
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

    def test_contrasenas_que_no_coinciden_son_invalidas(self):
        condominio = Condominio.objects.create(nombre="Test Claves No Coinciden", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        form = RegistroResidenteForm(data={
            "nombre": "Rosa", "apellido": "Mena", "email": "rosa_claves@example.com", "unidad": unidad.pk,
            "password1": "unaClaveSegura123", "password2": "otraClaveDistinta456", "acepto_terminos": True,
        }, condominio=condominio)
        self.assertFalse(form.is_valid())
        self.assertIn("Las contraseñas no coinciden.", str(form.errors))


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

    def test_mi_perfil_permite_borrar_el_email(self):
        """email no es obligatorio (ver RegistroResidenteForm -- igual se
        puede crear la cuenta sin), así que borrarlo desde Mi perfil
        tampoco debería exigir que se valide como único."""
        from .forms import MiPerfilForm

        condominio = Condominio.objects.create(nombre="Test Borrar Email Perfil", plan="premium")
        membresia = crear_membresia(condominio, "residente", username="perfil_borra_email", email="tenia@example.com")
        form = MiPerfilForm(
            data={"first_name": membresia.user.first_name or "X", "last_name": membresia.user.last_name or "Y", "email": ""},
            instance=membresia.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "")

    def test_registro_residente_form_sin_condominio_no_rompe(self):
        """Instanciarlo sin el kwarg condominio (ej. en un contexto que
        todavía no resolvió el condominio) no debe fallar -- queda con los
        campos de torre/casa en su estado por defecto, sin acotar."""
        form = RegistroResidenteForm()
        self.assertIsNone(form.condominio)

    def test_unidad_form_con_condominio_acota_las_torres_y_usa_su_etiqueta(self):
        from .forms import UnidadForm

        condominio = Condominio.objects.create(nombre="Test Unidad Form Torre", plan="premium", etiqueta_torre="Block")
        torre = Torre.objects.create(condominio=condominio, nombre="3")
        otro_condominio = Condominio.objects.create(nombre="Test Unidad Form Otro", plan="premium")
        Torre.objects.create(condominio=otro_condominio, nombre="9")

        form = UnidadForm(condominio=condominio)
        self.assertEqual(form.fields["torre"].label, "Block")
        self.assertIn(torre, form.fields["torre"].queryset)
        self.assertEqual(form.fields["torre"].queryset.count(), 1)


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

    def test_muestra_el_medidor_de_seguridad_de_la_contrasena(self):
        r = self.client.get(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}))
        self.assertContains(r, "medidor_contrasena_vivo.js")
        self.assertContains(r, "initMedidorContrasenaVivo")
        self.assertContains(r, "<li>")  # ayudas_contrasena (reglas reales de Django)

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
        # calle_unidad_libre SÍ sigue disponible en modo torres -- un
        # condominio con torres puede además tener casas sueltas (ver
        # AutoregistroMixtoTorresYCasasTests), no son modos excluyentes.
        self.assertIn("calle_unidad_libre", form.fields)
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


class AutoregistroMixtoTorresYCasasTests(TestCase):
    """Un condominio puede tener torres Y casas sueltas al mismo tiempo
    (ej. una junta de vecinos con algunos blocks y además una calle de
    casas) -- no es "modo torres" o "modo casas" excluyentes, Unidad.torre
    ya es opcional por unidad, no por condominio. El selector de torre
    siempre ofrece "sin torre" (aunque todavía no exista ninguna casa
    registrada -- el primer vecino sin torre tiene que poder inaugurar su
    calle igual que puede hacerlo el segundo/tercero)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Mixto Torres y Casas", plan="premium")
        cls.torre1 = Torre.objects.create(condominio=cls.condominio, nombre="1")

    def _datos_base(self, **extra):
        datos = {
            "nombre": "Rosa", "apellido": "Mena", "email": "rosa_mixto@example.com",
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        }
        datos.update(extra)
        return datos

    def test_pagina_ofrece_opcion_sin_torre_aunque_no_exista_ninguna_casa_todavia(self):
        """Cold-start: cero casas registradas todavía, pero la opción debe
        estar igual -- si dependiera de que ya exista una, nadie podría
        ser el primero (ver AutoregistroCasasLibresTests, mismo criterio
        aplicado acá al caso mixto)."""
        r = self.client.get(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'value="sin-torre"')
        self.assertContains(r, "vivo en una casa")

    def test_registrarse_sin_torre_pero_con_calle_crea_una_casa_sin_torre(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(calle_unidad_libre="Los Aromos", numero_unidad_libre="7"),
        )
        self.assertEqual(r.status_code, 302)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="7")
        self.assertIsNone(unidad.torre)
        self.assertEqual(unidad.calle, "Los Aromos")
        user = User.objects.get(email="rosa_mixto@example.com")
        self.assertEqual(user.membresia.unidad, unidad)

    def test_registrarse_con_torre_sigue_funcionando_igual(self):
        """El agregado de calle no debe romper el camino normal de torre."""
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(torre_unidad_libre="1", numero_unidad_libre="302"),
        )
        self.assertEqual(r.status_code, 302)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="302")
        self.assertEqual(unidad.torre, self.torre1)

    def test_sin_torre_ni_calle_no_se_puede_registrar(self):
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(numero_unidad_libre="9"),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Unidad.objects.filter(condominio=self.condominio, numero="9").exists())
        self.assertFalse(User.objects.filter(email="rosa_mixto@example.com").exists())

    def test_elegir_una_casa_sin_torre_ya_existente_de_la_lista(self):
        casa = Unidad.objects.create(condominio=self.condominio, torre=None, numero="7", calle="Los Aromos")
        r = self.client.post(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}),
            self._datos_base(unidad=casa.pk),
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio, numero="7").count(), 1)


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

    @patch("django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("Resend caído"))
    def test_si_el_envio_falla_la_cuenta_se_crea_igual(self, mock_send):
        """El correo de bienvenida nunca debe bloquear el alta -- si Resend
        falla, la cuenta queda creada igual (ver enviar_correo_bienvenida,
        try/except con logger.exception)."""
        r = self.client.post(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}), {
            "nombre": "Carla", "apellido": "Fuentes", "email": "carla@example.com", "unidad": self.unidad.pk,
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(email="carla@example.com").exists())
        mock_send.assert_called_once()


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
        """Un alta manual (ej. un management command o una carga directa por
        admin) puede seguir pasando pagado_hasta=None a propósito si no
        quiere dar el trial -- el default no lo fuerza."""
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

    @patch("django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("Resend caído"))
    def test_si_el_envio_falla_igual_queda_marcada_atendida(self, mock_send):
        solicitud = self._solicitud()
        self._marcar_atendida(solicitud.pk)
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.atendida)
        mock_send.assert_called_once()


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

    def test_filtra_por_busqueda_de_nombre(self):
        condominio = Condominio.objects.create(nombre="Test Filtro Busqueda", plan="premium")
        crear_membresia(condominio, "residente", username="busqueda_rosa", first_name="Rosa", last_name="Mena")
        crear_membresia(condominio, "residente", username="busqueda_juan", first_name="Juan", last_name="Soto")
        self.client.force_login(crear_devquad("filtro_busqueda_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.get(reverse("miembros") + "?q=Rosa")
        nombres = [m.user.get_full_name() for m in r.context["membresias"]]
        self.assertEqual(nombres, ["Rosa Mena"])

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

    def test_el_mensaje_menciona_la_opcion_de_casa_si_el_condominio_tiene_torres(self):
        """El link ya sirve para registrar una casa sin torre (ver
        RegistroResidenteForm, caso mixto) -- pero si el mensaje de
        invitación solo dice "elige tu depto", un vecino que vive en una
        casa (como Andrés/Adela en Empart) no se entera de que el mismo
        link también sirve para él."""
        condominio_con_torre = Condominio.objects.create(nombre="Test Mixto Invitacion", plan="premium")
        Torre.objects.create(condominio=condominio_con_torre, nombre="1")
        membresia = crear_membresia(condominio_con_torre, "residente", username="invitar_mixto")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("compartir-invitacion"))
        self.assertContains(r, "o%20tu%20casa")

    def test_el_mensaje_no_menciona_casa_de_mas_si_el_condominio_no_tiene_torres(self):
        """En un condominio de puras casas (sin ninguna torre) ya no hace
        falta aclarar nada -- decirlo igual sería redundante/confuso."""
        condominio_sin_torre = Condominio.objects.create(nombre="Test Puras Casas Invitacion", plan="premium")
        membresia = crear_membresia(condominio_sin_torre, "residente", username="invitar_puras_casas")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("compartir-invitacion"))
        self.assertNotContains(r, "o%20tu%20casa")


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

    def test_vecino_sin_nombre_cargado_no_muestra_el_username(self):
        """Si el vecino no cargó nombre/apellido, el directorio no debe
        caer al username como respaldo -- eso filtraría su usuario de
        login, justo lo que este directorio dice explícitamente no mostrar
        (ver DirectorioVecinosView, "a propósito NO muestra usuario")."""
        vecino = crear_membresia(
            self.condominio, "residente", unidad=self.unidad, username="directorio_sin_nombre_secreto",
        )
        yo = crear_membresia(self.condominio, "delegado", unidad=self.unidad, username="directorio_yo2")
        self.client.force_login(yo.user)
        r = self.client.get(reverse("directorio"))
        contenido = r.content.decode()
        self.assertNotIn("directorio_sin_nombre_secreto", contenido)
        self.assertIn("Vecino/a", contenido)


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

    def test_usuario_logueado_sin_membresia_ni_staff_no_puede_entrar(self):
        """Caso defensivo -- en teoría toda cuenta real es is_staff (devquad)
        o tiene Membresia, pero el mixin no debe asumirlo ciegamente. Usa
        /invitar/ (solo CondominioRequiredMixin) y no /miembros/ (que
        además lleva SoloStaffMixin, que rechazaría antes por otra razón)."""
        huerfano = User.objects.create_user(username="mixin_sin_nada")
        self.client.force_login(huerfano)
        r = self.client.get(reverse("compartir-invitacion"))
        self.assertRedirects(r, reverse("login"), fetch_redirect_response=False)

    def test_devquad_con_condominio_activo_que_se_desactiva_queda_bloqueado(self):
        condominio = Condominio.objects.create(nombre="Test Devquad Se Desactiva", plan="premium")
        self.client.force_login(crear_devquad("mixin_devquad_se_desactiva"))
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        condominio.activo = False
        condominio.save(update_fields=["activo"])
        r = self.client.get(reverse("miembros"))
        self.assertRedirects(r, reverse("cuenta-desactivada"))


class InicioResidenteCondominioDesactivadoTests(TestCase):
    """InicioView tiene su propia lógica inline de resolución de condominio
    (no usa CondominioRequiredMixin, ver su docstring) -- esta rama
    (residente/delegado cuyo condominio se desactivó) no se cubre desde
    ningún otro test porque CondominioRequiredMixinRamasTests prueba el
    mismo bloqueo pero vía otra vista (/miembros/)."""

    def test_residente_de_condominio_desactivado_va_a_cuenta_desactivada(self):
        condominio = Condominio.objects.create(nombre="Test Inicio Desactivado", plan="premium", activo=False)
        residente = crear_membresia(condominio, "residente", username="inicio_desactivado_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("cuenta-desactivada"))


class AceptarTerminosViewTests(TestCase):
    def test_get_redirige_a_inicio_si_ya_acepto(self):
        condominio = Condominio.objects.create(nombre="Test Terminos Ya Acepto", plan="premium")
        residente = crear_membresia(condominio, "residente", username="terminos_ya_acepto")  # crear_membresia ya pone terminos_aceptados_en
        self.client.force_login(residente.user)
        r = self.client.get(reverse("aceptar-terminos"))
        self.assertRedirects(r, reverse("inicio"))

    def test_get_redirige_a_inicio_si_no_tiene_membresia(self):
        self.client.force_login(crear_devquad("terminos_sin_membresia"))
        r = self.client.get(reverse("aceptar-terminos"))
        # fetch_redirect_response=False: a este devquad sin condominio
        # activo "inicio" lo rebota de nuevo (a devquad-condominios) -- acá
        # solo importa que AceptarTerminosView.get() apunte a "inicio".
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)

    def test_post_sin_membresia_no_rompe(self):
        self.client.force_login(crear_devquad("terminos_post_sin_membresia"))
        r = self.client.post(reverse("aceptar-terminos"), {"acepto": "on"})
        self.assertRedirects(r, reverse("login"))


class MiCambiarContrasenaViewFormValidTests(TestCase):
    def test_post_valido_cambia_la_contrasena_y_redirige(self):
        condominio = Condominio.objects.create(nombre="Test Cambiar Post", plan="premium")
        residente = crear_membresia(
            condominio, "residente", unidad=Unidad.objects.create(condominio=condominio, numero="1"), username="cambiar_post_residente",
        )
        residente.user.set_password("ClaveViejaSegura123")
        residente.user.save()
        self.client.force_login(residente.user)
        r = self.client.post(reverse("cambiar-contrasena"), {
            "old_password": "ClaveViejaSegura123",
            "new_password1": "ClaveNuevaSegura456",
            "new_password2": "ClaveNuevaSegura456",
        })
        self.assertRedirects(r, reverse("mi-perfil"))
        residente.user.refresh_from_db()
        self.assertTrue(residente.user.check_password("ClaveNuevaSegura456"))


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

    def test_muestra_el_medidor_de_seguridad_en_vivo(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url_confirmar = reverse("password-reset-confirmar", kwargs={"uidb64": uid, "token": token})
        r = self.client.get(url_confirmar, follow=True)
        self.assertContains(r, "medidor_contrasena_vivo.js")
        self.assertContains(r, "initMedidorContrasenaVivo")

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

    def test_unidades_filtra_por_torre(self):
        r = self.client.get(reverse("unidades") + f"?torre={self.torre_1.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({u.torre_id for u in r.context["unidades"]}, {self.torre_1.pk})
        self.assertEqual(len(r.context["unidades"]), 2)

    def test_crear_unidad_la_acota_al_condominio_activo(self):
        r = self.client.post(reverse("crear-unidad"), {"numero": "99", "torre": self.torre_1.pk, "alicuota": "0"})
        self.assertEqual(r.status_code, 302)
        unidad = Unidad.objects.get(condominio=self.condominio, numero="99")
        self.assertEqual(unidad.torre_id, self.torre_1.pk)


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

    def test_privacidad_no_afirma_que_la_app_movil_ya_entrega_notificaciones(self):
        """No existe ninguna app móvil (Expo/React Native) en este repo --
        solo el código servidor que la enviaría si existiera. La política
        no debe describir eso en presente como si ya ocurriera hoy."""
        r = self.client.get(reverse("privacidad"))
        contenido = r.content.decode()
        self.assertNotIn("entrega las notificaciones a tu celular", contenido)


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


class SolicitudAccesoRegionComunaTests(TestCase):
    """El formulario público de contacto de la landing (SolicitudAccesoForm)
    usa el mismo patrón de región/comuna con choices reales que ya existe en
    CrearCondominioForm (ver DevquadCrearCondominioViewTests) -- antes era
    texto libre sin validar."""

    def _datos_base(self, **extra):
        datos = {"nombre": "Rosa", "condominio": "Mi Junta de Vecinos", "telefono": "+56912345678"}
        datos.update(extra)
        return datos

    def test_region_y_comuna_que_calzan_son_validas(self):
        from .forms import SolicitudAccesoForm

        form = SolicitudAccesoForm(data=self._datos_base(region="valparaiso", comuna="Valparaíso"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_comuna_que_no_pertenece_a_la_region_es_invalida(self):
        from .forms import SolicitudAccesoForm

        form = SolicitudAccesoForm(data=self._datos_base(region="valparaiso", comuna="Providencia"))
        self.assertFalse(form.is_valid())
        self.assertIn("Esa comuna no pertenece a la región elegida.", form.errors["__all__"])

    def test_region_y_comuna_son_opcionales(self):
        from .forms import SolicitudAccesoForm

        form = SolicitudAccesoForm(data=self._datos_base())
        self.assertTrue(form.is_valid(), form.errors)

    def test_landing_sin_login_muestra_el_selector_de_region_en_cascada(self):
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="id_sol_region"')
        self.assertContains(r, 'id="id_sol_comuna"')
        self.assertContains(r, "Valparaíso")
        self.assertContains(r, "cascada_region_comuna.js")

    def test_post_guarda_la_region_y_la_comuna(self):
        r = self.client.post(
            reverse("solicitar-acceso"),
            self._datos_base(region="valparaiso", comuna="Valparaíso"),
        )
        self.assertEqual(r.status_code, 302)
        solicitud = SolicitudAcceso.objects.get(nombre="Rosa")
        self.assertEqual(solicitud.region, "valparaiso")
        self.assertEqual(solicitud.comuna, "Valparaíso")

    def test_correo_de_aviso_incluye_la_region_legible(self):
        self.client.post(reverse("solicitar-acceso"), self._datos_base(region="valparaiso", comuna="Valparaíso"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Región: Valparaíso", mail.outbox[0].body)

    @patch("core.views.send_mail", side_effect=Exception("Resend caído"))
    def test_si_el_aviso_por_correo_falla_el_lead_queda_guardado_igual(self, mock_send):
        """El correo es solo un aviso a DevQuad -- si falla, el lead (que es
        lo que de verdad importa, alguien pidiendo acceso) no se pierde."""
        r = self.client.post(reverse("solicitar-acceso"), self._datos_base())
        self.assertEqual(r.status_code, 302)
        self.assertTrue(SolicitudAcceso.objects.filter(nombre="Rosa").exists())
        mock_send.assert_called_once()

    def test_datos_invalidos_no_crean_un_lead(self):
        r = self.client.post(reverse("solicitar-acceso"), self._datos_base(telefono=""), follow=True)
        self.assertContains(r, "No pudimos enviar tu solicitud")
        self.assertFalse(SolicitudAcceso.objects.filter(nombre="Rosa").exists())


class MiCambiarContrasenaViewTests(TestCase):
    """Mismo medidor de seguridad en vivo + reglas reales de Django que ya
    se usa en el registro de residente y en recuperar contraseña (ver
    PasswordResetConfirmView) -- acá es la vista para cambiarla ya logueado."""

    def test_muestra_el_medidor_de_seguridad_de_la_contrasena(self):
        condominio = Condominio.objects.create(nombre="Test Cambiar Contrasena", plan="premium")
        membresia = crear_membresia(condominio, "residente", unidad=Unidad.objects.create(condominio=condominio, numero="1"))
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("cambiar-contrasena"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "medidor_contrasena_vivo.js")
        self.assertContains(r, "initMedidorContrasenaVivo")
        self.assertContains(r, "<li>")  # ayudas_contrasena


class CondominioUpdateViewTests(TestCase):
    """/mi-condominio/ antes solo mostraba el QR de autoregistro -- ahora
    también deja editar nombre/dirección/región/comuna/datos de
    transferencia, que antes solo se podían corregir desde el admin."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre="Test Editar Condominio", plan="premium", direccion="Calle Vieja 1", comuna="Valparaíso", region="valparaiso",
        )

    def _login_devquad(self, username="editar_condominio_devquad"):
        self.client.force_login(crear_devquad(username))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_get_muestra_los_datos_actuales_precargados(self):
        self._login_devquad()
        r = self.client.get(reverse("mi-condominio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Calle Vieja 1")
        self.assertContains(r, "Guardar")

    def test_post_actualiza_el_condominio(self):
        self._login_devquad()
        r = self.client.post(reverse("mi-condominio"), {
            "nombre": "Test Editar Condominio", "etiqueta_organizacion": "Junta de vecinos",
            "direccion": "Calle Nueva 2", "region": "metropolitana", "comuna": "Providencia",
            "datos_transferencia": "Banco Estado, cuenta 123",
            "etiqueta_torre": "Torre", "etiqueta_unidad": "Unidad", "genero_unidad": "f",
        })
        self.assertRedirects(r, reverse("mi-condominio"))
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.direccion, "Calle Nueva 2")
        self.assertEqual(self.condominio.region, "metropolitana")
        self.assertEqual(self.condominio.comuna, "Providencia")
        self.assertEqual(self.condominio.etiqueta_organizacion, "Junta de vecinos")
        self.assertEqual(self.condominio.datos_transferencia, "Banco Estado, cuenta 123")

    def test_post_puede_corregir_la_etiqueta_de_unidad(self):
        """Antes la única forma de arreglar una etiqueta_unidad mal escrita
        (ej. "Departamentos" en plural, que termina duplicando la "s" que
        agrega el resto de la app) era un script puntual o el admin de
        Django -- ahora se corrige desde el propio panel."""
        self.condominio.etiqueta_unidad = "Departamentos"
        self.condominio.save(update_fields=["etiqueta_unidad"])
        self._login_devquad()
        r = self.client.post(reverse("mi-condominio"), {
            "nombre": "Test Editar Condominio", "etiqueta_organizacion": "Junta de vecinos",
            "direccion": "Calle Vieja 1", "region": "valparaiso", "comuna": "Valparaíso",
            "etiqueta_torre": "Block", "etiqueta_unidad": "Departamento", "genero_unidad": "m",
        })
        self.assertRedirects(r, reverse("mi-condominio"))
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.etiqueta_torre, "Block")
        self.assertEqual(self.condominio.etiqueta_unidad, "Departamento")
        self.assertEqual(self.condominio.genero_unidad, "m")

    def test_comuna_que_no_calza_con_la_region_es_invalida(self):
        self._login_devquad()
        r = self.client.post(reverse("mi-condominio"), {
            "nombre": "Test Editar Condominio", "etiqueta_organizacion": "Condominio",
            "region": "valparaiso", "comuna": "Providencia",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Esa comuna no pertenece a la región elegida.")
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.comuna, "Valparaíso")  # no se tocó

    def test_un_residente_no_puede_editar(self):
        residente = crear_membresia(self.condominio, "residente", unidad=Unidad.objects.create(condominio=self.condominio, numero="1"))
        self.client.force_login(residente.user)
        r = self.client.post(reverse("mi-condominio"), {"nombre": "Hackeado"})
        self.assertEqual(r.status_code, 302)
        self.condominio.refresh_from_db()
        self.assertNotEqual(self.condominio.nombre, "Hackeado")

    def test_sigue_mostrando_el_qr_de_autoregistro(self):
        self._login_devquad()
        r = self.client.get(reverse("mi-condominio"))
        self.assertContains(r, "Autoregistro de residentes")
        self.assertContains(r, reverse("regenerar-token-residentes"))


class ModelosStrYPropiedadesTests(TestCase):
    """__str__ y propiedades simples de varios modelos -- cada una se prueba
    directo, sin pasar por una vista, porque no todas se renderizan en
    ningún template hoy (ej. SolicitudAcceso.__str__ solo se ve en el
    admin)."""

    def test_etiqueta_unidad_todos_concuerda_en_genero_masculino(self):
        condominio = Condominio.objects.create(nombre="Test Etiqueta Todos M", plan="premium", genero_unidad="m")
        self.assertEqual(condominio.etiqueta_unidad_todos, "TODOS los")

    def test_etiqueta_unidad_todos_concuerda_en_genero_femenino(self):
        condominio = Condominio.objects.create(nombre="Test Etiqueta Todos F", plan="premium", genero_unidad="f")
        self.assertEqual(condominio.etiqueta_unidad_todos, "TODAS las")

    def test_str_de_unidad_con_calle_y_sin_torre(self):
        condominio = Condominio.objects.create(nombre="Test Str Unidad Casa", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, torre=None, numero="45", calle="Los Aromos")
        self.assertEqual(str(unidad), "Los Aromos 45 - Test Str Unidad Casa")

    def test_str_de_unidad_con_torre_usa_las_etiquetas_propias_del_condominio(self):
        """Antes decía "Torre X - Depto Y" fijo, sin importar cómo le dicen
        en ese condominio -- confundía al mostrar la unidad de alguien cuyo
        condominio usa otras palabras (ej. "Block"/"Depto")."""
        condominio = Condominio.objects.create(
            nombre="Test Str Unidad Etiquetas", plan="premium", etiqueta_torre="Block", etiqueta_unidad="Depto",
        )
        torre = Torre.objects.create(condominio=condominio, nombre="2")
        unidad = Unidad.objects.create(condominio=condominio, torre=torre, numero="2")
        self.assertEqual(str(unidad), "Block 2 - Depto 2")

    def test_str_de_solicitud_acceso(self):
        from .models import SolicitudAcceso

        solicitud = SolicitudAcceso.objects.create(nombre="Rosa", condominio="Mi Junta", telefono="+56911111111")
        self.assertEqual(str(solicitud), "Mi Junta (Rosa)")

    def test_str_de_solicitud_eliminacion(self):
        from .models import SolicitudEliminacion

        solicitud = SolicitudEliminacion.objects.create(
            nombre="Juan Pérez", username="jperez", condominio_nombre="Mi Condominio",
        )
        self.assertEqual(str(solicitud), "Juan Pérez (jperez) - Mi Condominio")


class MoverMiembroViewTests(TestCase):
    """Mover una Membresia ya existente a otro condominio -- nunca se borra
    ni se crea una cuenta nueva (Membresia.user es OneToOneField). No toca
    historial (alertas/avisos/pagos quedan donde ocurrieron de verdad) ni
    una donación activa (sigue igual, confirmado con el usuario)."""

    @classmethod
    def setUpTestData(cls):
        cls.origen = Condominio.objects.create(nombre="Test Mover Origen", plan="premium")
        cls.destino = Condominio.objects.create(nombre="Test Mover Destino", plan="premium")
        cls.torre_destino = Torre.objects.create(condominio=cls.destino, nombre="1")
        cls.unidad_destino = Unidad.objects.create(condominio=cls.destino, torre=cls.torre_destino, numero="101")
        cls.unidad_origen = Unidad.objects.create(condominio=cls.origen, numero="1")

    def setUp(self):
        self.miembro = crear_membresia(self.origen, "residente", unidad=self.unidad_origen, username="mover_residente")
        self.client.force_login(crear_devquad("mover_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.origen.pk]))

    def test_residente_no_puede_acceder(self):
        self.client.logout()
        self.client.force_login(self.miembro.user)
        r = self.client.get(reverse("mover-miembro", args=[self.miembro.pk]))
        self.assertEqual(r.status_code, 302)

    def test_get_muestra_el_formulario_con_los_datos_actuales(self):
        r = self.client.get(reverse("mover-miembro", args=[self.miembro.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "mover_residente")  # sin nombre/apellido cargado, cae al username
        self.assertContains(r, self.origen.nombre)

    def test_las_opciones_de_unidad_destino_quedan_ordenadas_por_torre_y_numero(self):
        """Mismo criterio de orden natural que ya usa UnidadListView (por
        largo de nombre y alfabético, no el orden en que se crearon) --
        sin esto "Torre 10" aparecía antes que "Torre 2" (orden de texto)."""
        torre_2 = Torre.objects.create(condominio=self.destino, nombre="2")
        Unidad.objects.create(condominio=self.destino, torre=torre_2, numero="10")
        Unidad.objects.create(condominio=self.destino, torre=torre_2, numero="2")
        r = self.client.get(reverse("mover-miembro", args=[self.miembro.pk]))
        contenido = r.content.decode()
        inicio = contenido.index('id="unidades-por-condominio-data"')
        fin = contenido.index("</script>", inicio)
        bloque = contenido[inicio:fin]
        # Torre "1" (unidad_destino de setUpTestData) antes que Torre "2",
        # y dentro de Torre "2" el depto "2" antes que el "10".
        self.assertLess(bloque.index("Torre 1 -"), bloque.index("Torre 2 - Unidad 2"))
        self.assertLess(bloque.index("Torre 2 - Unidad 2"), bloque.index("Torre 2 - Unidad 10"))

    def test_las_opciones_de_unidad_destino_usan_las_etiquetas_del_condominio_destino(self):
        """El selector de unidad destino mostraba "Torre X - Y" fijo, sin
        importar cómo le dice ESE condominio a sus torres/unidades (ej.
        "Block"/"Depto"). Se arma en JS desde unidades_por_condominio (ver
        get_context_data) -- se verifica en ESE JSON, no en el <select>
        renderizado por Django (que usa Unidad.__str__ igual, pero la
        cascada lo reemplaza entero al cargar la página)."""
        self.destino.etiqueta_torre = "Block"
        self.destino.etiqueta_unidad = "Depto"
        self.destino.save(update_fields=["etiqueta_torre", "etiqueta_unidad"])
        r = self.client.get(reverse("mover-miembro", args=[self.miembro.pk]))
        contenido = r.content.decode()
        inicio = contenido.index('id="unidades-por-condominio-data"')
        fin = contenido.index("</script>", inicio)
        self.assertIn("Block 1 - Depto 101", contenido[inicio:fin])

    def test_post_mueve_la_membresia_sin_crear_una_nueva(self):
        pk_original = self.miembro.pk
        r = self.client.post(reverse("mover-miembro", args=[self.miembro.pk]), {
            "condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk,
        })
        self.assertRedirects(r, reverse("miembros"))
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.pk, pk_original)
        self.assertEqual(self.miembro.condominio_id, self.destino.pk)
        self.assertEqual(self.miembro.unidad_id, self.unidad_destino.pk)
        self.assertEqual(Membresia.objects.filter(user=self.miembro.user).count(), 1)

    def test_unidad_de_un_tercer_condominio_es_invalida(self):
        """La unidad no solo tiene que ser de OTRO condominio (eso ya lo
        filtra el queryset del campo) -- tiene que ser del mismo condominio
        que se eligió como destino, no de un tercero cualquiera."""
        tercero = Condominio.objects.create(nombre="Test Mover Tercero", plan="premium")
        unidad_tercero = Unidad.objects.create(condominio=tercero, numero="9")
        r = self.client.post(reverse("mover-miembro", args=[self.miembro.pk]), {
            "condominio_destino": self.destino.pk, "unidad_destino": unidad_tercero.pk,
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Esa unidad no pertenece al condominio destino elegido.")
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.condominio_id, self.origen.pk)

    def test_unidad_del_condominio_de_origen_no_es_una_opcion_valida(self):
        otra_unidad_origen = Unidad.objects.create(condominio=self.origen, numero="2")
        r = self.client.post(reverse("mover-miembro", args=[self.miembro.pk]), {
            "condominio_destino": self.destino.pk, "unidad_destino": otra_unidad_origen.pk,
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "no está entre las disponibles")
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.condominio_id, self.origen.pk)

    def test_no_se_puede_mover_un_miembro_de_otro_condominio_activo(self):
        """Seguridad: el pk de la URL no alcanza -- el miembro tiene que
        pertenecer al condominio que devquad tiene activo ahora mismo."""
        otro_condominio = Condominio.objects.create(nombre="Test Mover Ajeno", plan="premium")
        ajeno = crear_membresia(otro_condominio, "residente", username="mover_ajeno")
        r = self.client.get(reverse("mover-miembro", args=[ajeno.pk]))
        self.assertEqual(r.status_code, 404)

    def test_no_toca_el_historial_de_alertas_del_condominio_viejo(self):
        from alertas.models import Alerta

        alerta = Alerta.objects.create(condominio=self.origen, autor=self.miembro, tipo="robo", estado="resuelta")
        self.client.post(reverse("mover-miembro", args=[self.miembro.pk]), {
            "condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk,
        })
        alerta.refresh_from_db()
        self.assertEqual(alerta.condominio_id, self.origen.pk)

    def test_no_toca_una_donacion_activa(self):
        from pagos.models import SuscripcionRecurrente

        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=self.origen, membresia=self.miembro, tipo="donacion", monto=2000,
            mercadopago_preapproval_id="pre-mover-1", estado="autorizada",
        )
        self.client.post(reverse("mover-miembro", args=[self.miembro.pk]), {
            "condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk,
        })
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.condominio_id, self.origen.pk)
        self.assertEqual(suscripcion.estado, "autorizada")

    def test_la_lista_de_miembros_ofrece_el_link_para_mover(self):
        r = self.client.get(reverse("miembros"))
        self.assertContains(r, reverse("mover-miembro", args=[self.miembro.pk]))

    def test_no_mueve_a_otro_miembro_que_comparte_la_misma_unidad(self):
        """Mover a una persona es por Membresia, no por Unidad -- si dos
        residentes comparten la misma unidad (ej. pareja en el mismo
        depto), mover a uno NO debe mover al otro ni tocar la Unidad
        compartida."""
        companero = crear_membresia(self.origen, "residente", unidad=self.unidad_origen, username="mover_companero")
        self.client.post(reverse("mover-miembro", args=[self.miembro.pk]), {
            "condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk,
        })
        companero.refresh_from_db()
        self.unidad_origen.refresh_from_db()
        self.assertEqual(companero.condominio_id, self.origen.pk)
        self.assertEqual(companero.unidad_id, self.unidad_origen.pk)
        self.assertEqual(self.unidad_origen.condominio_id, self.origen.pk)


class CondominioDeLaApiClaimJwtTests(TestCase):
    def test_devquad_con_claim_condominio_id_en_el_token_resuelve_ese_condominio(self):
        from rest_framework.test import APIRequestFactory

        from core.permissions import condominio_de_la_api

        condominio = Condominio.objects.create(nombre="Test Claim JWT", plan="premium")
        devquad = crear_devquad("claim_jwt_devquad")
        token = AccessToken.for_user(devquad)
        token["condominio_id"] = condominio.pk

        request = APIRequestFactory().get("/")
        request.user = devquad
        request.auth = token
        self.assertEqual(condominio_de_la_api(request), condominio)

    def test_devquad_sin_claim_sigue_resolviendo_por_sesion_web(self):
        """SessionAuthentication (el panel web) no setea request.auth a un
        Token -- tiene que seguir funcionando igual que hoy."""
        from rest_framework.test import APIRequestFactory

        from core.permissions import condominio_de_la_api

        condominio = Condominio.objects.create(nombre="Test Claim Sesion", plan="premium")
        devquad = crear_devquad("claim_sesion_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))

        request = APIRequestFactory().get("/")
        request.user = devquad
        request.auth = None
        request.session = self.client.session
        self.assertEqual(condominio_de_la_api(request), condominio)


class DevquadCondominioActivoApiTests(TestCase):
    def test_lista_todos_los_condominios(self):
        Condominio.objects.create(nombre="Test Lista Api A", plan="premium")
        Condominio.objects.create(nombre="Test Lista Api B", plan="premium")
        devquad = crear_devquad("lista_api_devquad")
        self.client.force_login(devquad)
        r = self.client.get(reverse("api-devquad-condominios"))
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 2)

    def test_un_residente_no_puede_listar(self):
        condominio = Condominio.objects.create(nombre="Test Lista Api Residente", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        residente = crear_membresia(condominio, "residente", unidad=unidad, username="lista_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-devquad-condominios"))
        self.assertEqual(r.status_code, 403)

    def test_entrar_devuelve_tokens_nuevos_con_el_condominio_en_el_claim(self):
        condominio = Condominio.objects.create(nombre="Test Entrar Api", plan="premium")
        devquad = crear_devquad("entrar_api_devquad")
        refresh = RefreshToken.for_user(devquad)
        r = self.client.post(
            reverse("api-devquad-entrar-condominio", args=[condominio.pk]),
            {"refresh": str(refresh)}, content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        access_nuevo = AccessToken(datos["access"])
        self.assertEqual(access_nuevo["condominio_id"], condominio.pk)
        self.assertEqual(datos["condominio"]["id"], condominio.pk)

    def test_el_claim_sobrevive_a_un_refresh_posterior_de_verdad(self):
        """No alcanza con que el access recién emitido tenga el claim --
        tiene que seguir ahí después de un /auth/refresh/ real (recorrido
        completo vía HTTP, no armado a mano), que es lo que de verdad usa
        la app cuando el access de 30 min expira."""
        condominio = Condominio.objects.create(nombre="Test Entrar Refresh Real", plan="premium")
        devquad = crear_devquad("entrar_refresh_real_devquad")
        refresh_inicial = RefreshToken.for_user(devquad)
        r_entrar = self.client.post(
            reverse("api-devquad-entrar-condominio", args=[condominio.pk]),
            {"refresh": str(refresh_inicial)}, content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {refresh_inicial.access_token}",
        )
        refresh_con_claim = r_entrar.json()["refresh"]

        r_refresh = self.client.post(reverse("api-refresh"), {"refresh": refresh_con_claim}, content_type="application/json")
        self.assertEqual(r_refresh.status_code, 200)
        access_refrescado = AccessToken(r_refresh.json()["access"])
        self.assertEqual(access_refrescado["condominio_id"], condominio.pk)

        # Y ese access refrescado de verdad sirve para pegarle a un
        # endpoint de devquad -- no solo tiene el claim, resuelve el
        # condominio activo correcto.
        r_torres = self.client.get(reverse("torre-list"), HTTP_AUTHORIZATION=f"Bearer {access_refrescado}")
        self.assertEqual(r_torres.status_code, 200)

    def test_entrar_blacklistea_el_refresh_recibido(self):
        condominio = Condominio.objects.create(nombre="Test Entrar Blacklist", plan="premium")
        devquad = crear_devquad("entrar_blacklist_devquad")
        refresh = RefreshToken.for_user(devquad)
        self.client.post(
            reverse("api-devquad-entrar-condominio", args=[condominio.pk]),
            {"refresh": str(refresh)}, content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        r2 = self.client.post(reverse("api-refresh"), {"refresh": str(refresh)}, content_type="application/json")
        self.assertEqual(r2.status_code, 401)

    def test_entrar_no_puede_blacklistear_el_refresh_de_otro_usuario(self):
        """Un devquad autenticado con SU PROPIO access token no debe poder
        invalidar la sesión de otro usuario mandando el refresh de esa otra
        persona en el body -- eso la dejaría desconectada sin haber hecho
        nada."""
        condominio = Condominio.objects.create(nombre="Test Entrar Refresh Ajeno", plan="premium")
        devquad = crear_devquad("entrar_ajeno_devquad")
        otro_usuario = crear_devquad("entrar_ajeno_otro")
        mi_refresh = RefreshToken.for_user(devquad)
        refresh_ajeno = RefreshToken.for_user(otro_usuario)
        r = self.client.post(
            reverse("api-devquad-entrar-condominio", args=[condominio.pk]),
            {"refresh": str(refresh_ajeno)}, content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {mi_refresh.access_token}",
        )
        self.assertEqual(r.status_code, 400)
        r2 = self.client.post(reverse("api-refresh"), {"refresh": str(refresh_ajeno)}, content_type="application/json")
        self.assertEqual(r2.status_code, 200)  # el refresh ajeno sigue vivo


class DirectorioApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Directorio Api", plan="premium")

    def test_un_residente_no_puede_ver_el_directorio(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        residente = crear_membresia(self.condominio, "residente", unidad=unidad, username="dir_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-directorio"))
        self.assertEqual(r.status_code, 403)

    def test_un_delegado_ve_nombre_torre_y_unidad(self):
        torre = Torre.objects.create(condominio=self.condominio, nombre="1")
        unidad = Unidad.objects.create(condominio=self.condominio, torre=torre, numero="101")
        vecino = crear_membresia(self.condominio, "residente", unidad=unidad, username="dir_api_vecino", first_name="Ana", last_name="Soto")
        delegado = crear_membresia(self.condominio, "delegado", unidad=unidad, username="dir_api_delegado")
        self.client.force_login(delegado.user)
        r = self.client.get(reverse("api-directorio"))
        self.assertEqual(r.status_code, 200)
        fila = next(f for f in r.json() if f["nombre"] == "Ana Soto")
        self.assertEqual(fila["torre"], "1")
        self.assertEqual(fila["unidad"], "101")


class CondominioApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre="Test Condominio Api", plan="premium", direccion="Calle Vieja 1", comuna="Valparaíso", region="valparaiso",
        )

    def _login_devquad(self):
        devquad = crear_devquad("condominio_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_get_devuelve_los_datos_actuales(self):
        self._login_devquad()
        r = self.client.get(reverse("api-condominio"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["direccion"], "Calle Vieja 1")

    def test_patch_actualiza_solo_los_campos_mandados(self):
        self._login_devquad()
        r = self.client.patch(reverse("api-condominio"), {"direccion": "Calle Nueva 2"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.direccion, "Calle Nueva 2")
        self.assertEqual(self.condominio.nombre, "Test Condominio Api")

    def test_patch_con_comuna_que_no_calza_con_la_region_es_invalido(self):
        self._login_devquad()
        r = self.client.patch(
            reverse("api-condominio"), {"region": "valparaiso", "comuna": "Providencia"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.comuna, "Valparaíso")

    def test_patch_con_region_inventada_es_invalido(self):
        """region/comuna son CharField libres en el modelo -- sin validar
        contra la lista real, el PATCH aceptaba cualquier texto (el form
        HTML sí usa ChoiceField, ver RegionComunaMixin)."""
        self._login_devquad()
        r = self.client.patch(reverse("api-condominio"), {"region": "narnia"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.region, "valparaiso")

    def test_patch_con_region_inventada_es_invalido_incluso_sin_comuna_previa(self):
        """Mismo caso que arriba, pero con un condominio que todavía no
        tenía ninguna comuna cargada -- la validación cruzada (región vs.
        comuna) no alcanza a pescar esto si las dos quedan vacías."""
        condominio = Condominio.objects.create(nombre="Test Region Sin Comuna Previa", plan="premium")
        devquad = crear_devquad("region_sin_comuna_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))
        r = self.client.patch(reverse("api-condominio"), {"region": "narnia"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        condominio.refresh_from_db()
        self.assertEqual(condominio.region, "")

    def test_patch_con_comuna_inventada_es_invalido(self):
        self._login_devquad()
        r = self.client.patch(reverse("api-condominio"), {"comuna": "Comuna Que No Existe"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.comuna, "Valparaíso")

    def test_un_residente_no_puede_ver_ni_editar(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        residente = crear_membresia(self.condominio, "residente", unidad=unidad, username="condominio_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-condominio"))
        self.assertEqual(r.status_code, 403)

    def test_regenerar_token_cambia_el_token(self):
        self._login_devquad()
        token_anterior = self.condominio.token_registro_residentes
        r = self.client.post(reverse("api-regenerar-token"))
        self.assertEqual(r.status_code, 200)
        self.condominio.refresh_from_db()
        self.assertNotEqual(self.condominio.token_registro_residentes, token_anterior)
        self.assertEqual(r.json()["token_registro_residentes"], self.condominio.token_registro_residentes)


class InvitacionApiTests(TestCase):
    def test_devuelve_el_link_y_el_mensaje(self):
        condominio = Condominio.objects.create(nombre="Test Invitacion Api", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        residente = crear_membresia(condominio, "residente", unidad=unidad, username="invitacion_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-invitacion"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(condominio.token_registro_residentes, r.json()["link_autoregistro"])


class RegistroPublicoApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Registro Publico Api", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="101")

    def test_get_devuelve_las_unidades_disponibles(self):
        r = self.client.get(reverse("api-registro", args=[self.condominio.token_registro_residentes]))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertEqual(datos["condominio"]["nombre"], "Test Registro Publico Api")
        self.assertEqual(len(datos["unidades"]), 1)

    def test_token_invalido_da_404(self):
        r = self.client.get(reverse("api-registro", args=["token-que-no-existe"]))
        self.assertEqual(r.status_code, 404)

    def test_post_crea_la_cuenta_y_devuelve_tokens(self):
        r = self.client.post(
            reverse("api-registro", args=[self.condominio.token_registro_residentes]),
            {
                "nombre": "Pedro", "apellido": "Pérez", "email": "pedro.registro.api@example.com",
                "unidad": self.unidad.pk, "password1": "ClaveSegura123", "password2": "ClaveSegura123",
                "acepto_terminos": True,
            },
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        datos = r.json()
        self.assertTrue(datos["access"])
        membresia = Membresia.objects.get(user__username=datos["username"])
        self.assertEqual(membresia.condominio, self.condominio)
        self.assertEqual(membresia.unidad, self.unidad)

    def test_post_con_datos_invalidos_devuelve_400(self):
        r = self.client.post(
            reverse("api-registro", args=[self.condominio.token_registro_residentes]),
            {"nombre": "Pedro"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_si_falla_crear_la_membresia_no_queda_un_user_huerfano(self):
        """create_user() y Membresia.objects.create() tienen que ser
        atómicos -- sin eso, si el segundo paso falla, queda una cuenta sin
        ninguna membresía a la que nadie podría acceder normalmente."""
        usuarios_antes = User.objects.count()
        with patch("core.api_views.Membresia.objects.create", side_effect=Exception("falla simulada")):
            with self.assertRaises(Exception):
                self.client.post(
                    reverse("api-registro", args=[self.condominio.token_registro_residentes]),
                    {
                        "nombre": "Ana", "apellido": "Soto", "email": "ana.huerfano.api@example.com",
                        "unidad": self.unidad.pk, "password1": "ClaveSegura123", "password2": "ClaveSegura123",
                        "acepto_terminos": True,
                    },
                    content_type="application/json",
                )
        self.assertEqual(User.objects.count(), usuarios_antes)


class TorreApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Torre Api", plan="premium")

    def _login_devquad(self):
        devquad = crear_devquad("torre_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_lista_solo_las_torres_del_condominio_activo(self):
        Torre.objects.create(condominio=self.condominio, nombre="1")
        otro = Condominio.objects.create(nombre="Test Torre Api Otro", plan="premium")
        Torre.objects.create(condominio=otro, nombre="Ajena")
        self._login_devquad()
        r = self.client.get(reverse("torre-list"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        nombres = [t["nombre"] for t in datos["results"]] if isinstance(datos, dict) else [t["nombre"] for t in datos]
        self.assertEqual(nombres, ["1"])

    def test_crear_una_torre(self):
        self._login_devquad()
        r = self.client.post(reverse("torre-list"), {"nombre": "2"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Torre.objects.filter(condominio=self.condominio, nombre="2").exists())

    def test_un_residente_no_puede_crear(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        residente = crear_membresia(self.condominio, "residente", unidad=unidad, username="torre_api_residente")
        self.client.force_login(residente.user)
        r = self.client.post(reverse("torre-list"), {"nombre": "3"}, content_type="application/json")
        self.assertEqual(r.status_code, 403)


class UnidadApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Unidad Api", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="1")

    def _login_devquad(self):
        devquad = crear_devquad("unidad_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_crear_una_unidad(self):
        self._login_devquad()
        r = self.client.post(
            reverse("unidad-list"), {"numero": "101", "torre": self.torre.pk, "calle": "", "alicuota": "0"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Unidad.objects.filter(condominio=self.condominio, numero="101").exists())

    def test_una_torre_de_otro_condominio_es_invalida(self):
        otro = Condominio.objects.create(nombre="Test Unidad Api Otro", plan="premium")
        torre_ajena = Torre.objects.create(condominio=otro, nombre="Ajena")
        self._login_devquad()
        r = self.client.post(
            reverse("unidad-list"), {"numero": "102", "torre": torre_ajena.pk}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Unidad.objects.filter(numero="102").exists())

    def test_crear_una_unidad_repetida_da_400_no_500(self):
        Unidad.objects.create(condominio=self.condominio, torre=self.torre, numero="101")
        self._login_devquad()
        r = self.client.post(
            reverse("unidad-list"), {"numero": "101", "torre": self.torre.pk, "calle": "", "alicuota": "0"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio, torre=self.torre, numero="101").count(), 1)

    def test_lista_paginada(self):
        for i in range(55):
            Unidad.objects.create(condominio=self.condominio, numero=str(i))
        self._login_devquad()
        r = self.client.get(reverse("unidad-list"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertIn("results", datos)
        self.assertEqual(len(datos["results"]), 50)

    def test_lista_en_orden_natural_no_lexicografico(self):
        """Unidad.Meta.ordering=["numero"] es orden de texto -- "10" sale
        antes que "2". El panel web (UnidadListView) usa orden natural (por
        largo y alfabético); la API tiene que dar lo mismo, para que la app
        no muestre un orden distinto al que ya conoce quien usa la web."""
        Unidad.objects.create(condominio=self.condominio, torre=self.torre, numero="10")
        Unidad.objects.create(condominio=self.condominio, torre=self.torre, numero="2")
        self._login_devquad()
        r = self.client.get(reverse("unidad-list"))
        numeros = [u["numero"] for u in r.json()["results"]]
        self.assertEqual(numeros.index("2"), 0)
        self.assertEqual(numeros.index("10"), 1)


class MembresiaApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Membresia Api", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="1")

    def _login_devquad(self):
        devquad = crear_devquad("membresia_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_lista_los_miembros_del_condominio_activo(self):
        crear_membresia(self.condominio, "residente", unidad=self.unidad, username="membresia_api_vecino", first_name="Rosa", last_name="Diaz")
        self._login_devquad()
        r = self.client.get(reverse("membresia-list"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()["results"]
        fila = next(f for f in datos if f["nombre"] == "Rosa Diaz")
        self.assertEqual(fila["unidad_numero"], "1")

    def test_crear_un_miembro_nuevo(self):
        self._login_devquad()
        r = self.client.post(
            reverse("membresia-list"),
            {"nombre": "Luis", "apellido": "Rojas", "email": "luis.membresia.api@example.com", "rol": "residente", "unidad": self.unidad.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        datos = r.json()
        self.assertTrue(datos["password_temporal"])
        membresia = Membresia.objects.get(pk=datos["id"])
        self.assertEqual(membresia.condominio, self.condominio)
        self.assertEqual(membresia.unidad, self.unidad)

    def test_crear_residente_sin_unidad_da_400(self):
        self._login_devquad()
        r = self.client.post(
            reverse("membresia-list"),
            {"nombre": "Luis", "apellido": "Rojas", "email": "luis2.membresia.api@example.com", "rol": "residente"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_un_residente_no_puede_listar_ni_crear(self):
        residente = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="membresia_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("membresia-list"))
        self.assertEqual(r.status_code, 403)


class MoverMiembroApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origen = Condominio.objects.create(nombre="Test Mover Api Origen", plan="premium")
        cls.destino = Condominio.objects.create(nombre="Test Mover Api Destino", plan="premium")
        cls.unidad_origen = Unidad.objects.create(condominio=cls.origen, numero="1")
        cls.unidad_destino = Unidad.objects.create(condominio=cls.destino, numero="101")

    def setUp(self):
        self.miembro = crear_membresia(self.origen, "residente", unidad=self.unidad_origen, username="mover_api_residente")
        self.client.force_login(crear_devquad("mover_api_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.origen.pk]))

    def test_mueve_la_membresia_sin_crear_una_nueva(self):
        r = self.client.patch(
            reverse("membresia-mover", args=[self.miembro.pk]),
            {"condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.condominio, self.destino)
        self.assertEqual(self.miembro.unidad, self.unidad_destino)
        self.assertEqual(Membresia.objects.filter(user=self.miembro.user).count(), 1)

    def test_unidad_que_no_es_del_condominio_destino_da_400(self):
        tercero = Condominio.objects.create(nombre="Test Mover Api Tercero", plan="premium")
        unidad_tercero = Unidad.objects.create(condominio=tercero, numero="9")
        r = self.client.patch(
            reverse("membresia-mover", args=[self.miembro.pk]),
            {"condominio_destino": self.destino.pk, "unidad_destino": unidad_tercero.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_miembro_de_otro_condominio_da_404(self):
        otro = Condominio.objects.create(nombre="Test Mover Api Ajeno", plan="premium")
        ajeno = crear_membresia(otro, "residente", username="mover_api_ajeno")
        r = self.client.patch(
            reverse("membresia-mover", args=[ajeno.pk]),
            {"condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 404)


class MembresiaTelefonoTests(TestCase):
    def test_telefono_es_opcional_y_vacio_por_defecto(self):
        condominio = Condominio.objects.create(nombre="Test Telefono Default", plan="premium")
        membresia = crear_membresia(condominio, "residente", unidad=Unidad.objects.create(condominio=condominio, numero="1"))
        self.assertEqual(membresia.telefono, "")


class MiPerfilTelefonoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Mi Perfil Telefono", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="1")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="mi_perfil_tel", email="tel@example.com")
        self.client.force_login(self.membresia.user)

    def test_get_precarga_el_telefono_actual(self):
        self.membresia.telefono = "+56911112222"
        self.membresia.save(update_fields=["telefono"])
        r = self.client.get(reverse("mi-perfil"))
        self.assertContains(r, "+56911112222")

    def test_post_actualiza_el_telefono(self):
        r = self.client.post(reverse("mi-perfil"), {
            "first_name": "Mi", "last_name": "Perfil", "email": "tel@example.com", "telefono": "+56933334444",
        })
        self.assertRedirects(r, reverse("mi-perfil"))
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.telefono, "+56933334444")

    def test_post_sin_telefono_lo_deja_vacio_no_falla(self):
        r = self.client.post(reverse("mi-perfil"), {
            "first_name": "Mi", "last_name": "Perfil", "email": "tel@example.com", "telefono": "",
        })
        self.assertRedirects(r, reverse("mi-perfil"))
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.telefono, "")
