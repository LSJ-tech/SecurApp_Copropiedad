from django import forms

from .models import NumeroEmergencia


class NumeroEmergenciaForm(forms.ModelForm):
    class Meta:
        model = NumeroEmergencia
        fields = ["categoria", "nombre", "telefono"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. Chilquinta, Plan Cuadrante 23"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 600 600 5000"}),
        }
