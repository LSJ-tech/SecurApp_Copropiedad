from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("registro/", views.RegistroCondominioView.as_view(), name="registro-condominio"),
    path("solicitar-acceso/", views.SolicitarAccesoView.as_view(), name="solicitar-acceso"),
    path("unirme/<uuid:token>/", views.RegistroResidenteView.as_view(), name="registro-residente"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("mi-perfil/", views.MiPerfilView.as_view(), name="mi-perfil"),
    path("mi-perfil/cambiar-contrasena/", views.MiCambiarContrasenaView.as_view(), name="cambiar-contrasena"),
    path("mi-perfil/eliminar-cuenta/", views.SolicitarEliminacionView.as_view(), name="solicitar-eliminacion"),
    path("cuenta-desactivada/", views.CuentaDesactivadaView.as_view(), name="cuenta-desactivada"),
    path("privacidad/", views.PrivacidadView.as_view(), name="privacidad"),
    path("terminos/", views.TerminosView.as_view(), name="terminos"),
    path("aceptar-terminos/", views.AceptarTerminosView.as_view(), name="aceptar-terminos"),
    path("offline/", views.OfflineView.as_view(), name="offline"),
    path("sw.js", views.ServiceWorkerView.as_view(), name="service-worker"),
    path("mi-condominio/", views.CondominioUpdateView.as_view(), name="mi-condominio"),
    path("mi-condominio/qr-residentes.png", views.QRRegistroResidentesView.as_view(), name="qr-registro-residentes"),
    path("mi-condominio/regenerar-link-residentes/", views.RegenerarTokenResidentesView.as_view(), name="regenerar-token-residentes"),
    path("admin-utils/probar-correo/", views.probar_correo, name="probar-correo"),
    path("admin-utils/listar-condominios/", views.listar_condominios, name="listar-condominios"),
    path("admin-utils/cargar-torres-empart/", views.cargar_torres_empart, name="cargar-torres-empart"),
    path("admin-utils/agregar-departamentos-1-2-empart/", views.agregar_departamentos_1_2_empart, name="agregar-departamentos-1-2-empart"),
    path("miembros/", views.MiembroListView.as_view(), name="miembros"),
    path("miembros/nuevo/", views.CrearMiembroView.as_view(), name="crear-miembro"),
    path("torres/", views.TorreListView.as_view(), name="torres"),
    path("torres/nueva/", views.TorreCreateView.as_view(), name="crear-torre"),
    path("unidades/", views.UnidadListView.as_view(), name="unidades"),
    path("unidades/nueva/", views.UnidadCreateView.as_view(), name="crear-unidad"),
    path("unidades/aplicar-alicuota/", views.AplicarAlicuotaMasivaView.as_view(), name="aplicar-alicuota-masiva"),
]
