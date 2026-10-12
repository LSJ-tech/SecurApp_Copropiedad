from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .views import EMAIL_CONTACTO_DEVQUAD

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("registro/", views.RegistroCondominioView.as_view(), name="registro-condominio"),
    path("solicitar-acceso/", views.SolicitarAccesoView.as_view(), name="solicitar-acceso"),
    path("unirme/<uuid:token>/", views.RegistroResidenteView.as_view(), name="registro-residente"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "contrasena/recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="core/password_reset_form.html",
            email_template_name="core/emails/password_reset.txt",
            html_email_template_name="core/emails/password_reset.html",
            subject_template_name="core/emails/password_reset_subject.txt",
            extra_email_context={"platform_name": settings.PLATFORM_NAME, "email_contacto": EMAIL_CONTACTO_DEVQUAD},
            success_url=reverse_lazy("password-reset-enviado"),
        ),
        name="password-reset",
    ),
    path(
        "contrasena/recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(template_name="core/password_reset_done.html"),
        name="password-reset-enviado",
    ),
    path(
        "contrasena/recuperar/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(
            template_name="core/password_reset_confirm.html",
            success_url=reverse_lazy("password-reset-listo"),
        ),
        name="password-reset-confirmar",
    ),
    path(
        "contrasena/recuperar/listo/",
        auth_views.PasswordResetCompleteView.as_view(template_name="core/password_reset_complete.html"),
        name="password-reset-listo",
    ),
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
    path("admin-utils/buscar-borrados/", views.buscar_borrados, name="buscar-borrados"),
    path("admin-utils/normalizar-nombres/", views.normalizar_nombres_existentes, name="normalizar-nombres"),
    path("admin-utils/corregir-etiqueta-unidad-empart/", views.corregir_etiqueta_unidad_empart, name="corregir-etiqueta-unidad-empart"),
    path("admin-utils/cargar-torres-empart/", views.cargar_torres_empart, name="cargar-torres-empart"),
    path("admin-utils/agregar-departamentos-1-2-empart/", views.agregar_departamentos_1_2_empart, name="agregar-departamentos-1-2-empart"),
    path("directorio/", views.DirectorioVecinosView.as_view(), name="directorio"),
    path("invitar/", views.CompartirInvitacionView.as_view(), name="compartir-invitacion"),
    path("miembros/", views.MiembroListView.as_view(), name="miembros"),
    path("miembros/nuevo/", views.CrearMiembroView.as_view(), name="crear-miembro"),
    path("torres/", views.TorreListView.as_view(), name="torres"),
    path("torres/nueva/", views.TorreCreateView.as_view(), name="crear-torre"),
    path("unidades/", views.UnidadListView.as_view(), name="unidades"),
    path("unidades/nueva/", views.UnidadCreateView.as_view(), name="crear-unidad"),
    path("unidades/aplicar-alicuota/", views.AplicarAlicuotaMasivaView.as_view(), name="aplicar-alicuota-masiva"),
]
