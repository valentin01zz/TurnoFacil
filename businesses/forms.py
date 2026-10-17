from django import forms

from .models import Service


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "duration_minutes", "is_active"]

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]
        if duration <= 0:
            raise forms.ValidationError("La duración tiene que ser mayor a cero.")
        return duration
