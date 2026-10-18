import logging
import uuid
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import password_validators_help_texts
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.views import PasswordResetConfirmView as _PasswordResetConfirmView
from django.contrib.staticfiles.finders import find as find_static
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Length
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView
from django.views.generic.base import View

from .comunas_chile import COMUNAS_POR_REGION
from .forms import CrearCondominioForm, CrearMiembroForm, MiCambiarContrasenaForm, MiPerfilForm, RegistroResidenteForm, SolicitudAccesoForm, TorreForm, UnidadForm, _normalizar_nombre
from .mixins import MENSAJE_SIN_CONDOMINIO, CondominioFormMixin, CondominioRequiredMixin, SoloStaffMixin, condominio_activo_devquad
from .mixins import DEVQUAD_CONDOMINIO_SESSION_KEY
from .models import Condominio, Membresia, SolicitudEliminacion, Torre, Unidad
from .usuarios import generar_password_temporal, generar_username

EMAIL_CONTACTO_DEVQUAD = "contacto@devquad.cl"
CONTENT_TYPE_TEXTO_PLANO = "text/plain; charset=utf-8"
logger = logging.getLogger(__name__)


def enviar_correo_bienvenida(user, condominio):
    """Correo de bienvenida a un miembro nuevo -- nunca incluye la contraseña
    (ya sea porque la eligió él mismo al autoregistrarse, o porque es
    temporal y se entrega aparte, ver CrearMiembroView). No bloquea el alta
    si Resend falla: el correo es un plus, no un requisito."""
    login_url = "https://securapp.devquad.cl/login/"
    contexto = {
        "platform_name": settings.PLATFORM_NAME,
        "nombre": user.first_name,
        "condominio_nombre": condominio.nombre,
        "username": user.username,
        "login_url": login_url,
        "email_contacto": EMAIL_CONTACTO_DEVQUAD,
    }
    texto_plano = (
        f"Hola {user.first_name},\n\n"
        f"Tu cuenta en {condominio.nombre} ya está lista en {settings.PLATFORM_NAME}. Desde ahí puedes:\n\n"
        f"- Activar el botón de pánico si tienes una emergencia -- avisa a todo el condominio al instante.\n"
        f"- Ver los avisos de tu directiva/administración.\n"
        f"- Revisar tus gastos comunes.\n\n"
        f"Entra con tu usuario «{user.username}» en {login_url}\n\n"
        f"Cualquier duda, escríbenos a {EMAIL_CONTACTO_DEVQUAD}."
    )
    try:
        correo = EmailMultiAlternatives(
            subject=f"¡Bienvenido a {settings.PLATFORM_NAME}, {user.first_name}!",
            body=texto_plano,
            from_email=None,
            to=[user.email],
        )
        correo.attach_alternative(render_to_string("core/emails/bienvenida.html", contexto), "text/html")
        correo.send()
    except Exception:
        logger.exception("No se pudo enviar el correo de bienvenida a %s (usuario %s, condominio %s).", user.email, user.username, condominio.nombre)


def enviar_correo_eliminacion_confirmada(solicitud):
    """Se manda cuando DevQuad marca la SolicitudEliminacion como atendida
    (ver marcar_atendida en core/admin.py) -- usa solicitud.email (copia
    tomada al momento del pedido), nunca membresia.user.email, porque para
    cuando se marca atendida la cuenta ya puede estar eliminada. No bloquea
    la acción del admin si Resend falla."""
    if not solicitud.email:
        logger.warning("SolicitudEliminacion #%s marcada atendida sin email guardado -- no se pudo avisar.", solicitud.pk)
        return
    contexto = {
        "platform_name": settings.PLATFORM_NAME,
        "nombre": solicitud.nombre,
        "email_contacto": EMAIL_CONTACTO_DEVQUAD,
    }
    texto_plano = (
        f"Hola {solicitud.nombre},\n\n"
        f"Confirmamos que tu cuenta y tus datos personales en {settings.PLATFORM_NAME} ya fueron eliminados, "
        f"según tu solicitud.\n\n"
        f"Cualquier duda, escríbenos a {EMAIL_CONTACTO_DEVQUAD}."
    )
    try:
        correo = EmailMultiAlternatives(
            subject=f"Tu cuenta en {settings.PLATFORM_NAME} fue eliminada",
            body=texto_plano,
            from_email=None,
            to=[solicitud.email],
        )
        correo.attach_alternative(render_to_string("core/emails/eliminacion_confirmada.html", contexto), "text/html")
        correo.send()
    except Exception:
        logger.exception("No se pudo enviar el correo de confirmación de eliminación a %s (solicitud #%s).", solicitud.email, solicitud.pk)


@staff_member_required
@require_GET
def probar_correo(request):
    """Diagnóstico manual: confirma que RESEND_API_KEY está bien configurada en el hosting."""
    destino = request.GET.get("destino", "")
    try:
        validate_email(destino)
    except ValidationError:
        return HttpResponse("Agrega ?destino=tu@email.com (una dirección válida) a la URL.", status=400)
    send_mail(
        subject="Correo de prueba de SecurApp Copropiedad",
        message="Si recibiste esto, el envío de correo (Resend) está funcionando correctamente.",
        from_email=None,
        recipient_list=[destino],
    )
    return HttpResponse(f"Correo de prueba enviado a {escape(destino)}.")


@staff_member_required
@require_GET
def normalizar_nombres_existentes(request):
    """Uso único: los formularios de registro/alta ya normalizan nombre y
    apellido desde ahora (ver _normalizar_nombre en core/forms.py), pero eso
    no corrige lo que ya quedó guardado en producción con mayúsculas/
    minúsculas inconsistentes (ej. "juan perez", "JUAN PEREZ"). Idempotente:
    correrla de nuevo no cambia nada que ya esté bien."""
    cambiados = []
    for user in User.objects.exclude(first_name="", last_name=""):
        nuevo_first = _normalizar_nombre(user.first_name) if user.first_name else user.first_name
        nuevo_last = _normalizar_nombre(user.last_name) if user.last_name else user.last_name
        if nuevo_first != user.first_name or nuevo_last != user.last_name:
            cambiados.append(f"{user.username}: {user.first_name!r} {user.last_name!r} -> {nuevo_first!r} {nuevo_last!r}")
            user.first_name = nuevo_first
            user.last_name = nuevo_last
            user.save(update_fields=["first_name", "last_name"])
    if not cambiados:
        return HttpResponse("Ningún nombre necesitaba normalizarse.", content_type=CONTENT_TYPE_TEXTO_PLANO)
    return HttpResponse(f"{len(cambiados)} usuario(s) corregido(s):\n" + "\n".join(cambiados), content_type=CONTENT_TYPE_TEXTO_PLANO)


@staff_member_required
@require_GET
def buscar_borrados(request):
    """Diagnóstico manual: busca en el registro de auditoría del admin de
    Django (LogEntry) qué se borró y cuándo, filtrando por `?q=`.
    `LogEntry.object_repr` guarda el __str__ del objeto en el momento del
    borrado (ej. "jlroman (Residente de Población Empart)" para una
    Membresia, o el username a secas para un User) -- útil para confirmar
    qué modelo se borró exactamente, pero NO permite reconstruir los datos
    por sí solo (no guarda una copia serializada del objeto)."""
    from django.contrib.admin.models import LogEntry

    q = request.GET.get("q", "").strip()
    entradas = LogEntry.objects.filter(action_flag=3).select_related("user", "content_type").order_by("-action_time")
    if q:
        entradas = entradas.filter(object_repr__icontains=q)
    entradas = entradas[:50]

    if not entradas:
        q_seguro = escape(q)
        return HttpResponse(f"Sin borrados registrados{f' que coincidan con {q_seguro!r}' if q_seguro else ''}.", content_type=CONTENT_TYPE_TEXTO_PLANO)

    lineas = [
        f"{e.action_time:%Y-%m-%d %H:%M} | modelo={e.content_type.model if e.content_type else '?'} | "
        f"borrado_por={e.user.username if e.user else '?'} | object_repr={e.object_repr!r}"
        for e in entradas
    ]
    return HttpResponse("\n".join(lineas), content_type=CONTENT_TYPE_TEXTO_PLANO)


@staff_member_required
@require_GET
def listar_condominios(request):
    """Diagnóstico manual: nombre exacto, torres y unidades de cada condominio real en esta base de datos."""
    lineas = []
    condominios = Condominio.objects.order_by("nombre").annotate(
        _torres=Count("torres", distinct=True), _unidades=Count("unidades", distinct=True), _miembros=Count("membresias", distinct=True),
    )
    for condominio in condominios:
        lineas.append(
            f"id={condominio.pk} | nombre={condominio.nombre!r} | torres={condominio._torres} | "
            f"unidades={condominio._unidades} | miembros={condominio._miembros} | "
            f"direccion={condominio.direccion!r} | comuna={condominio.comuna!r} | region={condominio.region!r}"
        )
    return HttpResponse("\n".join(lineas) or "No hay condominios.", content_type=CONTENT_TYPE_TEXTO_PLANO)


def _condominio_empart_o_error():
    """Busca el único condominio real cuyo nombre contiene "Empart" (no
    exacto -- el usuario le cambió el nombre a "Población Empart" después de
    que estas vistas se escribieron) -- usado por las 3 vistas de uso único
    que operan sobre ese condominio en producción. Devuelve (condominio,
    None) si lo encuentra, o (None, HttpResponse de error 404/409) si no."""
    condominios = Condominio.objects.filter(nombre__icontains="Empart")
    if not condominios.exists():
        return None, HttpResponse("No existe ningún condominio cuyo nombre contenga 'Empart'.", status=404)
    if condominios.count() > 1:
        nombres = ", ".join(repr(c.nombre) for c in condominios)
        return None, HttpResponse(f"Hay más de un condominio que contiene 'Empart', no sé cuál usar: {nombres}.", status=409)
    return condominios.get(), None


@staff_member_required
@require_GET
def corregir_etiqueta_unidad_empart(request):
    """Uso único: la etiqueta_unidad de Población Empart quedó guardada como
    "Departamentos" (plural) en vez de "Departamento" (singular) -- el resto
    del sistema agrega la "s" solo cuando corresponde, así que en plural
    quedaba duplicada ("Departamentoss", "Nuevo departamentos"). Idempotente."""
    condominio, error = _condominio_empart_o_error()
    if error:
        return error

    valor_anterior = condominio.etiqueta_unidad
    if valor_anterior == "Departamento":
        return HttpResponse(f"etiqueta_unidad de {condominio.nombre!r} ya es 'Departamento', no se tocó nada.", content_type=CONTENT_TYPE_TEXTO_PLANO)

    condominio.etiqueta_unidad = "Departamento"
    condominio.save(update_fields=["etiqueta_unidad"])
    return HttpResponse(
        f"etiqueta_unidad de {condominio.nombre!r} corregida: {valor_anterior!r} -> 'Departamento'.",
        content_type=CONTENT_TYPE_TEXTO_PLANO,
    )


@staff_member_required
@require_GET
def cargar_torres_empart(request):
    """
    Uso único: completa el condominio real de Empart en producción con sus
    16 torres confirmadas x 5 pisos x 4 deptos (320 unidades). Idempotente
    (get_or_create) -- correrla más de una vez no duplica nada. No toca
    miembros ni unidades que ya existan.

    Busca por "Empart" dentro del nombre (no exacto) -- el nombre real del
    condominio cambió a "Población Empart" después de que esto se escribió.
    """
    condominio, error = _condominio_empart_o_error()
    if error:
        return error

    numeros_por_piso = ["1", "2", "3", "4"]
    pisos = ["1", "2", "3", "4", "5"]
    torres_nombres = [str(n) for n in range(1, 17)]

    torres_creadas = 0
    unidades_creadas = 0
    with transaction.atomic():
        for nombre_torre in torres_nombres:
            torre, creada = Torre.objects.get_or_create(condominio=condominio, nombre=nombre_torre)
            if creada:
                torres_creadas += 1
            for piso in pisos:
                for posicion in numeros_por_piso:
                    numero = f"{piso}{posicion}"
                    _, creada = Unidad.objects.get_or_create(condominio=condominio, torre=torre, numero=numero)
                    if creada:
                        unidades_creadas += 1

    return HttpResponse(
        f"Listo. Torres nuevas: {torres_creadas} (de 16). Unidades nuevas: {unidades_creadas} (de 320 esperadas)."
    )


@staff_member_required
@require_GET
def agregar_departamentos_1_2_empart(request):
    """
    Uso único: agrega los departamentos "1" y "2" (plantas bajas, fuera del
    esquema piso+posición de los otros 320) a cada uno de los 16 blocks del
    condominio real de Empart en producción. Idempotente (get_or_create) --
    correrla más de una vez no duplica nada.

    Busca por "Empart" dentro del nombre (no exacto) -- el usuario le cambió
    el nombre real a "Población Empart" después de cargar las torres, así
    que un match exacto a "Empart" ya no encuentra el condominio.
    """
    condominio, error = _condominio_empart_o_error()
    if error:
        return error

    torres = list(condominio.torres.all())
    if not torres:
        return HttpResponse("Empart no tiene blocks cargados todavía -- corre primero cargar_torres_empart.", status=400)

    unidades_creadas = 0
    with transaction.atomic():
        for torre in torres:
            for numero in ("1", "2"):
                _, creada = Unidad.objects.get_or_create(condominio=condominio, torre=torre, numero=numero)
                if creada:
                    unidades_creadas += 1

    return HttpResponse(
        f"Listo. Departamentos nuevos: {unidades_creadas} (de {len(torres) * 2} esperados, 2 por cada uno de los {len(torres)} blocks)."
    )


class SolicitarAccesoView(FormView):
    """Formulario público embebido en la landing -- captura el interés de quien todavía no tiene código."""

    template_name = "core/registro_condominio.html"  # no se usa directo: el form vive embebido en landing.html
    form_class = SolicitudAccesoForm
    success_url = reverse_lazy("inicio")

    def form_valid(self, form):
        solicitud = form.save()
        try:
            send_mail(
                subject=f"Nueva solicitud de acceso a SecurApp Copropiedad: {solicitud.condominio}",
                message=(
                    f"Nombre: {solicitud.nombre}\nCondominio: {solicitud.condominio}\nComuna: {solicitud.comuna}\n"
                    f"Teléfono: {solicitud.telefono}\nEmail: {solicitud.email}\nMensaje: {solicitud.mensaje}\n\n"
                    f"Gestionar en /admin/core/solicitudacceso/"
                ),
                from_email=None,
                recipient_list=[EMAIL_CONTACTO_DEVQUAD],
            )
        except Exception:
            # el lead ya quedó guardado -- el correo es solo un aviso, no bloquea
            # la solicitud -- pero si falla queda registrado en los logs de
            # Render, no desaparece en silencio (ver incidente real del correo
            # de bienvenida, mismo patrón).
            logger.exception("No se pudo avisar por correo de la nueva solicitud de acceso de %s (%s).", solicitud.nombre, solicitud.condominio)
        messages.success(self.request, "¡Gracias! Recibimos tu solicitud y te vamos a contactar pronto.")
        return redirect("inicio")

    def form_invalid(self, form):
        messages.error(self.request, "No pudimos enviar tu solicitud — revisa los datos e inténtalo de nuevo.")
        return redirect("inicio")


class RegistroResidenteView(FormView):
    """Autoregistro público de residente -- el link/QR trae el token del condominio, el residente elige su depto."""

    template_name = "core/registro_residente.html"
    form_class = RegistroResidenteForm

    def dispatch(self, request, *args, **kwargs):
        self.condominio = get_object_or_404(Condominio, token_registro_residentes=kwargs["token"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["condominio"] = self.condominio
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["condominio"] = self.condominio
        context["torres"] = (
            Torre.objects.filter(condominio=self.condominio)
            .annotate(_len=Length("nombre")).order_by("_len", "nombre")
        )
        unidades = (
            Unidad.objects.filter(condominio=self.condominio)
            .annotate(_len=Length("numero")).order_by("torre_id", "_len", "numero")
        )
        unidades_por_torre = {}
        hay_sin_torre = False
        for unidad in unidades:
            clave = str(unidad.torre_id) if unidad.torre_id else "sin-torre"
            hay_sin_torre = hay_sin_torre or clave == "sin-torre"
            unidades_por_torre.setdefault(clave, []).append({"id": unidad.pk, "numero": unidad.numero})
        context["unidades_por_torre"] = unidades_por_torre
        context["hay_unidades_sin_torre"] = hay_sin_torre
        # Lista de números ya registrados por otros vecinos, para que quien
        # se registra por texto libre (su depto/casa no está en la lista,
        # ver RegistroResidenteForm) vea los números ya usados antes de
        # escribir el suyo y no cree sin querer un casi-duplicado por una
        # diferencia de tipeo. Las calles solo aplican en modo casas.
        context["numeros_unidad_existentes"] = list(unidades.values_list("numero", flat=True))
        if context["torres"].exists():
            # Para el datalist de "torre_unidad_libre" (ver RegistroResidenteForm)
            # -- es texto libre pero tiene que calzar exacto (sin mayúsculas/
            # minúsculas) con una torre ya creada, así que ayuda tenerlas a mano.
            context["torres_existentes"] = list(context["torres"].values_list("nombre", flat=True))
        else:
            context["calles_existentes"] = sorted(set(unidades.exclude(calle="").values_list("calle", flat=True)))
        return context

    def form_valid(self, form):
        datos = form.cleaned_data
        username = generar_username(datos["nombre"], datos["apellido"])
        user = User.objects.create_user(
            username=username, password=datos["password1"], email=datos.get("email", ""),
            first_name=datos["nombre"], last_name=datos["apellido"],
        )
        Membresia.objects.create(
            user=user, condominio=self.condominio, unidad=datos["unidad"], rol="residente",
            terminos_aceptados_en=timezone.now(),
        )
        if user.email:
            enviar_correo_bienvenida(user, self.condominio)
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            self.request,
            f"¡Bienvenido a {self.condominio.nombre}! Tu usuario es «{username}» — anótalo, lo necesitas para "
            f"volver a entrar. Desde aquí puedes activar el botón de pánico, ver los avisos de tu condominio y "
            f"revisar tus gastos comunes.",
        )
        return redirect("inicio")


def _contexto_invitacion(request, condominio):
    link = request.build_absolute_uri(
        reverse("registro-residente", kwargs={"token": condominio.token_registro_residentes})
    )
    mensaje = (
        f"🏠 ¡Hola, vecino/a!\n\n"
        # "tu {etiqueta}" en vez de "nuestro/nuestra {etiqueta}" a propósito --
        # "tu" no cambia con el género de la palabra (condominio, junta de
        # vecinos, comunidad...), así que no hace falta saber el género de
        # etiqueta_organizacion para que la frase quede bien armada.
        f"Te invito a unirte a *SecurApp* 🔐, la app de tu {condominio.etiqueta_organizacion.lower()} *{condominio.nombre}*.\n\n"
        f"Desde ahí puedes:\n"
        f"✅ Activar el botón de pánico\n"
        f"✅ Ver avisos y alertas\n"
        f"✅ Revisar tus gastos comunes\n\n"
        f"Crea tu cuenta eligiendo tu {condominio.etiqueta_unidad.lower()} acá 👇\n"
        f"{link}"
    )
    return {"link_autoregistro": link, "mensaje_whatsapp_invitacion": mensaje}


class QRRegistroResidentesView(CondominioRequiredMixin, View):
    """Abierto a cualquier rol -- es solo lectura y el link que codifica es el
    mismo que ya puede ver/copiar cualquier miembro en CompartirInvitacionView."""

    def get(self, request):
        url = request.build_absolute_uri(
            reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes})
        )
        imagen = qrcode.make(url)
        buffer = BytesIO()
        imagen.save(buffer, format="PNG")
        return HttpResponse(buffer.getvalue(), content_type="image/png")


class CompartirInvitacionView(CondominioRequiredMixin, TemplateView):
    """Abierta a cualquier rol: cualquier vecino puede compartir el link/QR de
    autoregistro con otros vecinos. Regenerar el link sigue siendo exclusivo
    de la directiva (ver RegenerarTokenResidentesView), porque invalida el
    link/QR de todos los demás."""

    template_name = "core/compartir_invitacion.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_contexto_invitacion(self.request, self.condominio))
        return context


class RegenerarTokenResidentesView(SoloStaffMixin, CondominioRequiredMixin, View):
    def post(self, request):
        self.condominio.token_registro_residentes = uuid.uuid4()
        self.condominio.save(update_fields=["token_registro_residentes"])
        messages.success(request, "Se generó un link nuevo — el anterior ya no sirve para registrarse.")
        return redirect("mi-condominio")


class InicioView(TemplateView):
    """
    La raíz del sitio hace dos trabajos distintos según quién la visite:
    sin sesión, es la landing comercial; con sesión y condominio, es el
    dashboard interno. No se puede resolver con CondominioRequiredMixin
    porque ese mixin exige login antes de decidir nada.
    """

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            self.template_name = "core/landing.html"
            return super().get(request, *args, **kwargs)

        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            if request.user.is_staff:
                condominio = condominio_activo_devquad(request)
                if condominio is None:
                    return redirect("devquad-condominios")
                if not condominio.puede_operar:
                    return redirect("cuenta-desactivada")
                self.membresia = None
                self.condominio = condominio
                self.template_name = "core/inicio.html"
                return super().get(request, *args, **kwargs)
            messages.error(request, MENSAJE_SIN_CONDOMINIO)
            return redirect("login")
        if not membresia.condominio.puede_operar:
            return redirect("cuenta-desactivada")
        if not membresia.terminos_aceptados_en:
            return redirect("aceptar-terminos")

        self.membresia = membresia
        self.condominio = membresia.condominio
        self.template_name = "core/inicio.html"
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, "membresia"):
            context["membresia"] = self.membresia
            context["condominio"] = self.condominio
            if self.membresia and self.membresia.rol == "residente":
                from pagos.models import SuscripcionRecurrente
                context["total_torres"] = self.condominio.total_torres
                context["total_unidades"] = self.condominio.total_unidades
                context["total_miembros"] = Membresia.objects.filter(condominio=self.condominio).count()
                context["donacion_recurrente_activa"] = SuscripcionRecurrente.objects.filter(
                    membresia=self.membresia, tipo="donacion", estado__in=["pendiente", "autorizada"],
                ).first()
            if self.membresia is None:
                context.update(self._resumen_administracion())
        else:
            context.update(self._estadisticas_landing())
        return context

    def _estadisticas_landing(self):
        """Prueba social con números reales, no testimonios inventados --
        se recalculan solos en cada visita, directo desde la base de datos."""
        from alertas.models import Alerta

        return {
            "stat_organizaciones": Condominio.objects.filter(activo=True).count(),
            "stat_unidades": Unidad.objects.count(),
            "stat_miembros": Membresia.objects.count(),
            # Solo se muestra si ya hay al menos una -- "0 alertas resueltas"
            # no es un dato que convenza a nadie de probar la plataforma.
            "stat_alertas_resueltas": Alerta.objects.filter(estado="resuelta").count(),
        }

    def _resumen_administracion(self):
        from alertas.models import Alerta

        condominio = self.condominio
        return {
            "total_unidades": condominio.total_unidades,
            "total_miembros": Membresia.objects.filter(condominio=condominio).count(),
            "alertas_activas_count": Alerta.objects.filter(condominio=condominio, estado="activa").count(),
        }


class DevquadCondominiosView(LoginRequiredMixin, SoloStaffMixin, ListView):
    """Panel de devquad: lista todos los condominios/juntas de vecinos para
    elegir en cuál operar (ver condominio_activo_devquad en
    core/mixins.py). Reemplaza el redirect directo a /admin/ que tenía
    antes un is_staff sin Membresia propia -- panel con la misma estética
    del resto del sitio, no el admin de Django crudo."""

    model = Condominio
    template_name = "core/devquad_condominios.html"
    context_object_name = "condominios"

    def get_queryset(self):
        return super().get_queryset().order_by("nombre")


class DevquadCrearCondominioView(LoginRequiredMixin, SoloStaffMixin, CreateView):
    """Alta de un condominio nuevo desde el panel de devquad -- reemplaza
    al viejo RegistroCondominioView (público, con código de invitación):
    acá quien lo crea ya está logueado como devquad, no hace falta crear
    una cuenta nueva ni un código."""

    model = Condominio
    form_class = CrearCondominioForm
    template_name = "core/devquad_crear_condominio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comunas_por_region"] = COMUNAS_POR_REGION
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Condominio «{self.object.nombre}» creado.")
        return response

    def get_success_url(self):
        return reverse("devquad-entrar-condominio", args=[self.object.pk])


class DevquadEntrarCondominioView(LoginRequiredMixin, SoloStaffMixin, View):
    """Marca este condominio como el activo para la sesión de devquad --
    ver condominio_activo_devquad en core/mixins.py."""

    def get(self, request, *args, **kwargs):
        condominio = get_object_or_404(Condominio, pk=kwargs["pk"])
        request.session[DEVQUAD_CONDOMINIO_SESSION_KEY] = condominio.pk
        return redirect("inicio")


class DevquadSalirCondominioView(LoginRequiredMixin, SoloStaffMixin, View):
    """Limpia el condominio activo de la sesión de devquad y vuelve al listado."""

    def get(self, request, *args, **kwargs):
        request.session.pop(DEVQUAD_CONDOMINIO_SESSION_KEY, None)
        return redirect("devquad-condominios")


class CuentaDesactivadaView(TemplateView):
    template_name = "core/cuenta_desactivada.html"


class OfflineView(TemplateView):
    """A donde cae el service worker (sw.js) cuando no hay conexión -- página
    autocontenida, sin depender del Bootstrap de un CDN que tampoco cargaría
    sin red."""

    template_name = "core/offline.html"


class ServiceWorkerView(View):
    """Sirve sw.js en la raíz del sitio (no bajo /static/) para que su scope
    cubra todo el dominio -- el scope por defecto de un service worker es el
    directorio desde el que se sirve."""

    def get(self, _request, *args, **kwargs):
        ruta = find_static("core/sw.js")
        with open(ruta, "rb") as archivo:
            contenido = archivo.read()
        response = HttpResponse(contenido, content_type="application/javascript")
        response["Service-Worker-Allowed"] = "/"
        return response


class PrivacidadView(TemplateView):
    template_name = "core/privacidad.html"


class TerminosView(TemplateView):
    template_name = "core/terminos.html"


class ComoInstalarView(TemplateView):
    """Instrucciones de instalación de la PWA (agregar a pantalla de inicio)
    -- para que la directiva deje de tener que explicarlo uno por uno. Abierta
    sin login, igual que Privacidad/Términos, para poder mandar el link
    directo por WhatsApp a alguien que todavía ni se ha registrado."""

    template_name = "core/como_instalar.html"


class AceptarTerminosView(LoginRequiredMixin, View):
    """Interstitial que se muestra una sola vez por cuenta -- a propósito NO
    usa CondominioRequiredMixin (ese mixin exige haber aceptado los términos,
    así que crearía un loop infinito acá mismo)."""

    def get(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None or membresia.terminos_aceptados_en:
            return redirect("inicio")
        return render(request, "core/aceptar_terminos.html")

    def post(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            messages.error(request, MENSAJE_SIN_CONDOMINIO)
            return redirect("login")
        if not request.POST.get("acepto"):
            messages.error(request, "Tienes que aceptar los Términos de Uso y la Política de Privacidad para continuar.")
            return redirect("aceptar-terminos")
        membresia.terminos_aceptados_en = timezone.now()
        membresia.save(update_fields=["terminos_aceptados_en"])
        return redirect("inicio")


class SolicitarEliminacionView(LoginRequiredMixin, View):
    """Pide eliminar la cuenta y los datos personales -- no borra nada al tiro,
    deja la solicitud registrada y avisa a DevQuad para procesarla a mano (ver
    SolicitudEliminacion). A propósito NO usa CondominioRequiredMixin: tiene que
    seguir siendo alcanzable aunque la persona no haya aceptado los términos."""

    def get(self, request, *args, **kwargs):
        return render(request, "core/solicitar_eliminacion.html")

    def post(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        motivo = request.POST.get("motivo", "").strip()
        SolicitudEliminacion.objects.create(
            membresia=membresia,
            nombre=request.user.get_full_name() or request.user.username,
            username=request.user.username,
            email=request.user.email,
            condominio_nombre=membresia.condominio.nombre if membresia else "",
            motivo=motivo,
        )
        send_mail(
            subject=f"Solicitud de eliminación de cuenta — {request.user.get_full_name() or request.user.username}",
            message=(
                f"Usuario: {request.user.username}\n"
                f"Condominio: {membresia.condominio.nombre if membresia else '(sin condominio vinculado)'}\n"
                f"Motivo: {motivo or '(sin detalle)'}"
            ),
            from_email=None,
            recipient_list=[EMAIL_CONTACTO_DEVQUAD],
        )
        messages.success(
            request,
            "Recibimos tu solicitud. Nos vamos a poner en contacto contigo para confirmar la eliminación de tu cuenta y tus datos.",
        )
        return redirect("mi-perfil")


class DirectorioVecinosView(CondominioRequiredMixin, ListView):
    """Directorio simple -- solo nombre y block/depto. A propósito NO
    muestra usuario, email ni rol: eso sigue siendo exclusivo de devquad en
    MiembroListView. Residente ya no tiene acceso (decisión de producto);
    delegado y devquad sí."""

    template_name = "core/directorio_vecinos.html"
    context_object_name = "membresias"
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            membresia = getattr(request.user, "membresia", None)
            if membresia and membresia.rol == "residente":
                messages.error(request, "El directorio ya no está disponible para residentes.")
                return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Membresia.objects.filter(condominio=self.condominio).select_related("user", "unidad", "unidad__torre")
        return qs.annotate(
            _torre_len=Length("unidad__torre__nombre"), _num_len=Length("unidad__numero"),
        ).order_by("_torre_len", "unidad__torre__nombre", "_num_len", "unidad__numero", "user__last_name")


class MiembroListView(SoloStaffMixin, CondominioRequiredMixin, ListView):
    template_name = "core/miembro_list.html"
    context_object_name = "membresias"
    paginate_by = 50

    def get_queryset(self):
        qs = Membresia.objects.filter(condominio=self.condominio).select_related("user", "unidad", "unidad__torre")

        rol = self.request.GET.get("rol")
        if rol:
            qs = qs.filter(rol=rol)

        busqueda = self.request.GET.get("q", "").strip()
        if busqueda:
            qs = qs.filter(
                Q(user__first_name__icontains=busqueda)
                | Q(user__last_name__icontains=busqueda)
                | Q(user__username__icontains=busqueda)
            )

        return qs.annotate(
            _torre_len=Length("unidad__torre__nombre"), _num_len=Length("unidad__numero"),
        ).order_by("rol", "_torre_len", "unidad__torre__nombre", "_num_len", "unidad__numero", "user__last_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rol_seleccionado"] = self.request.GET.get("rol", "")
        context["busqueda"] = self.request.GET.get("q", "")
        return context


class CrearMiembroView(SoloStaffMixin, CondominioRequiredMixin, FormView):
    template_name = "core/miembro_form.html"
    form_class = CrearMiembroForm
    success_url = reverse_lazy("miembros")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["condominio"] = self.condominio
        return kwargs

    def form_valid(self, form):
        datos = form.cleaned_data
        username = generar_username(datos["nombre"], datos["apellido"])
        password = generar_password_temporal()
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, password=password,
                first_name=datos["nombre"], last_name=datos["apellido"], email=datos.get("email", ""),
            )
            Membresia.objects.create(
                user=user, condominio=self.condominio, rol=datos["rol"],
                unidad=datos.get("unidad"),
            )
        if user.email:
            enviar_correo_bienvenida(user, self.condominio)
        messages.success(
            self.request,
            f"Cuenta creada: usuario «{username}», contraseña temporal «{password}» — entrégasela a la persona, "
            "no queda guardada en ningún otro lado.",
        )
        return super().form_valid(form)


class CondominioUpdateView(SoloStaffMixin, CondominioRequiredMixin, TemplateView):
    """No edita nada acá -- es la página de devquad para el autoregistro de
    residentes (QR/link)."""

    template_name = "core/condominio_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_contexto_invitacion(self.request, self.condominio))
        return context


class TorreListView(SoloStaffMixin, CondominioFormMixin, ListView):
    model = Torre
    template_name = "core/torre_list.html"
    context_object_name = "torres"

    def get_queryset(self):
        return super().get_queryset().annotate(
            _len=Length("nombre"),
            unidades_count=Count("unidades", distinct=True),
            miembros_count=Count("unidades__membresias", distinct=True),
        ).order_by("_len", "nombre")


class TorreCreateView(SoloStaffMixin, CondominioFormMixin, CreateView):
    model = Torre
    form_class = TorreForm
    template_name = "core/torre_form.html"
    success_url = reverse_lazy("torres")


class UnidadListView(SoloStaffMixin, CondominioFormMixin, ListView):
    model = Unidad
    template_name = "core/unidad_list.html"
    context_object_name = "unidades"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related("torre")
        torre_id = self.request.GET.get("torre")
        if torre_id:
            qs = qs.filter(torre_id=torre_id)
        return qs.annotate(
            _torre_len=Length("torre__nombre"), _num_len=Length("numero"),
            miembros_count=Count("membresias", distinct=True),
        ).order_by("_torre_len", "torre__nombre", "_num_len", "numero")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["torres"] = Torre.objects.filter(condominio=self.condominio).annotate(_len=Length("nombre")).order_by("_len", "nombre")
        context["torre_seleccionada"] = self.request.GET.get("torre", "")
        return context


class UnidadCreateView(SoloStaffMixin, CondominioFormMixin, CreateView):
    model = Unidad
    form_class = UnidadForm
    template_name = "core/unidad_form.html"
    success_url = reverse_lazy("unidades")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["condominio"] = self.condominio
        return kwargs


class MiPerfilView(CondominioRequiredMixin, UpdateView):
    """Cualquier miembro edita sus propios datos -- residente, directiva o conserjería."""

    model = User
    form_class = MiPerfilForm
    template_name = "core/mi_perfil.html"
    success_url = reverse_lazy("mi-perfil")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Tus datos quedaron actualizados.")
        return super().form_valid(form)


class MiCambiarContrasenaView(PasswordChangeView):
    template_name = "core/cambiar_contrasena.html"
    form_class = MiCambiarContrasenaForm
    success_url = reverse_lazy("mi-perfil")

    def form_valid(self, form):
        messages.success(self.request, "Tu contraseña fue cambiada correctamente.")
        return super().form_valid(form)


class PasswordResetConfirmView(_PasswordResetConfirmView):
    """Igual que la vista de Django, pero pasa las reglas de contraseña como
    texto plano (ayudas_contrasena) en vez del HTML pre-armado de
    form.new_password1.help_text -- evita usar el filtro |safe en el
    template. El HTML de Django siempre fue seguro en los hechos (sale de
    AUTH_PASSWORD_VALIDATORS, nunca de un usuario), pero SonarCloud no
    puede probar eso de forma estática y lo marca como hallazgo a revisar
    (Web:S5247) -- esto lo saca de raíz en vez de solo silenciarlo."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ayudas_contrasena"] = password_validators_help_texts()
        return context
