from django import forms
from django.urls import reverse
from django.utils.html import format_html


def privacy_consent_field():
    """Unticked box for the privacy policy; the form adds it only once the policy is published."""
    return forms.BooleanField(
        label=format_html(
            'Leí y acepto la <a href="{}" target="_blank" rel="noopener">'
            "Política de Privacidad</a>",
            reverse("privacy"),
        ),
        error_messages={"required": "Para seguir tenés que aceptar la Política de Privacidad."},
    )


class ServiceRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email de tu cuenta",
        help_text="El que usás para ingresar a TurnoFacil. No hace falta iniciar sesión.",
    )

    def __init__(self, *args, deletion=False, **kwargs):
        super().__init__(*args, **kwargs)
        if deletion:
            self.fields["email"].label = "Tu email"
            self.fields["email"].help_text = (
                "El de tu cuenta de TurnoFacil o el que usaste para reservar un turno. "
                "No hace falta iniciar sesión."
            )

    # Honeypot: hidden from people, often filled in by bots.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if self.cleaned_data["website"]:
            raise forms.ValidationError("No pudimos procesar la solicitud.")
        return ""


class AcceptTermsForm(forms.Form):
    accept_terms = forms.BooleanField(
        label="Acepto los Términos y Condiciones",
        error_messages={"required": "Para seguir tenés que aceptar los Términos y Condiciones."},
    )
