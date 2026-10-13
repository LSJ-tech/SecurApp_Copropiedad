from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models.functions import Length

from .comunas_chile import COMUNAS_POR_REGION, comuna_choices_agrupadas
from .models import REGION_CHOICES, ROL_CHOICES, CodigoInvitacion, Condominio, SolicitudAcceso, Torre, Unidad

LABEL_TU_NOMBRE = "Tu nombre"
LABEL_EMAIL = "Email"
LABEL_EMAIL_OPCIONAL = "Email (opcional)"


def _normalizar_nombre(texto):
    """Primera letra de cada palabra en mayúscula, el resto en minúscula --
    para que no quede "juan perez"/"JUAN PEREZ" en la base según cómo lo haya
    tipeado cada quien. str.title() también separa bien en apóstrofes
    (ej. "o'higgins" -> "O'Higgins"), que es lo único no trivial acá."""
    return " ".join(texto.split()).title()


def _validar_email_unico(email, excluir_user_id=None):
    """Un mismo email no puede quedar en dos cuentas -- se usa para mandar el
    correo de bienvenida, comprobantes de pago y (a futuro) recuperar la
    contraseña, así que tiene que apuntar a una sola persona."""
    qs = User.objects.filter(email__iexact=email)
    if excluir_user_id:
        qs = qs.exclude(pk=excluir_user_id)
    if qs.exists():
        raise ValidationError("Ya existe una cuenta registrada con este email.")
    return email


class NormalizarNombreApellidoMixin:
    """Mezclar en cualquier form con campos "nombre"/"apellido" de texto
    libre -- normaliza los dos igual (ver _normalizar_nombre). MiPerfilForm
    no lo usa porque sus campos se llaman first_name/last_name (ModelForm
    sobre User)."""

    def clean_nombre(self):
        return _normalizar_nombre(self.cleaned_data["nombre"])

    def clean_apellido(self):
        return _normalizar_nombre(self.cleaned_data["apellido"])


class ConfirmacionContrasenaMixin(forms.Form):
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput(attrs={"class": "form-control"}))

    def clean_password1(self):
        password = self.cleaned_data["password1"]
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") and cleaned.get("password2") and cleaned["password1"] != cleaned["password2"]:
            raise ValidationError("Las contraseñas no coinciden.")
        return cleaned


class RegistroCondominioForm(NormalizarNombreApellidoMixin, ConfirmacionContrasenaMixin):
    """Alta de un condominio nuevo y de su primer usuario (directiva), sin intervención manual."""

    field_order = [
        "codigo_invitacion", "nombre_condominio", "direccion_condominio", "region_condominio", "comuna_condominio",
        "nombre", "apellido", "password1", "password2", "acepto_terminos",
    ]

    codigo_invitacion = forms.CharField(
        max_length=20, label="Código de invitación",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Pídeselo a quien te invitó a usar la plataforma.",
    )
    nombre_condominio = forms.CharField(
        max_length=150, label="Nombre del condominio o junta de vecinos",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    direccion_condominio = forms.CharField(
        max_length=255, required=False, label="Dirección o sector",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="No tiene que ser una dirección exacta -- puede ser \"Sector Los Aromos\" o similar.",
    )
    comuna_condominio = forms.ChoiceField(
        choices=[("", "---------")] + comuna_choices_agrupadas(REGION_CHOICES), required=False, label="Comuna",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    region_condominio = forms.ChoiceField(
        choices=[("", "---------")] + REGION_CHOICES, required=False, label="Región",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nombre = forms.CharField(
        max_length=150, label=LABEL_TU_NOMBRE,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    apellido = forms.CharField(
        max_length=150, label="Tu apellido",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    acepto_terminos = forms.BooleanField(
        required=True, label="Acepto los Términos de Uso y la Política de Privacidad",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        error_messages={"required": "Tienes que aceptar los Términos de Uso y la Política de Privacidad para continuar."},
    )

    def clean_codigo_invitacion(self):
        codigo = self.cleaned_data["codigo_invitacion"].strip().upper()
        try:
            self.codigo_obj = CodigoInvitacion.objects.get(codigo=codigo, condominio__isnull=True)
        except CodigoInvitacion.DoesNotExist:
            raise ValidationError("Código inválido o ya usado.")
        return codigo

    def clean(self):
        cleaned = super().clean()
        region = cleaned.get("region_condominio")
        comuna = cleaned.get("comuna_condominio")
        # El filtrado real pasa por JS (ver cascada_region_comuna.js) -- esto
        # solo cubre a quien tiene JS desactivado y deja una combinación que
        # no corresponde (ej. elige la región después de la comuna).
        if region and comuna and comuna not in COMUNAS_POR_REGION.get(region, []):
            raise ValidationError("Esa comuna no pertenece a la región elegida.")
        return cleaned


class CrearMiembroForm(NormalizarNombreApellidoMixin, forms.Form):
    """Directiva/administración crea la cuenta de otro miembro del condominio.

    Solo directiva puede nombrar directiva/administración (cuentas de
    gobierno/gestión) -- administración solo puede crear conserjería o
    residentes (cuentas operativas), nunca a su propio nivel o superior.
    """

    nombre = forms.CharField(max_length=150, label="Nombre", widget=forms.TextInput(attrs={"class": "form-control"}))
    apellido = forms.CharField(max_length=150, label="Apellido", widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(label=LABEL_EMAIL, widget=forms.EmailInput(attrs={"class": "form-control"}))
    rol = forms.ChoiceField(choices=[c for c in ROL_CHOICES if c[0] != "directiva"], widget=forms.Select(attrs={"class": "form-select"}))
    unidad = forms.ModelChoiceField(queryset=Unidad.objects.none(), required=False, label="Unidad (obligatorio para residentes)", widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, condominio=None, creador_rol=None, **kwargs):
        super().__init__(*args, **kwargs)
        if creador_rol == "directiva":
            self.fields["rol"].choices = ROL_CHOICES
        else:
            self.fields["rol"].choices = [c for c in ROL_CHOICES if c[0] in ("conserje", "residente")]
        if condominio is not None:
            self.fields["unidad"].label = f"{condominio.etiqueta_unidad} (obligatorio para residentes)"
            self.fields["unidad"].queryset = (
                Unidad.objects.filter(condominio=condominio)
                .select_related("torre")
                .annotate(_torre_len=Length("torre__nombre"), _num_len=Length("numero"))
                .order_by("_torre_len", "torre__nombre", "_num_len", "numero")
            )

    def clean_email(self):
        return _validar_email_unico(self.cleaned_data["email"])

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("rol") == "residente" and not cleaned.get("unidad"):
            raise ValidationError("Selecciona la unidad del residente.")
        return cleaned


class RegistroResidenteForm(NormalizarNombreApellidoMixin, ConfirmacionContrasenaMixin):
    """Autoregistro público de un residente -- elige su propio depto de una lista, vía el link/QR del condominio."""

    field_order = [
        "nombre", "apellido", "email", "unidad", "calle_unidad_libre", "numero_unidad_libre",
        "password1", "password2", "acepto_terminos",
    ]

    nombre = forms.CharField(max_length=150, label=LABEL_TU_NOMBRE, widget=forms.TextInput(attrs={"class": "form-control"}))
    apellido = forms.CharField(max_length=150, label="Tu apellido", widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(
        label=LABEL_EMAIL,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        help_text="Te mandamos un correo de bienvenida.",
    )
    unidad = forms.ModelChoiceField(queryset=Unidad.objects.none(), required=False, label="Tu departamento", widget=forms.Select(attrs={"class": "form-select"}))
    calle_unidad_libre = forms.CharField(
        max_length=150, required=False, label="Nombre de tu calle (opcional)",
        help_text="Solo hace falta si la junta de vecinos tiene más de una calle.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    numero_unidad_libre = forms.CharField(
        max_length=100, required=False, label="Número de tu casa",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    acepto_terminos = forms.BooleanField(
        required=True, label="Acepto los Términos de Uso y la Política de Privacidad",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        error_messages={"required": "Tienes que aceptar los Términos de Uso y la Política de Privacidad para continuar."},
    )

    def __init__(self, *args, condominio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.condominio = condominio
        # La señal de "este condominio es de casas, no de block/depto" es que
        # nunca tuvo torres cargadas -- a propósito no se mira si ya hay
        # Unidad creadas, porque esas se van creando solas a medida que la
        # gente se registra (ver clean()), y el modo tiene que seguir
        # dejando escribir un número nuevo para el segundo/tercer vecino
        # también, no solo para el primero que inaugura la lista.
        self.modo_casas = condominio is not None and not Torre.objects.filter(condominio=condominio).exists()
        if condominio is None:
            return
        etiqueta = condominio.etiqueta_unidad.lower()
        if self.modo_casas:
            # Ninguno de los dos campos es obligatorio por separado -- clean()
            # exige al menos uno. Así el primer vecino puede escribir su
            # número (todavía no hay nada que elegir) y el segundo puede
            # sumarse a una casa ya registrada eligiéndola, o escribir una
            # nueva si la suya no está en la lista.
            self.fields["unidad"].label = f"Tu {etiqueta} (si ya está en la lista)"
            self.fields["unidad"].queryset = (
                Unidad.objects.filter(condominio=condominio).annotate(_num_len=Length("numero")).order_by("_num_len", "numero")
            )
            self.fields["numero_unidad_libre"].label = f"O escribe el número de tu {etiqueta} si no está en la lista"
            self.fields["numero_unidad_libre"].widget.attrs["list"] = "numeros-unidad-existentes"
            self.fields["calle_unidad_libre"].widget.attrs["list"] = "calles-existentes"
        else:
            del self.fields["numero_unidad_libre"]
            del self.fields["calle_unidad_libre"]
            self.fields["unidad"].required = True
            self.fields["unidad"].label = f"Tu {etiqueta}"
            self.fields["unidad"].queryset = (
                Unidad.objects.filter(condominio=condominio)
                .select_related("torre")
                .annotate(_torre_len=Length("torre__nombre"), _num_len=Length("numero"))
                .order_by("_torre_len", "torre__nombre", "_num_len", "numero")
            )

    def clean(self):
        cleaned = super().clean()
        if self.modo_casas and not cleaned.get("unidad"):
            numero = (cleaned.get("numero_unidad_libre") or "").strip()
            calle = _normalizar_nombre((cleaned.get("calle_unidad_libre") or "").strip())
            if numero:
                unidad, _creada = Unidad.objects.get_or_create(condominio=self.condominio, torre=None, numero=numero, calle=calle)
                cleaned["unidad"] = unidad
            else:
                etiqueta = self.condominio.etiqueta_unidad.lower()
                raise ValidationError(f"Elige tu {etiqueta} de la lista, o escribe el número si todavía no aparece.")
        return cleaned

    def clean_email(self):
        return _validar_email_unico(self.cleaned_data["email"])


class CondominioForm(forms.ModelForm):
    class Meta:
        model = Condominio
        fields = ["datos_transferencia"]
        widgets = {
            "datos_transferencia": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }
        labels = {
            "datos_transferencia": "Datos para transferencia de gastos comunes",
        }
        help_texts = {
            "datos_transferencia": "Banco, tipo de cuenta, número, RUT y email — se muestra a los residentes al pagar.",
        }


class SolicitudAccesoForm(forms.ModelForm):
    """Formulario público de la landing -- captura el interés de quien todavía no tiene código de invitación."""

    class Meta:
        model = SolicitudAcceso
        fields = ["nombre", "condominio", "comuna", "telefono", "email", "mensaje"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": LABEL_TU_NOMBRE}),
            "condominio": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del condominio o junta de vecinos"}),
            "comuna": forms.TextInput(attrs={"class": "form-control", "placeholder": "Comuna"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "+56 9 ..."}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": LABEL_EMAIL_OPCIONAL}),
            "mensaje": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Cuéntanos un poco de tu comunidad (opcional)"}),
        }
        labels = {
            "nombre": "Nombre", "condominio": "Condominio o junta de vecinos", "comuna": "Comuna",
            "telefono": "Teléfono", "email": "Email", "mensaje": "Mensaje",
        }


class TorreForm(forms.ModelForm):
    class Meta:
        model = Torre
        fields = ["nombre"]
        widgets = {"nombre": forms.TextInput(attrs={"class": "form-control"})}


class UnidadForm(forms.ModelForm):
    class Meta:
        model = Unidad
        fields = ["numero", "calle", "torre", "alicuota"]
        widgets = {
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "calle": forms.TextInput(attrs={"class": "form-control"}),
            "torre": forms.Select(attrs={"class": "form-select"}),
            "alicuota": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
        }

    def __init__(self, *args, condominio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if condominio is not None:
            self.fields["torre"].label = condominio.etiqueta_torre
            self.fields["torre"].queryset = Torre.objects.filter(condominio=condominio).annotate(_len=Length("nombre")).order_by("_len", "nombre")


class MiPerfilForm(forms.ModelForm):
    """Cualquier miembro (residente, directiva, conserjería) edita sus propios datos."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }
        labels = {"first_name": "Nombre", "last_name": "Apellido", "email": "Email"}

    def clean_first_name(self):
        return _normalizar_nombre(self.cleaned_data["first_name"])

    def clean_last_name(self):
        return _normalizar_nombre(self.cleaned_data["last_name"])

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not email:
            return email
        return _validar_email_unico(email, excluir_user_id=self.instance.pk)


class MiCambiarContrasenaForm(PasswordChangeForm):
    """Mismo PasswordChangeForm de Django, solo con clases de Bootstrap."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
