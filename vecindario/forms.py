from django import forms
from django.core.exceptions import ValidationError

from core.forms import LABEL_EMAIL_OPCIONAL, LABEL_TU_NOMBRE, ConfirmacionContrasenaMixin, NormalizarNombreApellidoMixin, _validar_email_unico

from .models import COMUNAS_PILOTO
from .services import geocodificar_direccion, geocodificar_inverso, region_de_comuna


class RegistroVecinoForm(NormalizarNombreApellidoMixin, ConfirmacionContrasenaMixin):
    """Autoregistro público a la red vecinal geográfica -- sin condominio,
    sin código de invitación. Siempre se prefiere la ubicación GPS del
    navegador (campos lat/lng ocultos, llenados por JS); si no hay permiso
    de ubicación, se geocodifica la dirección escrita."""

    nombre = forms.CharField(max_length=150, label=LABEL_TU_NOMBRE, widget=forms.TextInput(attrs={"class": "form-control"}))
    apellido = forms.CharField(max_length=150, label="Tu apellido", widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(required=False, label=LABEL_EMAIL_OPCIONAL, widget=forms.EmailInput(attrs={"class": "form-control"}))
    telefono = forms.CharField(max_length=20, label="Tu teléfono", widget=forms.TextInput(attrs={"class": "form-control"}))
    direccion_texto = forms.CharField(
        max_length=255, required=False, label="Tu dirección",
        help_text="O usa el botón de ubicación de arriba -- no hace falta escribir la dirección si ya la usaste.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    lat = forms.DecimalField(required=False, widget=forms.HiddenInput())
    lng = forms.DecimalField(required=False, widget=forms.HiddenInput())
    acepto_terminos = forms.BooleanField(
        required=True, label="Acepto los Términos de Uso y la Política de Privacidad",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        error_messages={"required": "Tienes que aceptar los Términos de Uso y la Política de Privacidad para continuar."},
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        return _validar_email_unico(email) if email else email

    def clean(self):
        cleaned = super().clean()
        lat, lng = cleaned.get("lat"), cleaned.get("lng")
        direccion_texto = (cleaned.get("direccion_texto") or "").strip()

        if lat is not None and lng is not None:
            resultado = geocodificar_inverso(lat, lng)
            if not resultado:
                raise ValidationError("No pudimos reconocer tu ubicación. Escribe tu dirección más abajo e inténtalo de nuevo.")
            cleaned["lat"], cleaned["lng"] = lat, lng
            cleaned["comuna"] = resultado["comuna"]
            cleaned["direccion_texto"] = direccion_texto or resultado["comuna"]
        elif direccion_texto:
            resultado = geocodificar_direccion(direccion_texto)
            if not resultado:
                raise ValidationError("No pudimos encontrar esa dirección -- revisa que esté bien escrita, o usa el botón de ubicación.")
            cleaned["lat"], cleaned["lng"] = resultado["lat"], resultado["lng"]
            cleaned["comuna"] = resultado["comuna"]
            cleaned["direccion_texto"] = direccion_texto
        else:
            raise ValidationError("Escribe tu dirección, o usa el botón de ubicación para que la detectemos solos.")

        comunas_piloto_normalizadas = {c.strip().lower() for c in COMUNAS_PILOTO}
        if cleaned["comuna"].strip().lower() not in comunas_piloto_normalizadas:
            raise ValidationError(
                f"Por ahora SecurApp solo cubre {', '.join(COMUNAS_PILOTO)} -- todavía no llegamos a "
                f"{cleaned['comuna']}. Escríbenos a contacto@devquad.cl y te avisamos cuando lleguemos."
            )

        region = region_de_comuna(cleaned["comuna"])
        if not region:
            raise ValidationError("No pudimos confirmar la región de esa comuna. Intenta con el botón de ubicación.")
        cleaned["region"] = region
        return cleaned
