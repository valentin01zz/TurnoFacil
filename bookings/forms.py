import re
from datetime import datetime

from django import forms
from django.utils import timezone

from .availability import booking_window


def clean_phone(value):
    phone = value.strip()
    if not re.fullmatch(r"[0-9 +()\-]+", phone) or len(re.sub(r"\D", "", phone)) < 6:
        raise forms.ValidationError("Ingresá un teléfono válido.")
    return phone


class BookingDateForm(forms.Form):
    """A day inside the booking window."""

    date = forms.DateField(label="Día", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        first_day, last_day = booking_window()
        self.fields["date"].widget.attrs.update(min=first_day.isoformat(), max=last_day.isoformat())

    def clean_date(self):
        date = self.cleaned_data["date"]
        first_day, last_day = booking_window()
        if not first_day <= date <= last_day:
            raise forms.ValidationError(f"Elegí un día entre hoy y el {last_day:%d/%m/%Y}.")
        return date


class SlotQueryForm(BookingDateForm):
    """Service, professional and day the customer wants to see free times for."""

    service = forms.ModelChoiceField(
        label="Servicio", queryset=None, empty_label="Elegí un servicio"
    )
    professional = forms.ModelChoiceField(
        label="Profesional", queryset=None, empty_label="Elegí un profesional"
    )
    field_order = ["service", "professional", "date"]

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = business.services.filter(is_active=True)
        professionals = business.professionals.filter(is_active=True)
        self.fields["professional"].queryset = professionals
        self.single_professional = professionals.first() if len(professionals) == 1 else None
        if self.single_professional:
            self.fields["professional"].required = False
            self.fields["professional"].widget = forms.HiddenInput()

    def clean_professional(self):
        return self.cleaned_data.get("professional") or self.single_professional


class RescheduleQueryForm(BookingDateForm):
    """New day and, if the business has several, professional for an existing appointment."""

    professional = forms.ModelChoiceField(label="Profesional", queryset=None, empty_label=None)
    field_order = ["professional", "date"]

    def __init__(self, *args, appointment, **kwargs):
        kwargs.setdefault("initial", {"professional": appointment.professional_id})
        super().__init__(*args, **kwargs)
        professionals = appointment.business.professionals.filter(is_active=True)
        self.fields["professional"].queryset = professionals
        self.fallback_professional = appointment.professional
        if len(professionals) <= 1:
            self.fields["professional"].required = False
            self.fields["professional"].widget = forms.HiddenInput()

    def clean_professional(self):
        return self.cleaned_data.get("professional") or self.fallback_professional


class SlotForm(forms.Form):
    start_at = forms.ChoiceField(
        label="Horario",
        widget=forms.RadioSelect,
        error_messages={"invalid_choice": "Ese horario ya no está disponible. Elegí otro."},
    )

    def __init__(self, *args, slots, **kwargs):
        super().__init__(*args, **kwargs)
        self.slots = {slot.isoformat(): slot for slot in slots}
        self.fields["start_at"].choices = [
            (value, f"{timezone.localtime(slot):%H:%M}") for value, slot in self.slots.items()
        ]

    def clean_start_at(self):
        return self.slots[self.cleaned_data["start_at"]]


class BookingForm(SlotForm):
    customer_name = forms.CharField(label="Nombre y apellido", max_length=100)
    customer_phone = forms.CharField(label="Teléfono", max_length=30)
    customer_email = forms.EmailField(label="Email")
    # Honeypot: hidden from people, often filled in by bots.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_customer_phone(self):
        return clean_phone(self.cleaned_data["customer_phone"])

    def clean_website(self):
        if self.cleaned_data["website"]:
            raise forms.ValidationError("No pudimos procesar la reserva.")
        return ""


class PanelScheduleForm(forms.Form):
    """Professional, day and time chosen by the business owner (any time, not only free slots)."""

    professional = forms.ModelChoiceField(label="Profesional", queryset=None, empty_label=None)
    date = forms.DateField(label="Día", widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(
        label="Hora", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["professional"].queryset = business.professionals.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        date, time = cleaned_data.get("date"), cleaned_data.get("time")
        if date and time:
            start_at = timezone.make_aware(datetime.combine(date, time))
            if start_at <= timezone.now():
                raise forms.ValidationError("Elegí un día y hora a futuro.")
            cleaned_data["start_at"] = start_at
        return cleaned_data


class PanelAppointmentForm(PanelScheduleForm):
    service = forms.ModelChoiceField(label="Servicio", queryset=None, empty_label=None)
    customer_name = forms.CharField(label="Nombre y apellido", max_length=100)
    customer_phone = forms.CharField(label="Teléfono", max_length=30)
    customer_email = forms.EmailField(
        label="Email (opcional)",
        required=False,
        help_text="Si lo cargás, el cliente recibe la confirmación y el recordatorio.",
    )
    field_order = [
        "customer_name",
        "customer_phone",
        "customer_email",
        "service",
        "professional",
        "date",
        "time",
    ]

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, business=business, **kwargs)
        self.fields["service"].queryset = business.services.filter(is_active=True)

    def clean_customer_phone(self):
        return clean_phone(self.cleaned_data["customer_phone"])
