from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Condominio, Membresia

from .models import Aviso, AvisoLectura, Publicacion


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


class AvisoLecturaTests(TestCase):
    """Confirmación de lectura: cualquier miembro puede marcar un aviso como
    visto, pero las estadísticas ("Visto por X de Y vecinos") solo las ve
    directiva/administración -- a un residente no le aporta nada."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Lectura Avisos", plan="premium")
        cls.otro_condominio = Condominio.objects.create(nombre="Test Lectura Avisos B", plan="premium")

    def setUp(self):
        self.directiva = crear_membresia(self.condominio, "directiva", username="lectura_directiva")
        self.residente = crear_membresia(self.condominio, "residente", username="lectura_residente")
        self.otro_residente = crear_membresia(self.condominio, "residente", username="lectura_residente_2")
        self.aviso = Aviso.objects.create(condominio=self.condominio, autor=self.directiva, titulo="Corte de agua", cuerpo="Mañana de 9 a 12.")

    def test_marcar_leido_crea_el_registro(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("aviso-marcar-leido", args=[self.aviso.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AvisoLectura.objects.filter(aviso=self.aviso, membresia=self.residente).exists())

    def test_marcar_leido_es_idempotente(self):
        self.client.force_login(self.residente.user)
        self.client.post(reverse("aviso-marcar-leido", args=[self.aviso.pk]))
        r = self.client.post(reverse("aviso-marcar-leido", args=[self.aviso.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AvisoLectura.objects.filter(aviso=self.aviso, membresia=self.residente).count(), 1)

    def test_no_puede_marcar_leido_un_aviso_de_otro_condominio(self):
        autor_ajeno = crear_membresia(self.otro_condominio, "directiva", username="lectura_directiva_ajena")
        aviso_ajeno = Aviso.objects.create(condominio=self.otro_condominio, autor=autor_ajeno, titulo="Ajeno", cuerpo="...")
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("aviso-marcar-leido", args=[aviso_ajeno.pk]))
        self.assertEqual(r.status_code, 404)

    def test_residente_no_ve_las_estadisticas_de_lectura(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("aviso-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertIsNone(resultados[0]["leido_por_count"])
        self.assertIsNone(resultados[0]["total_destinatarios"])

    def test_directiva_ve_cuantos_vecinos_lo_han_visto(self):
        AvisoLectura.objects.create(aviso=self.aviso, membresia=self.residente)
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("aviso-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual(resultados[0]["leido_por_count"], 1)
        self.assertEqual(resultados[0]["total_destinatarios"], 3)


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

    def test_el_listado_no_crece_en_queries_por_fila(self):
        """autor es un Membresia, y Membresia.__str__ toca autor.user y
        autor.condominio -- sin list_select_related, cada fila nueva sumaría
        2 queries más. Confirma que el total no depende de cuántas filas hay."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        condominio = Condominio.objects.create(nombre="Test N+1 Aviso", plan="premium")
        staff = User.objects.create_superuser(username="n1_aviso_staff", password="x")
        self.client.force_login(staff)

        autor = crear_membresia(condominio, "directiva", username="n1_aviso_autor_0")
        Aviso.objects.create(condominio=condominio, autor=autor, titulo="Aviso 0", cuerpo="...")
        with CaptureQueriesContext(connection) as ctx_una_fila:
            self.client.get("/admin/comunicacion/aviso/")

        for i in range(1, 4):
            autor = crear_membresia(condominio, "directiva", username=f"n1_aviso_autor_{i}")
            Aviso.objects.create(condominio=condominio, autor=autor, titulo=f"Aviso {i}", cuerpo="...")
        with CaptureQueriesContext(connection) as ctx_cuatro_filas:
            self.client.get("/admin/comunicacion/aviso/")

        self.assertEqual(len(ctx_una_fila.captured_queries), len(ctx_cuatro_filas.captured_queries))


class PublicacionApiTests(TestCase):
    """Muro de vecinos: a diferencia de Aviso, CUALQUIER miembro puede
    publicar -- solo borrar queda restringido al autor o a directiva/
    administración (moderación, ver EsAutorODirectivaOAdministracion)."""

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Muro A", plan="premium")
        cls.otro_condominio = Condominio.objects.create(nombre="Test Muro B", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="muro_residente")
        self.otro_residente = crear_membresia(self.condominio, "residente", username="muro_otro_residente")
        self.directiva = crear_membresia(self.condominio, "directiva", username="muro_directiva")

    def test_cualquier_rol_puede_publicar(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(reverse("publicacion-list"), {"categoria": "se_vende", "titulo": "Bicicleta", "cuerpo": "Poco uso"})
        self.assertEqual(r.status_code, 201)
        publicacion = Publicacion.objects.get(titulo="Bicicleta")
        self.assertEqual(publicacion.condominio, self.condominio)
        self.assertEqual(publicacion.autor, self.residente)

    def test_lista_solo_las_del_propio_condominio(self):
        Publicacion.objects.create(condominio=self.condominio, autor=self.residente, titulo="Propia", cuerpo="...")
        autor_ajeno = crear_membresia(self.otro_condominio, "residente", username="muro_ajeno")
        Publicacion.objects.create(condominio=self.otro_condominio, autor=autor_ajeno, titulo="Ajena", cuerpo="...")

        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("publicacion-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([p["titulo"] for p in resultados], ["Propia"])

    def test_el_autor_puede_borrar_lo_suyo(self):
        publicacion = Publicacion.objects.create(condominio=self.condominio, autor=self.residente, titulo="Mía", cuerpo="...")
        self.client.force_login(self.residente.user)
        r = self.client.delete(reverse("publicacion-detail", args=[publicacion.pk]))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Publicacion.objects.filter(pk=publicacion.pk).exists())

    def test_otro_residente_no_puede_borrar_lo_ajeno(self):
        publicacion = Publicacion.objects.create(condominio=self.condominio, autor=self.residente, titulo="Mía", cuerpo="...")
        self.client.force_login(self.otro_residente.user)
        r = self.client.delete(reverse("publicacion-detail", args=[publicacion.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Publicacion.objects.filter(pk=publicacion.pk).exists())

    def test_directiva_puede_moderar_borrando_lo_de_cualquiera(self):
        publicacion = Publicacion.objects.create(condominio=self.condominio, autor=self.residente, titulo="Mía", cuerpo="...")
        self.client.force_login(self.directiva.user)
        r = self.client.delete(reverse("publicacion-detail", args=[publicacion.pk]))
        self.assertEqual(r.status_code, 204)

    def test_puede_eliminar_refleja_quien_consulta(self):
        Publicacion.objects.create(condominio=self.condominio, autor=self.residente, titulo="Mía", cuerpo="...")

        self.client.force_login(self.otro_residente.user)
        r = self.client.get(reverse("publicacion-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertFalse(resultados[0]["puede_eliminar"])

        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("publicacion-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertTrue(resultados[0]["puede_eliminar"])


class PublicacionSoloTorreTests(TestCase):
    """Un residente puede acotar su publicación a su propia torre en vez de
    todo el condominio -- directiva/administración/conserjería siguen
    viendo todo, porque gestionan/moderan el condominio completo."""

    @classmethod
    def setUpTestData(cls):
        from core.models import Torre, Unidad

        cls.condominio = Condominio.objects.create(nombre="Test Muro Torre", plan="premium")
        cls.torre1 = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.torre2 = Torre.objects.create(condominio=cls.condominio, nombre="2")
        cls.unidad_t1 = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre1, numero="101")
        cls.unidad_t2 = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre2, numero="201")

    def setUp(self):
        self.residente_t1 = crear_membresia(self.condominio, "residente", username="muro_torre_r1")
        self.residente_t1.unidad = self.unidad_t1
        self.residente_t1.save(update_fields=["unidad"])

        self.residente_t2 = crear_membresia(self.condominio, "residente", username="muro_torre_r2")
        self.residente_t2.unidad = self.unidad_t2
        self.residente_t2.save(update_fields=["unidad"])

        self.residente_sin_unidad = crear_membresia(self.condominio, "residente", username="muro_torre_sin_unidad")
        self.directiva = crear_membresia(self.condominio, "directiva", username="muro_torre_directiva")

    def test_solo_mi_torre_usa_la_torre_del_autor(self):
        self.client.force_login(self.residente_t1.user)
        r = self.client.post(reverse("publicacion-list"), {
            "categoria": "otro", "titulo": "Fuga de agua", "cuerpo": "En el pasillo del 3er piso", "solo_mi_torre": True,
        })
        self.assertEqual(r.status_code, 201)
        publicacion = Publicacion.objects.get(titulo="Fuga de agua")
        self.assertEqual(publicacion.torre, self.torre1)

    def test_sin_marcar_queda_para_todo_el_condominio(self):
        self.client.force_login(self.residente_t1.user)
        self.client.post(reverse("publicacion-list"), {"categoria": "otro", "titulo": "General", "cuerpo": "..."})
        self.assertIsNone(Publicacion.objects.get(titulo="General").torre)

    def test_residente_de_otra_torre_no_ve_la_publicacion_acotada(self):
        Publicacion.objects.create(condominio=self.condominio, autor=self.residente_t1, torre=self.torre1, titulo="Solo T1", cuerpo="...")
        self.client.force_login(self.residente_t2.user)
        r = self.client.get(reverse("publicacion-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([p["titulo"] for p in resultados], [])

    def test_residente_de_la_misma_torre_si_la_ve(self):
        Publicacion.objects.create(condominio=self.condominio, autor=self.residente_t1, torre=self.torre1, titulo="Solo T1", cuerpo="...")
        self.client.force_login(self.residente_t1.user)
        r = self.client.get(reverse("publicacion-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([p["titulo"] for p in resultados], ["Solo T1"])

    def test_publicacion_del_condominio_completo_la_ven_todos(self):
        Publicacion.objects.create(condominio=self.condominio, autor=self.residente_t1, titulo="General", cuerpo="...")
        self.client.force_login(self.residente_t2.user)
        r = self.client.get(reverse("publicacion-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([p["titulo"] for p in resultados], ["General"])

    def test_directiva_ve_las_de_cualquier_torre(self):
        Publicacion.objects.create(condominio=self.condominio, autor=self.residente_t1, torre=self.torre1, titulo="Solo T1", cuerpo="...")
        Publicacion.objects.create(condominio=self.condominio, autor=self.residente_t2, torre=self.torre2, titulo="Solo T2", cuerpo="...")
        self.client.force_login(self.directiva.user)
        r = self.client.get(reverse("publicacion-list"))
        resultados = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual({p["titulo"] for p in resultados}, {"Solo T1", "Solo T2"})

    def test_residente_sin_unidad_no_puede_acotar(self):
        self.client.force_login(self.residente_sin_unidad.user)
        r = self.client.post(reverse("publicacion-list"), {
            "categoria": "otro", "titulo": "Sin unidad", "cuerpo": "...", "solo_mi_torre": True,
        })
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(Publicacion.objects.get(titulo="Sin unidad").torre)

    def test_la_pagina_ofrece_la_opcion_solo_a_quien_tiene_torre(self):
        self.client.force_login(self.residente_t1.user)
        r = self.client.get(reverse("muro-vecinos"))
        self.assertContains(r, "Publicar solo para")

        self.client.force_login(self.residente_sin_unidad.user)
        r = self.client.get(reverse("muro-vecinos"))
        self.assertNotContains(r, "Publicar solo para")


class MuroVecinosViewTests(TestCase):
    def test_cualquier_rol_puede_entrar(self):
        condominio = Condominio.objects.create(nombre="Test Muro Pagina", plan="premium")
        residente = crear_membresia(condominio, "residente", username="muro_pagina_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("muro-vecinos"))
        self.assertEqual(r.status_code, 200)
