from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AlertaCiudadana, PerfilGeografico
from .services import calcular_geohash, geocodificar_direccion, geocodificar_inverso, notificar_alerta_ciudadana, region_de_comuna, vecinos_geohash


def crear_perfil(username, lat, lng, geohash, comuna="Valparaíso", region="valparaiso"):
    user = User.objects.create_user(username=username)
    return PerfilGeografico.objects.create(
        user=user, direccion_texto="Calle de prueba 123", lat=lat, lng=lng,
        region=region, comuna=comuna, geohash=geohash,
    )


class VecinosGeohashTests(TestCase):
    """vecinos_geohash: la celda propia + sus 8 vecinas -- geohash no es
    perfectamente circular, por eso hay que cubrir los bordes."""

    def test_devuelve_9_celdas_para_un_geohash_normal(self):
        vecinos = vecinos_geohash("66j5f")
        self.assertEqual(len(vecinos), 9)

    def test_incluye_la_celda_propia(self):
        vecinos = vecinos_geohash("66j5f")
        self.assertIn("66j5f", vecinos)

    def test_no_tiene_duplicados(self):
        vecinos = vecinos_geohash("66j5f")
        self.assertEqual(len(vecinos), len(set(vecinos)))

    def test_dos_celdas_vecinas_entre_si_se_devuelven_mutuamente(self):
        """Si A es vecino de B, B también debería considerar a A su vecino -- confirma que get_adjacent no está invertido."""
        import pygeohash as pgh

        centro = "66j5f"
        top = pgh.get_adjacent(centro, "top")
        self.assertIn(centro, vecinos_geohash(top))

    def test_las_9_celdas_son_geografiacamente_vecinas(self):
        """Cada vecino debe estar a lo más a un paso de la celda central --
        confirma indirectamente que son top/bottom/left/right + diagonales,
        no un error que devuelva basura."""
        import pygeohash as pgh

        centro = "66j5f"
        lat_centro, lng_centro = pgh.decode(centro)
        vecinos = vecinos_geohash(centro)
        for v in vecinos:
            lat, lng = pgh.decode(v)
            # a una celda de distancia, la diferencia de lat/lng debería ser
            # chica (un par de celdas de ancho/alto en esta precisión)
            self.assertLess(abs(lat - lat_centro), 1.0)
            self.assertLess(abs(lng - lng_centro), 1.0)


class CalcularGeohashTests(TestCase):
    def test_devuelve_un_geohash_de_la_precision_configurada(self):
        from .models import PRECISION_GEOHASH

        self.assertEqual(len(calcular_geohash(-33.0472, -71.6127)), PRECISION_GEOHASH)

    def test_acepta_decimales_de_django(self):
        """lat/lng suelen venir como Decimal (DecimalField) -- confirma que no explota con eso."""
        from decimal import Decimal

        self.assertTrue(calcular_geohash(Decimal("-33.0472"), Decimal("-71.6127")))


class GeocodificarInversoTests(TestCase):
    """geocodificar_inverso -- sin tocar la red real de Nominatim, se mockea requests.get."""

    def test_devuelve_comuna_y_region_cuando_nominatim_responde_bien(self):
        respuesta_mock = Mock()
        respuesta_mock.json.return_value = {
            "address": {"city": "Valparaíso", "state": "Región de Valparaíso"},
        }
        respuesta_mock.raise_for_status.return_value = None
        with patch("vecindario.services.requests.get", return_value=respuesta_mock):
            resultado = geocodificar_inverso(-33.0472, -71.6127)
        self.assertEqual(resultado, {"comuna": "Valparaíso", "region": "Región de Valparaíso"})

    def test_usa_town_si_no_hay_city(self):
        respuesta_mock = Mock()
        respuesta_mock.json.return_value = {"address": {"town": "Casablanca", "state": "Región de Valparaíso"}}
        respuesta_mock.raise_for_status.return_value = None
        with patch("vecindario.services.requests.get", return_value=respuesta_mock):
            resultado = geocodificar_inverso(-33.32, -71.41)
        self.assertEqual(resultado["comuna"], "Casablanca")

    def test_devuelve_none_si_falla_la_red(self):
        import requests

        with patch("vecindario.services.requests.get", side_effect=requests.RequestException("timeout")):
            resultado = geocodificar_inverso(-33.0472, -71.6127)
        self.assertIsNone(resultado)

    def test_devuelve_none_si_no_trae_comuna(self):
        respuesta_mock = Mock()
        respuesta_mock.json.return_value = {"address": {}}
        respuesta_mock.raise_for_status.return_value = None
        with patch("vecindario.services.requests.get", return_value=respuesta_mock):
            resultado = geocodificar_inverso(0, 0)
        self.assertIsNone(resultado)


class GeocodificarDireccionTests(TestCase):
    def test_devuelve_lat_lng_comuna_region(self):
        respuesta_mock = Mock()
        respuesta_mock.json.return_value = [{
            "lat": "-33.0472", "lon": "-71.6127",
            "address": {"city": "Valparaíso", "state": "Región de Valparaíso"},
        }]
        respuesta_mock.raise_for_status.return_value = None
        with patch("vecindario.services.requests.get", return_value=respuesta_mock):
            resultado = geocodificar_direccion("Porvenir 1602, Playa Ancha")
        self.assertEqual(resultado["comuna"], "Valparaíso")
        self.assertAlmostEqual(resultado["lat"], -33.0472)
        self.assertAlmostEqual(resultado["lng"], -71.6127)

    def test_devuelve_none_si_no_hay_resultados(self):
        respuesta_mock = Mock()
        respuesta_mock.json.return_value = []
        respuesta_mock.raise_for_status.return_value = None
        with patch("vecindario.services.requests.get", return_value=respuesta_mock):
            resultado = geocodificar_direccion("una dirección que no existe en ninguna parte")
        self.assertIsNone(resultado)


class ComunaEnPilotoTests(TestCase):
    """RegistroVecinoForm no debe rechazar una comuna real del piloto solo
    porque Nominatim la devolvió con otra capitalización/espacios -- el
    mismo criterio de normalización que ya usa region_de_comuna."""

    def _form_con_comuna(self, comuna_nominatim):
        from .forms import RegistroVecinoForm

        resultado_mock = {"comuna": comuna_nominatim, "region": "Región de Valparaíso"}
        with patch("vecindario.forms.geocodificar_inverso", return_value=resultado_mock):
            form = RegistroVecinoForm(data={
                "nombre": "Ana", "apellido": "Soto", "telefono": "+56912345678",
                "lat": "-33.0472", "lng": "-71.6127",
                "password1": "contrasena-segura-123", "password2": "contrasena-segura-123",
                "acepto_terminos": "on",
            })
            form.is_valid()
        return form

    def test_acepta_la_comuna_tal_cual(self):
        self.assertTrue(self._form_con_comuna("Valparaíso").is_valid())

    def test_acepta_con_mayusculas_distintas(self):
        self.assertTrue(self._form_con_comuna("valparaíso").is_valid())

    def test_acepta_con_espacios_de_mas(self):
        self.assertTrue(self._form_con_comuna("  Valparaíso  ").is_valid())

    def test_rechaza_una_comuna_que_de_verdad_no_esta_en_el_piloto(self):
        self.assertFalse(self._form_con_comuna("Iquique").is_valid())


class RegionDeComunaTests(TestCase):
    """region_de_comuna -- busca contra COMUNAS_POR_REGION (datos propios,
    346 comunas oficiales), nunca confía en el texto de región que devuelve
    Nominatim (viene en formatos inconsistentes)."""

    def test_encuentra_la_region_de_una_comuna_real(self):
        self.assertEqual(region_de_comuna("Valparaíso"), "valparaiso")
        self.assertEqual(region_de_comuna("Viña del Mar"), "valparaiso")
        self.assertEqual(region_de_comuna("Casablanca"), "valparaiso")

    def test_no_distingue_mayusculas(self):
        self.assertEqual(region_de_comuna("valparaíso"), "valparaiso")

    def test_comuna_inexistente_devuelve_none(self):
        self.assertIsNone(region_de_comuna("Comuna que no existe"))


class NotificarAlertaCiudadanaTests(TestCase):
    """notificar_alerta_ciudadana -- mismo patrón que alertas.tests.NotificarAlertaTests."""

    def setUp(self):
        import pygeohash as pgh

        self.centro = "66j5f"
        self.vecino_hash = pgh.get_adjacent(self.centro, "top")
        self.lejos_hash = "abcde"  # geohash arbitrario, no vecino de 66j5f

        self.autor = crear_perfil("vec_autor", -33.0, -71.6, self.centro)
        self.vecino = crear_perfil("vec_vecino", -33.01, -71.61, self.vecino_hash)
        self.lejano = crear_perfil("vec_lejano", 10.0, 10.0, self.lejos_hash)

    def test_notifica_a_vecinos_cercanos_no_al_autor_ni_a_los_lejanos(self):
        alerta = AlertaCiudadana.objects.create(
            autor=self.autor, tipo="robo", lat=-33.0, lng=-71.6, geohash_momento=self.centro,
        )
        with patch("vecindario.services.enviar_push_a_usuarios") as mock_expo, \
             patch("vecindario.services.enviar_web_push_a_usuarios") as mock_web:
            notificar_alerta_ciudadana(alerta)

        self.assertEqual(mock_expo.call_count, 1)
        self.assertEqual(mock_web.call_count, 1)
        user_ids_avisados = set(mock_expo.call_args.args[0])
        self.assertIn(self.vecino.user_id, user_ids_avisados)
        self.assertNotIn(self.autor.user_id, user_ids_avisados)
        self.assertNotIn(self.lejano.user_id, user_ids_avisados)

    def test_no_llama_a_push_si_no_hay_nadie_cerca(self):
        autor_solo = crear_perfil("vec_solo", 50.0, 50.0, "zzzzz")
        alerta = AlertaCiudadana.objects.create(
            autor=autor_solo, tipo="robo", lat=50.0, lng=50.0, geohash_momento="zzzzz",
        )
        with patch("vecindario.services.enviar_push_a_usuarios") as mock_expo, \
             patch("vecindario.services.enviar_web_push_a_usuarios") as mock_web:
            notificar_alerta_ciudadana(alerta)
        mock_expo.assert_not_called()
        mock_web.assert_not_called()


class AlertaCiudadanaApiTests(TestCase):
    """AlertaCiudadanaViewSet -- cualquiera con PerfilGeografico puede crear
    y resolver, sin exigir Membresia. Mismo patrón que alertas.api_views."""

    def setUp(self):
        self.autor = crear_perfil("api_autor", -33.0, -71.6, "66j5f")

    def test_sin_perfil_geografico_no_puede_crear(self):
        user_sin_perfil = User.objects.create_user(username="sin_perfil")
        self.client.force_login(user_sin_perfil)
        r = self.client.post(reverse("alerta-ciudadana-list"), {"tipo": "robo", "lat": -33.0, "lng": -71.6}, content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_crea_alerta_y_calcula_geohash_del_momento(self):
        self.client.force_login(self.autor.user)
        with patch("vecindario.api_views.notificar_alerta_ciudadana") as mock_notificar:
            r = self.client.post(reverse("alerta-ciudadana-list"), {"tipo": "robo", "lat": -33.0, "lng": -71.6}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        alerta = AlertaCiudadana.objects.get(pk=r.json()["id"])
        self.assertEqual(alerta.autor, self.autor)
        self.assertTrue(alerta.geohash_momento)
        mock_notificar.assert_called_once_with(alerta)

    def test_patch_generico_no_esta_permitido_ni_siquiera_al_autor(self):
        """Solo la acción resolver() puede cambiar una alerta -- un PATCH
        genérico permitiría reescribir tipo/mensaje/lat/lng de cualquiera
        en el barrio (radio de 5km, gente sin verificar), no solo marcarla
        resuelta."""
        alerta = AlertaCiudadana.objects.create(autor=self.autor, tipo="robo", lat=-33.0, lng=-71.6, geohash_momento="66j5f")
        self.client.force_login(self.autor.user)
        r = self.client.patch(
            reverse("alerta-ciudadana-detail", kwargs={"pk": alerta.pk}),
            data={"mensaje": "contenido reescrito"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 405)
        alerta.refresh_from_db()
        self.assertEqual(alerta.mensaje, "")

    def test_resolver_marca_estado_y_autor(self):
        alerta = AlertaCiudadana.objects.create(autor=self.autor, tipo="robo", lat=-33.0, lng=-71.6, geohash_momento="66j5f")
        self.client.force_login(self.autor.user)
        r = self.client.patch(
            reverse("alerta-ciudadana-resolver", kwargs={"pk": alerta.pk}),
            data={"estado": "resuelta"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, "resuelta")
        self.assertEqual(alerta.resuelta_por, self.autor)

    def test_lista_solo_alertas_del_barrio_cercano(self):
        import pygeohash as pgh

        vecino_hash = pgh.get_adjacent("66j5f", "top")
        lejano = crear_perfil("api_lejano", 10.0, 10.0, "abcde")
        AlertaCiudadana.objects.create(autor=self.autor, tipo="robo", lat=-33.0, lng=-71.6, geohash_momento="66j5f")
        AlertaCiudadana.objects.create(autor=crear_perfil("api_vecino", -33.01, -71.61, vecino_hash), tipo="incendio", lat=-33.01, lng=-71.61, geohash_momento=vecino_hash)
        AlertaCiudadana.objects.create(autor=lejano, tipo="robo", lat=10.0, lng=10.0, geohash_momento="abcde")

        self.client.force_login(self.autor.user)
        r = self.client.get(reverse("alerta-ciudadana-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual(len(resultados), 2)


class RegistroVecinoViewTests(TestCase):
    def test_get_muestra_el_formulario(self):
        r = self.client.get(reverse("vecindario-registro"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Únete a la red vecinal")

    def test_post_con_gps_en_comuna_piloto_crea_cuenta(self):
        resultado_mock = {"comuna": "Valparaíso", "region": "Región de Valparaíso"}
        with patch("vecindario.forms.geocodificar_inverso", return_value=resultado_mock):
            r = self.client.post(reverse("vecindario-registro"), {
                "nombre": "Ana", "apellido": "Soto", "telefono": "+56912345678",
                "lat": "-33.047200", "lng": "-71.612700",
                "password1": "contrasena-segura-123", "password2": "contrasena-segura-123",
                "acepto_terminos": "on",
            })
        self.assertRedirects(r, reverse("mi-barrio"))
        perfil = PerfilGeografico.objects.get(user__first_name="Ana")
        self.assertEqual(perfil.comuna, "Valparaíso")
        self.assertEqual(perfil.region, "valparaiso")
        self.assertTrue(perfil.geohash)

    def test_post_fuera_de_comunas_piloto_rechaza(self):
        resultado_mock = {"comuna": "Iquique", "region": "Región de Tarapacá"}
        with patch("vecindario.forms.geocodificar_inverso", return_value=resultado_mock):
            r = self.client.post(reverse("vecindario-registro"), {
                "nombre": "Pedro", "apellido": "Pérez", "telefono": "+56911111111",
                "lat": "-20.21", "lng": "-70.15",
                "password1": "contrasena-segura-123", "password2": "contrasena-segura-123",
                "acepto_terminos": "on",
            })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PerfilGeografico.objects.filter(user__first_name="Pedro").exists())

    def test_post_sin_aceptar_terminos_rechaza(self):
        resultado_mock = {"comuna": "Valparaíso", "region": "Región de Valparaíso"}
        with patch("vecindario.forms.geocodificar_inverso", return_value=resultado_mock):
            r = self.client.post(reverse("vecindario-registro"), {
                "nombre": "Luis", "apellido": "López", "telefono": "+56922222222",
                "lat": "-33.0472", "lng": "-71.6127",
                "password1": "contrasena-segura-123", "password2": "contrasena-segura-123",
            })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(first_name="Luis").exists())


class BackfillPerfilesGeograficosTests(TestCase):
    """Management command -- dry-run por defecto, --aplicar para crear de verdad."""

    def setUp(self):
        from core.models import Condominio, Membresia

        self.condominio = Condominio.objects.create(
            nombre="Backfill Test", plan="premium", direccion="Porvenir 1602", comuna="Playa Ancha",
        )
        user = User.objects.create_user(username="backfill_miembro", first_name="Vecino", last_name="Empart")
        self.membresia = Membresia.objects.create(user=user, condominio=self.condominio, rol="residente", terminos_aceptados_en=timezone.now())

    def _mock_geocodificar(self):
        return patch("vecindario.management.commands.backfill_perfiles_geograficos.geocodificar_direccion", return_value={
            "lat": -33.0472, "lng": -71.6127, "comuna": "Valparaíso", "region": "Región de Valparaíso",
        })

    def test_dry_run_no_crea_nada(self):
        from io import StringIO

        from django.core.management import call_command

        with self._mock_geocodificar():
            call_command("backfill_perfiles_geograficos", stdout=StringIO())
        self.assertFalse(PerfilGeografico.objects.filter(user=self.membresia.user).exists())

    def test_aplicar_crea_el_perfil_heredando_la_ubicacion_del_condominio(self):
        from io import StringIO

        from django.core.management import call_command

        with self._mock_geocodificar():
            call_command("backfill_perfiles_geograficos", "--aplicar", stdout=StringIO())
        perfil = PerfilGeografico.objects.get(user=self.membresia.user)
        self.assertEqual(perfil.comuna, "Valparaíso")
        self.assertEqual(perfil.region, "valparaiso")

    def test_es_idempotente_no_duplica_en_segunda_corrida(self):
        from io import StringIO

        from django.core.management import call_command

        with self._mock_geocodificar():
            call_command("backfill_perfiles_geograficos", "--aplicar", stdout=StringIO())
            call_command("backfill_perfiles_geograficos", "--aplicar", stdout=StringIO())
        self.assertEqual(PerfilGeografico.objects.filter(user=self.membresia.user).count(), 1)

    def test_comuna_no_oficial_queda_reportada_sin_crear_perfil(self):
        from io import StringIO

        from django.core.management import call_command

        with patch("vecindario.management.commands.backfill_perfiles_geograficos.geocodificar_direccion", return_value={
            "lat": -33.0, "lng": -71.6, "comuna": "Comuna Inventada", "region": "Región X",
        }):
            salida = StringIO()
            call_command("backfill_perfiles_geograficos", "--aplicar", stdout=salida)
        self.assertFalse(PerfilGeografico.objects.filter(user=self.membresia.user).exists())
        self.assertIn("Comuna Inventada", salida.getvalue())


class MiBarrioViewTests(TestCase):
    def test_sin_perfil_geografico_redirige_a_registro(self):
        user = User.objects.create_user(username="sin_perfil_vista")
        self.client.force_login(user)
        r = self.client.get(reverse("mi-barrio"))
        self.assertRedirects(r, reverse("vecindario-registro"))

    def test_con_perfil_geografico_muestra_la_pagina(self):
        perfil = crear_perfil("con_perfil_vista", -33.0, -71.6, "66j5f")
        self.client.force_login(perfil.user)
        r = self.client.get(reverse("mi-barrio"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Botón de pánico")

    def test_sin_membresia_el_navbar_no_ofrece_links_de_condominio(self):
        """Regresión: antes el navbar mostraba Inicio/Directorio/Números de
        emergencia a cualquier logueado, pero esas vistas exigen condominio
        -- un vecino sin condominio las veía y le salía un error confuso
        ("tu cuenta no está vinculada a ningún condominio")."""
        perfil = crear_perfil("sin_membresia_navbar", -33.0, -71.6, "66j5f")
        self.client.force_login(perfil.user)
        r = self.client.get(reverse("mi-barrio"))
        self.assertNotContains(r, reverse("directorio"))
        self.assertNotContains(r, reverse("numeros-emergencia"))
        self.assertContains(r, reverse("mi-barrio"))

    def test_con_membresia_redirige_a_inicio(self):
        from core.models import Condominio, Membresia

        condominio = Condominio.objects.create(nombre="Test Mi Barrio", plan="premium")
        user = User.objects.create_user(username="con_membresia_barrio")
        Membresia.objects.create(user=user, condominio=condominio, rol="directiva", terminos_aceptados_en=timezone.now())
        self.client.force_login(user)
        r = self.client.get(reverse("mi-barrio"))
        self.assertRedirects(r, reverse("inicio"))

    def test_inicio_redirige_a_mi_barrio_si_no_tiene_condominio(self):
        """Regresión: Django manda a /login/ al éxito de login al default
        LOGIN_REDIRECT_URL='inicio' -- si InicioView no supiera de
        perfil_geografico, un vecino sin condominio que entra por /login/
        directo (sin venir ya de /mi-barrio/) caía en el error falso
        "tu cuenta no está vinculada a ningún condominio"."""
        perfil = crear_perfil("inicio_redirige_barrio", -33.0, -71.6, "66j5f")
        self.client.force_login(perfil.user)
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("mi-barrio"))

    def test_con_membresia_y_perfil_geografico_puede_ver_mi_barrio(self):
        """Alguien con los dos (ej. vecino de un condominio que también se
        unió a la red vecinal) sí puede ver /mi-barrio/, a diferencia de
        quien solo tiene Membresia."""
        from core.models import Condominio, Membresia

        condominio = Condominio.objects.create(nombre="Test Mi Barrio Doble", plan="premium")
        perfil = crear_perfil("con_ambos_perfiles", -33.0, -71.6, "66j5f")
        Membresia.objects.create(user=perfil.user, condominio=condominio, rol="directiva", terminos_aceptados_en=timezone.now())
        self.client.force_login(perfil.user)
        r = self.client.get(reverse("mi-barrio"))
        self.assertEqual(r.status_code, 200)


class ActualizarPerfilGeograficoViewTests(TestCase):
    def test_sin_perfil_geografico_redirige_a_registro(self):
        user = User.objects.create_user(username="sin_perfil_actualizar")
        self.client.force_login(user)
        r = self.client.get(reverse("vecindario-actualizar-ubicacion"))
        self.assertRedirects(r, reverse("vecindario-registro"))

    def test_sin_login_redirige_a_login(self):
        r = self.client.get(reverse("vecindario-actualizar-ubicacion"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)

    def test_get_precarga_la_direccion_y_telefono_actuales(self):
        perfil = crear_perfil("precarga_actualizar", -33.0, -71.6, "66j5f")
        perfil.direccion_texto = "Calle Vieja 123"
        perfil.telefono = "+56911112222"
        perfil.save()
        self.client.force_login(perfil.user)
        r = self.client.get(reverse("vecindario-actualizar-ubicacion"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Calle Vieja 123")
        self.assertContains(r, "+56911112222")

    def test_post_con_gps_en_comuna_piloto_actualiza_el_perfil(self):
        perfil = crear_perfil("actualizar_gps_ok", -33.0, -71.6, "66j5f")
        geohash_anterior = perfil.geohash
        self.client.force_login(perfil.user)
        resultado_mock = {"comuna": "Viña del Mar", "region": "Región de Valparaíso"}
        with patch("vecindario.forms.geocodificar_inverso", return_value=resultado_mock):
            r = self.client.post(reverse("vecindario-actualizar-ubicacion"), {
                "direccion_texto": "", "lat": "-33.024500", "lng": "-71.551600", "telefono": "+56933334444",
            })
        self.assertRedirects(r, reverse("mi-barrio"))
        perfil.refresh_from_db()
        self.assertEqual(perfil.comuna, "Viña del Mar")
        self.assertEqual(perfil.telefono, "+56933334444")
        self.assertNotEqual(perfil.geohash, geohash_anterior)

    def test_post_fuera_de_comunas_piloto_rechaza_y_no_modifica_el_perfil(self):
        perfil = crear_perfil("actualizar_fuera_piloto", -33.0, -71.6, "66j5f", comuna="Valparaíso")
        comuna_original = perfil.comuna
        self.client.force_login(perfil.user)
        resultado_mock = {"comuna": "Iquique", "region": "Región de Tarapacá"}
        with patch("vecindario.forms.geocodificar_inverso", return_value=resultado_mock):
            r = self.client.post(reverse("vecindario-actualizar-ubicacion"), {
                "direccion_texto": "", "lat": "-20.21", "lng": "-70.15", "telefono": "",
            })
        self.assertEqual(r.status_code, 200)
        perfil.refresh_from_db()
        self.assertEqual(perfil.comuna, comuna_original)
