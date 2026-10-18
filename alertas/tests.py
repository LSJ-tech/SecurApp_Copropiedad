from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia

from .models import TIPO_CHOICES, Alerta, NumeroEmergencia
from .services import TITULOS_POR_TIPO


def crear_membresia(condominio, rol, **user_kwargs):
    """Sin password: los tests se autentican con force_login."""
    username = user_kwargs.pop("username", f"t_{rol}_{Membresia.objects.count()}")
    user = User.objects.create_user(username=username, **user_kwargs)
    return Membresia.objects.create(user=user, condominio=condominio, rol=rol, terminos_aceptados_en=timezone.now())


def crear_devquad(username="devquad_test"):
    """Cuenta devquad -- is_staff, sin Membresia (ver condominio_activo_devquad)."""
    return User.objects.create_user(username=username, is_staff=True)


class FiltroEstadoAlertaTests(TestCase):
    """`?estado=activa` alguna vez no filtraba nada (no había filter_backend
    configurado) y 'Alertas activas' mostraba TODAS las alertas, incluidas
    las resueltas. Esto fija ese comportamiento."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Filtro Alertas", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", username="filtro_residente")
        self.client.force_login(self.membresia.user)
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="robo", estado="activa")
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="incendio", estado="resuelta")
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="otro", estado="falsa_alarma")

    def test_estado_activa_filtra_de_verdad(self):
        r = self.client.get(reverse("alerta-list") + "?estado=activa")
        datos = r.json()
        resultados = datos["results"] if isinstance(datos, dict) else datos
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["tipo"], "robo")

    def test_sin_filtro_devuelve_todas(self):
        r = self.client.get(reverse("alerta-list"))
        datos = r.json()
        resultados = datos["results"] if isinstance(datos, dict) else datos
        self.assertEqual(len(resultados), 3)


class AutoCierreYResolucionAbiertaTests(TestCase):
    """Cualquier rol puede resolver una alerta (no solo directiva/conserjería,
    ver TieneMembresia en vez de EsDirectivaOConserje), y una alerta activa
    hace más de 30 min se autocierra sola al listarse."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Autocierre", plan="premium")

    def setUp(self):
        self.autor = crear_membresia(self.condominio, "residente", username="auto_autor")
        self.vecino = crear_membresia(self.condominio, "residente", username="auto_vecino")

    def test_un_residente_puede_resolver_la_alerta_de_otro(self):
        alerta = Alerta.objects.create(condominio=self.condominio, autor=self.autor, tipo="robo", estado="activa")
        self.client.force_login(self.vecino.user)
        r = self.client.patch(
            reverse("alerta-resolver", kwargs={"pk": alerta.pk}),
            data={"estado": "resuelta"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, "resuelta")
        self.assertEqual(alerta.resuelta_por_id, self.vecino.pk)

    def test_alerta_vieja_se_autocierra_al_listar(self):
        alerta = Alerta.objects.create(condominio=self.condominio, autor=self.autor, tipo="robo", estado="activa")
        Alerta.objects.filter(pk=alerta.pk).update(fecha_creacion=timezone.now() - timedelta(minutes=45))
        self.client.force_login(self.vecino.user)
        self.client.get(reverse("alerta-list"))
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, "auto_cerrada")


class NotificarAlertaTests(TestCase):
    """Crear una alerta de verdad (vía la API, como hace el botón de pánico)
    debe disparar los dos canales de push -- Expo (app nativa futura) y Web
    Push (la PWA, agregada hoy) -- sin pegarle a ningún servicio real."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Notificar Alerta", plan="premium")

    def test_crear_alerta_llama_a_ambos_canales_de_push(self):
        membresia = crear_membresia(self.condominio, "residente", username="notif_autor")
        self.client.force_login(membresia.user)
        with patch("alertas.services.enviar_push_a_condominio") as mock_expo, \
             patch("alertas.services.enviar_web_push_a_condominio") as mock_web:
            r = self.client.post(reverse("alerta-list"), {"tipo": "robo", "mensaje": "Prueba"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(mock_expo.call_count, 1)
        self.assertEqual(mock_web.call_count, 1)
        self.assertEqual(mock_expo.call_args.kwargs["excluir_user_id"], membresia.user_id)
        self.assertEqual(mock_web.call_args.kwargs["excluir_user_id"], membresia.user_id)

    def test_todos_los_tipos_de_alerta_tienen_titulo_de_notificacion(self):
        """Si se agrega un tipo nuevo a TIPO_CHOICES sin agregarle su título en
        TITULOS_POR_TIPO, notificar_alerta no explota (usa el de "otro" como
        respaldo) pero manda un título genérico -- este test obliga a no
        olvidarlo."""
        codigos_con_titulo = set(TITULOS_POR_TIPO)
        codigos_declarados = {codigo for codigo, _ in TIPO_CHOICES}
        self.assertEqual(codigos_declarados, codigos_con_titulo)

    def test_cada_tipo_nuevo_crea_la_alerta_y_usa_su_propio_titulo(self):
        membresia = crear_membresia(self.condominio, "residente", username="notif_tipos")
        self.client.force_login(membresia.user)
        tipos_nuevos = [
            "emergencia_medica", "persona_extrana", "fuga_gas", "fuga_agua",
            "atrapado_ascensor", "objeto_sospechoso", "rina_disturbio",
        ]
        for tipo in tipos_nuevos:
            with patch("alertas.services.enviar_push_a_condominio") as mock_expo, \
                 patch("alertas.services.enviar_web_push_a_condominio"):
                r = self.client.post(reverse("alerta-list"), {"tipo": tipo}, content_type="application/json")
            self.assertEqual(r.status_code, 201)
            self.assertEqual(mock_expo.call_args.args[1], TITULOS_POR_TIPO[tipo])


class AlertaHistorialViewTests(TestCase):
    """Página web del historial (`alertas/views.py`) -- distinta del endpoint
    de API que prueba FiltroEstadoAlertaTests arriba."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Historial Alertas", plan="premium")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", username="historial_residente")
        self.client.force_login(self.membresia.user)
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="robo", estado="activa")
        Alerta.objects.create(condominio=self.condominio, autor=self.membresia, tipo="incendio", estado="resuelta")

    def test_sin_filtro_muestra_todas(self):
        r = self.client.get(reverse("alertas-historial"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["alertas"]), 2)
        self.assertEqual(r.context["estado_seleccionado"], "")

    def test_filtro_por_estado(self):
        r = self.client.get(reverse("alertas-historial") + "?estado=resuelta")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["alertas"]), 1)
        self.assertEqual(r.context["alertas"][0].tipo, "incendio")
        self.assertEqual(r.context["estado_seleccionado"], "resuelta")


class CondominiosVecinosCompartenAlertasTests(TestCase):
    """Dos condominios que comparten vecindario (M2M condominios_vecinos,
    simétrico) ven y reciben notificación de las alertas del otro -- pero
    nada más (miembros, gastos comunes, etc. siguen aislados por separado,
    eso no se tocó en este cambio)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio_a = Condominio.objects.create(nombre="Barrio A", plan="premium")
        cls.condominio_b = Condominio.objects.create(nombre="Barrio B", plan="premium")
        cls.condominio_suelto = Condominio.objects.create(nombre="Barrio Suelto", plan="premium")
        cls.condominio_a.condominios_vecinos.add(cls.condominio_b)

    def test_el_vinculo_es_simetrico(self):
        self.assertIn(self.condominio_b, self.condominio_a.condominios_vecinos.all())
        self.assertIn(self.condominio_a, self.condominio_b.condominios_vecinos.all())
        self.assertNotIn(self.condominio_suelto, self.condominio_a.condominios_vecinos.all())

    def test_ids_red_alertas_incluye_al_propio_y_a_los_vecinos(self):
        ids = self.condominio_a.ids_red_alertas
        self.assertCountEqual(ids, [self.condominio_a.pk, self.condominio_b.pk])
        self.assertEqual(self.condominio_suelto.ids_red_alertas, [self.condominio_suelto.pk])

    def test_un_residente_ve_la_alerta_activa_del_condominio_vecino(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor")
        alerta_b = Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_a = crear_membresia(self.condominio_a, "residente", username="vecino_a_residente")
        self.client.force_login(residente_a.user)
        r = self.client.get(reverse("alerta-list") + "?estado=activa")
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([a["id"] for a in resultados], [alerta_b.id])
        self.assertEqual(resultados[0]["condominio_nombre"], "Barrio B")

    def test_un_condominio_sin_vinculo_no_ve_la_alerta_ajena(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor2")
        Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_suelto = crear_membresia(self.condominio_suelto, "residente", username="suelto_residente")
        self.client.force_login(residente_suelto.user)
        r = self.client.get(reverse("alerta-list") + "?estado=activa")
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual(resultados, [])

    def test_un_residente_vecino_puede_resolver_la_alerta_del_otro_condominio(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor3")
        alerta_b = Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_a = crear_membresia(self.condominio_a, "residente", username="vecino_a_resuelve")
        self.client.force_login(residente_a.user)
        r = self.client.patch(
            reverse("alerta-resolver", kwargs={"pk": alerta_b.pk}),
            data={"estado": "falsa_alarma"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        alerta_b.refresh_from_db()
        self.assertEqual(alerta_b.estado, "falsa_alarma")
        self.assertEqual(alerta_b.resuelta_por_id, residente_a.pk)

    def test_el_historial_del_condominio_a_incluye_las_del_vecino_b(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor4")
        Alerta.objects.create(condominio=self.condominio_b, autor=autor_b, tipo="robo", estado="activa")

        residente_a = crear_membresia(self.condominio_a, "residente", username="vecino_a_historial")
        self.client.force_login(residente_a.user)
        r = self.client.get(reverse("alertas-historial"))
        self.assertEqual(len(r.context["alertas"]), 1)
        self.assertContains(r, "Barrio B")

    def test_notificar_alerta_avisa_tambien_al_condominio_vecino(self):
        autor_b = crear_membresia(self.condominio_b, "residente", username="vecino_b_autor5")
        self.client.force_login(autor_b.user)
        with patch("alertas.services.enviar_push_a_condominio") as mock_expo, \
             patch("alertas.services.enviar_web_push_a_condominio") as mock_web:
            r = self.client.post(reverse("alerta-list"), {"tipo": "robo"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(mock_expo.call_count, 2)
        self.assertEqual(mock_web.call_count, 2)
        condominios_avisados = {llamada.args[0] for llamada in mock_expo.call_args_list}
        self.assertEqual(condominios_avisados, {self.condominio_a, self.condominio_b})


class AlertaHistorialMuestraBlockTests(TestCase):
    """El historial mostraba el depto del autor/resolutor pero no el block --
    ahora muestra ambos cuando la unidad tiene torre asignada."""

    def test_muestra_el_block_ademas_del_depto(self):
        from core.models import Torre, Unidad

        condominio = Condominio.objects.create(nombre="Test Historial Block", plan="premium")
        torre = Torre.objects.create(condominio=condominio, nombre="9")
        unidad = Unidad.objects.create(condominio=condominio, torre=torre, numero="302")
        autor = crear_membresia(condominio, "residente", username="historial_block_autor")
        autor.unidad = unidad
        autor.save(update_fields=["unidad"])
        self.client.force_login(autor.user)
        Alerta.objects.create(condominio=condominio, autor=autor, tipo="robo", estado="activa")

        r = self.client.get(reverse("alertas-historial"))
        self.assertContains(r, f"{condominio.etiqueta_torre} 9, {condominio.etiqueta_unidad.lower()} 302")


class AlertaAdminTests(TestCase):
    """Insignias de color para tipo/estado (ver tipo_badge/estado_badge en
    alertas/admin.py) -- confirma que el changelist renderiza bien con
    ellas, no solo que el método en sí devuelve el valor esperado."""

    def test_changelist_renderiza_con_las_insignias(self):
        condominio = Condominio.objects.create(nombre="Test Admin Alerta", plan="premium")
        autor = crear_membresia(condominio, "residente", username="admin_alerta_autor")
        Alerta.objects.create(condominio=condominio, autor=autor, tipo="robo", estado="activa")
        staff = User.objects.create_superuser(username="admin_alerta_staff", password="x", email="admin_alerta_staff@example.com")
        self.client.force_login(staff)
        r = self.client.get("/admin/alertas/alerta/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Robo")
        self.assertContains(r, "Activa")


class NumeroEmergenciaListViewTests(TestCase):
    """Abierto a cualquier rol -- precarga los 4 nacionales solo la primera
    vez (ver NumeroEmergenciaListView.get_queryset)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Numeros Emergencia", plan="premium", region="valparaiso")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="num_emerg_residente")
        self.devquad = crear_devquad("num_emerg_devquad")

    def _login_devquad(self, condominio=None):
        self.client.force_login(self.devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[(condominio or self.condominio).pk]))

    def test_precarga_los_numeros_nacionales(self):
        from .models import NUMEROS_NACIONALES, NumeroEmergencia

        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(NumeroEmergencia.objects.filter(condominio=self.condominio).count(), len(NUMEROS_NACIONALES))
        self.assertContains(r, "133")
        self.assertContains(r, "132")

    def test_no_duplica_al_visitar_dos_veces(self):
        from .models import NUMEROS_NACIONALES, NumeroEmergencia

        self.client.force_login(self.residente.user)
        self.client.get(reverse("numeros-emergencia"))
        self.client.get(reverse("numeros-emergencia"))
        self.assertEqual(NumeroEmergencia.objects.filter(condominio=self.condominio).count(), len(NUMEROS_NACIONALES))

    def test_se_resincroniza_solo_si_un_nacional_se_borra_por_fuera_de_la_app(self):
        """Los nacionales no se pueden borrar desde la app (ver
        EliminarNumeroEmergenciaView), así que si uno desaparece fue por
        fuera (ej. admin de Django) -- en ese caso sí conviene recrearlo
        solo, no hay ninguna intención de directiva que respetar."""
        from .models import NUMEROS_NACIONALES, NumeroEmergencia

        self.client.force_login(self.residente.user)
        self.client.get(reverse("numeros-emergencia"))
        NumeroEmergencia.objects.get(condominio=self.condominio, nombre="Bomberos").delete()

        self.client.get(reverse("numeros-emergencia"))
        self.assertEqual(NumeroEmergencia.objects.filter(condominio=self.condominio).count(), len(NUMEROS_NACIONALES))
        self.assertTrue(NumeroEmergencia.objects.filter(condominio=self.condominio, nombre="Bomberos").exists())

    def test_los_numeros_nacionales_quedan_marcados_como_tales(self):
        from .models import NumeroEmergencia

        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertTrue(NumeroEmergencia.objects.get(condominio=self.condominio, nombre="Bomberos").es_nacional)
        self.assertContains(r, "Nacional")

    def test_sugerencias_segun_la_region_del_condominio(self):
        self._login_devquad()
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertIn("Chilquinta", r.context["sugerencias"]["electricidad"])
        self.assertContains(r, "Chilquinta")

    def test_residente_no_ve_las_sugerencias(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertNotContains(r, "Chilquinta")

    def test_sin_sugerencias_para_una_region_sin_cobertura(self):
        condominio = Condominio.objects.create(nombre="Test Sin Sugerencias", plan="premium", region="aysen")
        self._login_devquad(condominio)
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertEqual(r.context["sugerencias"], {})


class NumeroEmergenciaCreateViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Crear Numero", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="crear_num_residente")
        self.devquad = crear_devquad("crear_num_devquad")

    def _login_devquad(self):
        self.client.force_login(self.devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_residente_no_puede_agregar(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("numero-emergencia-crear"), {"categoria": "otro", "nombre": "Conserjería", "telefono": "123"})
        self.assertEqual(r.status_code, 302)
        from .models import NumeroEmergencia
        self.assertFalse(NumeroEmergencia.objects.filter(condominio=self.condominio).exists())

    def test_devquad_puede_agregar(self):
        self._login_devquad()
        r = self.client.post(reverse("numero-emergencia-crear"), {"categoria": "electricidad", "nombre": "Chilquinta", "telefono": "600 600 5000"})
        # assertRedirects sigue el redirect y confirma que responde 200 --
        # eso de paso dispara la sincronización de nacionales de
        # NumeroEmergenciaListView, así que puede haber más de un registro.
        self.assertRedirects(r, reverse("numeros-emergencia"))
        from .models import NumeroEmergencia
        numero = NumeroEmergencia.objects.get(condominio=self.condominio, nombre="Chilquinta")
        self.assertEqual(numero.telefono, "600 600 5000")
        self.assertFalse(numero.es_nacional)

    def test_prellena_desde_una_sugerencia_pero_nunca_el_telefono(self):
        self._login_devquad()
        r = self.client.get(reverse("numero-emergencia-crear") + "?nombre=Chilquinta&categoria=electricidad")
        self.assertContains(r, 'value="Chilquinta"')
        self.assertNotIn("telefono", r.context["form"].initial)


class EliminarNumeroEmergenciaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Borrar Numero", plan="premium")
        cls.otro_condominio = Condominio.objects.create(nombre="Test Borrar Numero B", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="borrar_num_residente")
        self.devquad = crear_devquad("borrar_num_devquad")

    def _login_devquad(self, condominio=None):
        self.client.force_login(self.devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[(condominio or self.condominio).pk]))

    def _numero(self, condominio=None):
        from .models import NumeroEmergencia
        return NumeroEmergencia.objects.create(condominio=condominio or self.condominio, categoria="otro", nombre="Conserjería", telefono="123")

    def test_residente_no_puede_borrar(self):
        numero = self._numero()
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("numero-emergencia-eliminar", args=[numero.pk]))
        self.assertEqual(r.status_code, 302)
        from .models import NumeroEmergencia
        self.assertTrue(NumeroEmergencia.objects.filter(pk=numero.pk).exists())

    def test_devquad_puede_borrar(self):
        numero = self._numero()
        self._login_devquad()
        r = self.client.post(reverse("numero-emergencia-eliminar", args=[numero.pk]))
        self.assertRedirects(r, reverse("numeros-emergencia"))
        from .models import NumeroEmergencia
        self.assertFalse(NumeroEmergencia.objects.filter(pk=numero.pk).exists())

    def test_no_puede_borrar_uno_de_otro_condominio(self):
        numero = self._numero(condominio=self.otro_condominio)
        self._login_devquad()
        r = self.client.post(reverse("numero-emergencia-eliminar", args=[numero.pk]))
        self.assertEqual(r.status_code, 404)
        from .models import NumeroEmergencia
        self.assertTrue(NumeroEmergencia.objects.filter(pk=numero.pk).exists())

    def test_ni_siquiera_devquad_puede_borrar_un_nacional(self):
        from .models import NumeroEmergencia

        numero = NumeroEmergencia.objects.create(condominio=self.condominio, categoria="policia", nombre="Carabineros", telefono="133")
        self._login_devquad()
        r = self.client.post(reverse("numero-emergencia-eliminar", args=[numero.pk]), follow=True)
        self.assertContains(r, "no se pueden eliminar")
        self.assertTrue(NumeroEmergencia.objects.filter(pk=numero.pk).exists())


class ProponerNumeroEmergenciaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Proponer Numero", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="proponer_num_residente")

    def test_cualquier_rol_puede_proponer(self):
        from .models import PropuestaNumeroEmergencia

        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("numero-emergencia-proponer"), {
            "categoria": "electricidad", "nombre": "CGE", "telefono": "800 800 767", "nota": "Lo que me dieron en mi boleta",
        })
        self.assertRedirects(r, reverse("numeros-emergencia"))
        propuesta = PropuestaNumeroEmergencia.objects.get(condominio=self.condominio)
        self.assertEqual(propuesta.autor, self.residente)
        self.assertEqual(propuesta.estado, "pendiente")

    def test_no_crea_un_numero_real_todavia(self):
        self.client.force_login(self.residente.user)
        self.client.post(reverse("numero-emergencia-proponer"), {"categoria": "electricidad", "nombre": "CGE", "telefono": "800 800 767"})
        self.assertFalse(NumeroEmergencia.objects.filter(condominio=self.condominio, nombre="CGE").exists())

    def test_no_se_puede_proponer_un_nombre_nacional(self):
        from .models import PropuestaNumeroEmergencia

        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("numero-emergencia-proponer"), {"categoria": "policia", "nombre": "Carabineros", "telefono": "999"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ya es un número nacional")
        self.assertFalse(PropuestaNumeroEmergencia.objects.filter(condominio=self.condominio).exists())


class RevisarPropuestaNumeroEmergenciaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Revisar Propuesta", plan="premium")
        cls.otro_condominio = Condominio.objects.create(nombre="Test Revisar Propuesta B", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="revisar_prop_residente")
        self.devquad = crear_devquad("revisar_prop_devquad")

    def _login_devquad(self, condominio=None):
        self.client.force_login(self.devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[(condominio or self.condominio).pk]))

    def _propuesta(self, condominio=None, **kwargs):
        from .models import PropuestaNumeroEmergencia

        kwargs.setdefault("categoria", "electricidad")
        kwargs.setdefault("nombre", "CGE")
        kwargs.setdefault("telefono", "800 800 767")
        return PropuestaNumeroEmergencia.objects.create(condominio=condominio or self.condominio, autor=self.residente, **kwargs)

    def test_residente_no_puede_aprobar(self):
        propuesta = self._propuesta()
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("propuesta-numero-emergencia-aprobar", args=[propuesta.pk]))
        self.assertEqual(r.status_code, 302)
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, "pendiente")
        self.assertFalse(NumeroEmergencia.objects.filter(condominio=self.condominio, nombre="CGE").exists())

    def test_devquad_puede_aprobar(self):
        propuesta = self._propuesta()
        self._login_devquad()
        r = self.client.post(reverse("propuesta-numero-emergencia-aprobar", args=[propuesta.pk]), follow=True)
        self.assertContains(r, "se agregó a los números de emergencia")
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, "aprobada")
        # devquad no tiene Membresia -- queda registrado que nadie en
        # particular (del condominio) la revisó, ver AprobarPropuestaNumeroEmergenciaView.
        self.assertIsNone(propuesta.revisada_por)
        self.assertIsNotNone(propuesta.fecha_revision)

        numero = NumeroEmergencia.objects.get(condominio=self.condominio, nombre="CGE")
        self.assertEqual(numero.telefono, "800 800 767")
        self.assertFalse(numero.es_nacional)

    def test_devquad_puede_rechazar(self):
        propuesta = self._propuesta()
        self._login_devquad()
        r = self.client.post(reverse("propuesta-numero-emergencia-rechazar", args=[propuesta.pk]))
        self.assertRedirects(r, reverse("numeros-emergencia"))
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, "rechazada")
        self.assertFalse(NumeroEmergencia.objects.filter(condominio=self.condominio, nombre="CGE").exists())

    def test_residente_no_puede_rechazar(self):
        propuesta = self._propuesta()
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("propuesta-numero-emergencia-rechazar", args=[propuesta.pk]))
        self.assertEqual(r.status_code, 302)
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, "pendiente")

    def test_no_puede_revisar_dos_veces(self):
        propuesta = self._propuesta()
        self._login_devquad()
        self.client.post(reverse("propuesta-numero-emergencia-aprobar", args=[propuesta.pk]))
        r = self.client.post(reverse("propuesta-numero-emergencia-aprobar", args=[propuesta.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(NumeroEmergencia.objects.filter(condominio=self.condominio, nombre="CGE").count(), 1)

    def test_no_puede_revisar_una_de_otro_condominio(self):
        propuesta = self._propuesta(condominio=self.otro_condominio)
        self._login_devquad()
        r = self.client.post(reverse("propuesta-numero-emergencia-aprobar", args=[propuesta.pk]))
        self.assertEqual(r.status_code, 404)


class NumeroEmergenciaListViewPropuestasContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Contexto Propuestas", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="ctx_prop_residente")
        self.otro_residente = crear_membresia(self.condominio, "residente", username="ctx_prop_residente_2")
        self.devquad = crear_devquad("ctx_prop_devquad")

    def test_residente_no_ve_las_propuestas_pendientes_de_todos(self):
        from .models import PropuestaNumeroEmergencia

        PropuestaNumeroEmergencia.objects.create(condominio=self.condominio, autor=self.otro_residente, categoria="otro", nombre="Otra", telefono="111")
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertNotIn("propuestas_pendientes", r.context)

    def test_devquad_ve_las_propuestas_pendientes_de_todos(self):
        from .models import PropuestaNumeroEmergencia

        propuesta = PropuestaNumeroEmergencia.objects.create(condominio=self.condominio, autor=self.residente, categoria="otro", nombre="Otra", telefono="111")
        self.client.force_login(self.devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertEqual(list(r.context["propuestas_pendientes"]), [propuesta])

    def test_cada_quien_ve_solo_sus_propias_propuestas(self):
        from .models import PropuestaNumeroEmergencia

        propia = PropuestaNumeroEmergencia.objects.create(condominio=self.condominio, autor=self.residente, categoria="otro", nombre="Propia", telefono="111")
        PropuestaNumeroEmergencia.objects.create(condominio=self.condominio, autor=self.otro_residente, categoria="otro", nombre="Ajena", telefono="222")

        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numeros-emergencia"))
        self.assertEqual(list(r.context["mis_propuestas"]), [propia])
