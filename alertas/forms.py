from django import forms

from .models import _NOMBRES_NACIONALES, NumeroEmergencia, PropuestaNumeroEmergencia


class NumeroEmergenciaForm(forms.ModelForm):
    class Meta:
        model = NumeroEmergencia
        fields = ["categoria", "nombre", "telefono"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. Chilquinta, Plan Cuadrante 23"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 600 600 5000"}),
        }


class PropuestaNumeroEmergenciaForm(forms.ModelForm):
    class Meta:
        model = PropuestaNumeroEmergencia
        fields = ["categoria", "nombre", "telefono", "nota"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. Chilquinta, Plan Cuadrante 23"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 600 600 5000"}),
            "nota": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional: para qué sirve o por qué lo propones"}),
        }

    def clean_nombre(self):
        """Los nacionales (Carabineros, Bomberos, etc.) son fijos -- no se
        proponen, se agregan solos (ver NumeroEmergenciaListView)."""
        nombre = self.cleaned_data["nombre"]
        if nombre in _NOMBRES_NACIONALES:
            raise forms.ValidationError("Ese ya es un número nacional, no hace falta proponerlo.")
        return nombre
