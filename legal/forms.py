from django import forms


class ServiceRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email de tu cuenta",
        help_text="El que usás para ingresar a TurnoFacil. No hace falta iniciar sesión.",
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
