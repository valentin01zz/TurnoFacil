import re

from django import forms
from django.utils import timezone

from .availability import booking_window


class SlotQueryForm(forms.Form):
    """Service, professional and day the customer wants to see free times for."""

    service = forms.ModelChoiceField(
        label="Servicio", queryset=None, empty_label="Elegí un servicio"
    )
    professional = forms.ModelChoiceField(
        label="Profesional", queryset=None, empty_label="Elegí un profesional"
    )
    date = forms.DateField(label="Día", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = business.services.filter(is_active=True)
        professionals = business.professionals.filter(is_active=True)
        self.fields["professional"].queryset = professionals
        self.single_professional = professionals.first() if len(professionals) == 1 else None
        if self.single_professional:
            self.fields["professional"].required = False
            self.fields["professional"].widget = forms.HiddenInput()
        first_day, last_day = booking_window()
        self.fields["date"].widget.attrs.update(min=first_day.isoformat(), max=last_day.isoformat())

    def clean_professional(self):
        return self.cleaned_data.get("professional") or self.single_professional

    def clean_date(self):
        date = self.cleaned_data["date"]
        first_day, last_day = booking_window()
        if not first_day <= date <= last_day:
            raise forms.ValidationError(f"Elegí un día entre hoy y el {last_day:%d/%m/%Y}.")
        return date


class BookingForm(forms.Form):
    start_at = forms.ChoiceField(
        label="Horario",
        widget=forms.RadioSelect,
        error_messages={"invalid_choice": "Ese horario ya no está disponible. Elegí otro."},
    )
    customer_name = forms.CharField(label="Nombre y apellido", max_length=100)
    customer_phone = forms.CharField(label="Teléfono", max_length=30)
    customer_email = forms.EmailField(label="Email")
    # Honeypot: hidden from people, often filled in by bots.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, slots, **kwargs):
        super().__init__(*args, **kwargs)
        self.slots = {slot.isoformat(): slot for slot in slots}
        self.fields["start_at"].choices = [
            (value, f"{timezone.localtime(slot):%H:%M}") for value, slot in self.slots.items()
        ]

    def clean_start_at(self):
        return self.slots[self.cleaned_data["start_at"]]

    def clean_customer_phone(self):
        phone = self.cleaned_data["customer_phone"].strip()
        if not re.fullmatch(r"[0-9 +()\-]+", phone) or len(re.sub(r"\D", "", phone)) < 6:
            raise forms.ValidationError("Ingresá un teléfono válido.")
        return phone

    def clean_website(self):
        if self.cleaned_data["website"]:
            raise forms.ValidationError("No pudimos procesar la reserva.")
        return ""
