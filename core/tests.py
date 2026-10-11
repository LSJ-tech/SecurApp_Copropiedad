from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import CrearMiembroForm, RegistroCondominioForm, RegistroResidenteForm
from .models import CodigoInvitacion, Condominio, Membresia, Torre, Unidad


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
    unidades), lo exclusivo de directiva (Mi condominio) y lo exclusivo del
    admin de la plataforma (crear torre)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Roles", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="101")

    def setUp(self):
        self.directiva = crear_membresia(self.condominio, "directiva", username="roles_directiva")
        self.administracion = crear_membresia(self.condominio, "administracion", username="roles_admon")
        self.conserje = crear_membresia(self.condominio, "conserje", username="roles_conserje")
        self.residente = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="roles_residente")

    def _login(self, membresia):
        self.client.force_login(membresia.user)

    def test_dia_a_dia_directiva_y_administracion_permitido(self):
        for membresia in (self.directiva, self.administracion):
            self._login(membresia)
            for url_name in ("miembros", "torres", "unidades", "gastos-comunes-list"):
                r = self.client.get(reverse(url_name))
                self.assertEqual(r.status_code, 200, f"{membresia.rol} debería poder ver {url_name}")
            self.client.logout()

    def test_dia_a_dia_bloqueado_para_conserje_y_residente(self):
        for membresia in (self.conserje, self.residente):
            self._login(membresia)
            for url_name in ("miembros", "torres", "unidades", "gastos-comunes-list"):
                r = self.client.get(reverse(url_name))
                self.assertEqual(r.status_code, 302, f"{membresia.rol} NO debería poder ver {url_name}")
            self.client.logout()

    def test_accesos_permitido_para_directiva_administracion_conserje(self):
        for membresia in (self.directiva, self.administracion, self.conserje):
            self._login(membresia)
            r = self.client.get(reverse("registro-ingreso-list"))
            self.assertEqual(r.status_code, 200)
            self.client.logout()

    def test_accesos_bloqueado_para_residente(self):
        self._login(self.residente)
        r = self.client.get(reverse("registro-ingreso-list"))
        self.assertEqual(r.status_code, 302)

    def test_mi_condominio_exclusivo_directiva(self):
        self._login(self.directiva)
        self.assertEqual(self.client.get(reverse("mi-condominio")).status_code, 200)
        self.client.logout()
        self._login(self.administracion)
        self.assertEqual(self.client.get(reverse("mi-condominio")).status_code, 302)

    def test_crear_torre_exclusivo_del_admin_de_la_plataforma(self):
        """Ni siquiera la directiva puede crear torres -- eso es de DevQuad (/admin)."""
        for membresia in (self.directiva, self.administracion):
            self._login(membresia)
            r = self.client.post(reverse("crear-torre"), {"nombre": "Nueva"})
            self.assertEqual(r.status_code, 302)
            self.client.logout()
        self.assertEqual(Torre.objects.filter(condominio=self.condominio, nombre="Nueva").count(), 0)

    def test_crear_miembro_form_rol_aware(self):
        """Administración no puede nombrar directiva/administración, directiva sí."""
        form_admon = CrearMiembroForm(condominio=self.condominio, creador_rol="administracion")
        self.assertEqual([c[0] for c in form_admon.fields["rol"].choices], ["conserje", "residente"])

        form_directiva = CrearMiembroForm(condominio=self.condominio, creador_rol="directiva")
        choices_directiva = [c[0] for c in form_directiva.fields["rol"].choices]
        self.assertIn("directiva", choices_directiva)
        self.assertIn("administracion", choices_directiva)

    def test_crear_miembro_residente_exige_unidad(self):
        form = CrearMiembroForm(
            data={"nombre": "Ana", "apellido": "Soto", "email": "ana@example.com", "rol": "residente"},
            condominio=self.condominio, creador_rol="directiva",
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

    def test_conserje_sin_unidad_es_valido(self):
        user = User.objects.create(username="conserje_sin_unidad")
        m = Membresia(user=user, condominio=self.cond1, rol="conserje", unidad=None)
        m.full_clean()  # no debe lanzar

    def test_residente_con_unidad_correcta_es_valido(self):
        user = User.objects.create(username="residente_ok")
        m = Membresia(user=user, condominio=self.cond1, rol="residente", unidad=self.unidad_cond1)
        m.full_clean()  # no debe lanzar


class TerminosAceptacionTests(TestCase):
    """El gate de Términos de Uso / Política de Privacidad: nadie debería
    poder usar una página protegida sin haber aceptado, pero tampoco debería
    quedar atrapado sin poder cerrar sesión (commit b58ea4e)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Terminos", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "directiva", terminos=False, username="pendiente_terminos")
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

    def test_registro_condominio_exige_checkbox(self):
        codigo = CodigoInvitacion.objects.create()
        datos = {
            "codigo_invitacion": codigo.codigo, "nombre_condominio": "Nuevo Condo",
            "nombre": "Logan", "apellido": "Test",
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123",
        }
        form_sin_checkbox = RegistroCondominioForm(data=datos)
        self.assertFalse(form_sin_checkbox.is_valid())

        datos["acepto_terminos"] = True
        form_con_checkbox = RegistroCondominioForm(data=datos)
        self.assertTrue(form_con_checkbox.is_valid(), form_con_checkbox.errors)

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
        directiva = crear_membresia(self.condominio, "directiva", username="bienvenida_directiva")
        self.client.force_login(directiva.user)
        r = self.client.post(reverse("crear-miembro"), {
            "nombre": "Juan", "apellido": "Perez", "email": "juan@example.com", "rol": "conserje",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["juan@example.com"])

    def test_crear_miembro_sin_email_no_crea_la_cuenta(self):
        directiva = crear_membresia(self.condominio, "directiva", username="bienvenida_directiva3")
        self.client.force_login(directiva.user)
        r = self.client.post(reverse("crear-miembro"), {"nombre": "Luis", "apellido": "Rojas", "rol": "conserje"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(first_name="Luis").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_el_correo_de_bienvenida_nunca_incluye_la_contrasena(self):
        directiva = crear_membresia(self.condominio, "directiva", username="bienvenida_directiva2")
        self.client.force_login(directiva.user)
        self.client.post(reverse("crear-miembro"), {
            "nombre": "Pedro", "apellido": "Diaz", "email": "pedro@example.com", "rol": "conserje",
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

    def test_directiva_no_puede_crear_miembro_con_email_repetido(self):
        directiva = crear_membresia(self.condominio, "directiva", username="email_unico_directiva")
        self.client.force_login(directiva.user)
        r = self.client.post(reverse("crear-miembro"), {
            "nombre": "Juan", "apellido": "Perez", "email": "repetido@example.com", "rol": "conserje",
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

    def test_registro_self_service_tambien_trae_la_prueba_gratis(self):
        codigo = CodigoInvitacion.objects.create()
        r = self.client.post(reverse("registro-condominio"), {
            "codigo_invitacion": codigo.codigo, "nombre_condominio": "Condo Prueba Self Service",
            "nombre": "Logan", "apellido": "Test",
            "password1": "unaClaveSegura123", "password2": "unaClaveSegura123",
            "acepto_terminos": True,
        })
        self.assertEqual(r.status_code, 302)
        condominio = Condominio.objects.get(nombre="Condo Prueba Self Service")
        self.assertIsNotNone(condominio.pagado_hasta)
        self.assertGreaterEqual(condominio.pagado_hasta, timezone.localdate())

    def test_se_puede_crear_sin_prueba_explicitamente(self):
        """Los management commands de alta manual (ej. crear_condominio_empart)
        pueden seguir pasando pagado_hasta=None a propósito si no quieren dar
        el trial -- el default no lo fuerza."""
        condominio = Condominio.objects.create(nombre="Test Sin Prueba", plan="premium", pagado_hasta=None)
        self.assertIsNone(condominio.pagado_hasta)


class DonacionVisibilidadTests(TestCase):
    """La donación es exclusiva de residentes -- directiva/administración solo
    ven la suscripción (que es la que de verdad pagan), y conserjería no ve
    ninguna de las dos (no le corresponde ninguno de los dos pagos)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Donacion Visibilidad", plan="premium")

    def test_administracion_no_ve_la_tarjeta_de_donacion(self):
        membresia = crear_membresia(self.condominio, "administracion", username="donvis_admon")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"Apoya el proyecto", r.content)
        self.assertIn("Suscripción de".encode(), r.content)

    def test_directiva_no_ve_la_tarjeta_de_donacion(self):
        membresia = crear_membresia(self.condominio, "directiva", username="donvis_directiva")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"Apoya el proyecto", r.content)

    def test_residente_si_ve_la_tarjeta_de_donacion(self):
        membresia = crear_membresia(self.condominio, "residente", username="donvis_residente")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Apoya el proyecto", r.content)

    def test_conserje_no_ve_la_tarjeta_de_donacion(self):
        membresia = crear_membresia(self.condominio, "conserje", username="donvis_conserje")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"Apoya el proyecto", r.content)


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


class InicioViewTests(TestCase):
    """Ramas de InicioView no cubiertas por el resto de los tests: staff sin
    membresía va al admin en vez del mensaje genérico, y el resumen de
    administración cuando SÍ hay un gasto común del periodo actual."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Inicio Extra", plan="premium")

    def test_staff_sin_membresia_va_al_admin(self):
        staff = User.objects.create_user(username="inicio_staff", is_staff=True)
        self.client.force_login(staff)
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("admin:index"))

    def test_no_staff_sin_membresia_va_al_login_con_mensaje(self):
        user = User.objects.create_user(username="inicio_sin_membresia")
        self.client.force_login(user)
        r = self.client.get(reverse("inicio"), follow=True)
        self.assertContains(r, "no está vinculada a ningún condominio")

    def test_resumen_administracion_con_gasto_comun_del_periodo(self):
        from gastoscomunes.models import CuotaUnidad, GastoComun

        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        gasto = GastoComun.objects.create(condominio=self.condominio, periodo="2026-09", monto_total=10000, fecha_vencimiento=timezone.localdate())
        CuotaUnidad.objects.create(gasto_comun=gasto, unidad=unidad, monto=10000, estado="pagado")
        administracion = crear_membresia(self.condominio, "administracion", username="inicio_admon_gasto")
        self.client.force_login(administracion.user)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["gasto_actual"], gasto)
        self.assertEqual(r.context["gasto_actual_cuotas_pagadas"], 1)
        self.assertEqual(r.context["gasto_actual_recaudado"], 10000)


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
        self.membresia = crear_membresia(self.condominio, "residente", username="elim_residente")
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
        self.assertEqual(len(mail.outbox), 1)


class QRYRegenerarTokenResidentesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test QR Token", plan="premium")

    def setUp(self):
        self.directiva = crear_membresia(self.condominio, "directiva", username="qr_directiva")
        self.client.force_login(self.directiva.user)

    def test_qr_devuelve_una_imagen_png(self):
        r = self.client.get(reverse("qr-registro-residentes"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")

    def test_regenerar_token_cambia_el_token(self):
        token_original = self.condominio.token_registro_residentes
        r = self.client.post(reverse("regenerar-token-residentes"))
        self.assertRedirects(r, reverse("mi-condominio"))
        self.condominio.refresh_from_db()
        self.assertNotEqual(self.condominio.token_registro_residentes, token_original)


class AplicarAlicuotaMasivaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Alicuota Masiva", plan="premium")

    def setUp(self):
        self.administracion = crear_membresia(self.condominio, "administracion", username="alicuota_admon")
        self.client.force_login(self.administracion.user)
        self.unidad = Unidad.objects.create(condominio=self.condominio, numero="1")

    def test_valor_valido_se_aplica_a_todas_las_unidades(self):
        r = self.client.post(reverse("aplicar-alicuota-masiva"), {"alicuota": "0,0033"})
        self.assertRedirects(r, reverse("unidades"))
        self.unidad.refresh_from_db()
        self.assertEqual(str(self.unidad.alicuota), "0.0033")

    def test_valor_invalido_no_cambia_nada(self):
        r = self.client.post(reverse("aplicar-alicuota-masiva"), {"alicuota": "no-es-un-numero"}, follow=True)
        self.assertContains(r, "número válido")
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.alicuota, 0)

    def test_valor_fuera_de_rango_no_cambia_nada(self):
        r = self.client.post(reverse("aplicar-alicuota-masiva"), {"alicuota": "100"}, follow=True)
        self.assertContains(r, "demasiado grande")
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.alicuota, 0)


class MiembroListFiltroRolTests(TestCase):
    def test_filtra_por_rol(self):
        condominio = Condominio.objects.create(nombre="Test Filtro Rol", plan="premium")
        directiva = crear_membresia(condominio, "directiva", username="filtro_rol_directiva")
        crear_membresia(condominio, "residente", username="filtro_rol_residente")
        self.client.force_login(directiva.user)
        r = self.client.get(reverse("miembros") + "?rol=residente")
        self.assertEqual(len(r.context["membresias"]), 1)
        self.assertEqual(r.context["membresias"][0].rol, "residente")


class CondominioRequiredMixinRamasTests(TestCase):
    """Ramas de CondominioRequiredMixin.dispatch() no cubiertas vía InicioView
    (que tiene su propia lógica inline, no usa este mixin): staff sin
    membresía va al admin, y un condominio desactivado bloquea el acceso."""

    def test_staff_sin_membresia_va_al_admin(self):
        staff = User.objects.create_user(username="mixin_staff", is_staff=True)
        self.client.force_login(staff)
        r = self.client.get(reverse("miembros"))
        self.assertRedirects(r, reverse("admin:index"))

    def test_condominio_desactivado_redirige_a_cuenta_desactivada(self):
        condominio = Condominio.objects.create(nombre="Test Desactivado", plan="premium", activo=False)
        membresia = crear_membresia(condominio, "directiva", username="mixin_desactivado")
        self.client.force_login(membresia.user)
        r = self.client.get(reverse("miembros"))
        self.assertRedirects(r, reverse("cuenta-desactivada"))


class SoloStaffMixinPermiteStaffTests(TestCase):
    def test_staff_si_puede_crear_torre(self):
        condominio = Condominio.objects.create(nombre="Test Staff Torre", plan="premium")
        membresia = crear_membresia(condominio, "directiva", username="staff_torre", is_staff=True)
        self.client.force_login(membresia.user)
        r = self.client.post(reverse("crear-torre"), {"nombre": "Nueva"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Torre.objects.filter(condominio=condominio, nombre="Nueva").exists())
