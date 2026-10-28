import re
from datetime import datetime, timedelta

from django import forms
from django.utils import timezone

from .models import Business, DepositSettings, Professional, Service, TimeOff, WorkingHours

# Working-hour ranges a professional can have (several per day are allowed).
MAX_WORKING_HOURS = 50
# Longest single time off, so a typo in the year cannot close the agenda for good.
MAX_TIME_OFF_DAYS = 366


def single_line(value):
    """Collapse line breaks, tabs and repeated spaces: these values end up in emails."""
    return " ".join(value.split())


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["name", "address", "show_prices"]
        help_texts = {
            "address": "Calle, número y barrio. La ven tus clientes al reservar.",
            "show_prices": (
                "Tus clientes ven el precio de cada servicio que lo tenga al reservar. "
                "Cargá el precio final, en pesos."
            ),
        }

    def clean_name(self):
        name = single_line(self.cleaned_data["name"])
        if not name:
            raise forms.ValidationError("Este campo es obligatorio.")
        return name

    def clean_address(self):
        return single_line(self.cleaned_data["address"])


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "duration_minutes", "price", "is_active"]
        labels = {"price": "Precio (opcional)"}
        help_texts = {
            "price": (
                "En pesos. Si lo dejás vacío no pasa nada. "
                "Cambiarlo no afecta los turnos ya tomados."
            )
        }

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price is not None and price <= 0:
            raise forms.ValidationError("El precio tiene que ser mayor a cero, o dejalo vacío.")
        return price

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]
        if duration <= 0:
            raise forms.ValidationError("La duración tiene que ser mayor a cero.")
        return duration


class ProfessionalForm(forms.ModelForm):
    class Meta:
        model = Professional
        fields = ["name", "is_active"]


ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9.\-]{6,20}$")


class DepositSettingsForm(forms.ModelForm):
    # Room for spaces and dashes as people paste them; cleaned down to the stored length.
    cbu_cvu = forms.CharField(
        label="CBU o CVU",
        max_length=30,
        required=False,
        help_text="22 números. Cargá el alias, el CBU/CVU o los dos.",
    )
    holder_tax_id = forms.CharField(
        label="CUIT o CUIL", max_length=16, required=False, help_text="Opcional."
    )

    class Meta:
        model = DepositSettings
        fields = [
            "enabled",
            "amount",
            "holder_name",
            "transfer_alias",
            "cbu_cvu",
            "holder_tax_id",
            "instructions",
        ]
        labels = {"enabled": "Pedir seña al reservar", "amount": "Monto de la seña (ARS)"}
        help_texts = {
            "transfer_alias": "Entre 6 y 20 letras, números, puntos o guiones.",
            "instructions": (
                "Opcional, hasta 300 caracteres. Por ejemplo, a dónde mandar el comprobante o cómo "
                "contactarte si hay dudas."
            ),
        }
        widgets = {"instructions": forms.Textarea(attrs={"rows": 3, "maxlength": 300})}

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is not None and amount <= 0:
            raise forms.ValidationError("El monto tiene que ser mayor a cero.")
        return amount

    def clean_holder_name(self):
        return single_line(self.cleaned_data["holder_name"])

    def clean_transfer_alias(self):
        alias = self.cleaned_data["transfer_alias"].strip()
        if alias and not ALIAS_PATTERN.match(alias):
            raise forms.ValidationError(
                "El alias tiene entre 6 y 20 caracteres: letras, números, puntos o guiones."
            )
        return alias

    def clean_cbu_cvu(self):
        number = re.sub(r"[\s-]", "", self.cleaned_data["cbu_cvu"])
        if number and not re.fullmatch(r"\d{22}", number):
            raise forms.ValidationError("El CBU o CVU tiene 22 números.")
        return number

    def clean_holder_tax_id(self):
        digits = re.sub(r"[\s-]", "", self.cleaned_data["holder_tax_id"])
        if not digits:
            return ""
        if not re.fullmatch(r"\d{11}", digits):
            raise forms.ValidationError("El CUIT o CUIL tiene 11 números.")
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"

    def clean_instructions(self):
        return single_line(self.cleaned_data["instructions"])

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("enabled"):
            return cleaned_data
        if not cleaned_data.get("amount") and "amount" not in self.errors:
            self.add_error("amount", "Para pedir seña, cargá el monto.")
        if not cleaned_data.get("holder_name") and "holder_name" not in self.errors:
            self.add_error("holder_name", "Para pedir seña, cargá el titular de la cuenta.")
        has_destination = cleaned_data.get("transfer_alias") or cleaned_data.get("cbu_cvu")
        if not has_destination and not {"transfer_alias", "cbu_cvu"} & set(self.errors):
            raise forms.ValidationError("Para pedir seña, cargá el alias o el CBU/CVU.")
        return cleaned_data


class WorkingHoursForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = ["weekday", "start_time", "end_time"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        if start and end and end <= start:
            raise forms.ValidationError("La hora de fin tiene que ser posterior a la de inicio.")
        return cleaned_data


class BaseWorkingHoursFormSet(forms.BaseInlineFormSet):
    default_error_messages = {
        "too_many_forms": (
            f"Podés cargar hasta {MAX_WORKING_HOURS} horarios por profesional. "
            "Uní tramos o borrá los que no uses."
        ),
    }

    def clean(self):
        # Overlaps first, so an exact copy gets this message and not the generic duplicate one.
        if not any(self.errors):
            self.check_overlaps()
        super().clean()

    def check_overlaps(self):
        """Sorted by day and start, any overlap shows up between neighbours, in any input order.
        Back-to-back ranges (09:00-13:00 and 13:00-17:00) are allowed."""
        ranges = sorted(
            (
                form.cleaned_data["weekday"],
                form.cleaned_data["start_time"],
                form.cleaned_data["end_time"],
            )
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        )
        for previous, current in zip(ranges, ranges[1:], strict=False):
            same_day = previous[0] == current[0]
            if same_day and current[1] < previous[2]:
                day = dict(WorkingHours.WEEKDAYS)[current[0]]
                raise forms.ValidationError(f"Hay horarios superpuestos el {day.lower()}.")


def working_hours_formset(extra):
    return forms.inlineformset_factory(
        Professional,
        WorkingHours,
        form=WorkingHoursForm,
        formset=BaseWorkingHoursFormSet,
        extra=extra,
        can_delete=True,
        max_num=MAX_WORKING_HOURS,
        validate_max=True,
        # Rows sent at all, deleted ones included: a forged form cannot make the server build more.
        absolute_max=MAX_WORKING_HOURS * 2,
    )


class AgendaForm(forms.Form):
    date = forms.DateField(
        label="Día", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    professional = forms.ModelChoiceField(
        label="Profesional", queryset=None, required=False, empty_label="Todos"
    )

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["professional"].queryset = business.professionals.all()


class TimeOffForm(forms.Form):
    """Days, or hours across days, when the business or one professional takes no bookings."""

    professional = forms.ModelChoiceField(
        label="¿Quién no atiende?", queryset=None, required=False, empty_label="Todo el negocio"
    )
    start_date = forms.DateField(
        label="Desde el día", widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        label="Hasta el día",
        required=False,
        help_text="Vacío si es un solo día.",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    start_time = forms.TimeField(
        label="Desde la hora",
        required=False,
        help_text="Sin horario se bloquean los días completos.",
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    end_time = forms.TimeField(
        label="Hasta la hora",
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    reason = forms.CharField(
        label="Motivo",
        max_length=100,
        required=False,
        help_text="Opcional. Lo ves solo vos, tus clientes no.",
    )

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.business = business
        self.fields["professional"].queryset = business.professionals.filter(is_active=True)

    def clean_reason(self):
        return single_line(self.cleaned_data["reason"])

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        if not start_date or {"end_date", "start_time", "end_time"} & set(self.errors):
            return cleaned_data
        end_date = cleaned_data.get("end_date") or start_date
        start_time, end_time = cleaned_data.get("start_time"), cleaned_data.get("end_time")
        if (start_time is None) != (end_time is None):
            raise forms.ValidationError(
                "Cargá las dos horas, o ninguna para bloquear días completos."
            )
        if end_date < start_date:
            raise forms.ValidationError("El día de fin no puede ser anterior al de inicio.")
        if (end_date - start_date).days >= MAX_TIME_OFF_DAYS:
            raise forms.ValidationError(f"Un bloqueo puede durar hasta {MAX_TIME_OFF_DAYS} días.")
        if start_time is None:
            start_at = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end_at = timezone.make_aware(
                datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            )
        else:
            start_at = timezone.make_aware(datetime.combine(start_date, start_time))
            end_at = timezone.make_aware(datetime.combine(end_date, end_time))
            if end_at <= start_at:
                raise forms.ValidationError(
                    "La hora de fin tiene que ser posterior a la de inicio."
                )
        if end_at <= timezone.now():
            raise forms.ValidationError("Ese período ya pasó. Elegí días a futuro.")
        cleaned_data["start_at"], cleaned_data["end_at"] = start_at, end_at
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        return TimeOff.objects.create(
            business=self.business,
            professional=data["professional"],
            start_at=data["start_at"],
            end_at=data["end_at"],
            reason=data["reason"],
        )


class CancelAffectedForm(forms.Form):
    """Confirmed appointments inside a time off that the owner chooses to cancel."""

    appointments = forms.ModelMultipleChoiceField(
        label="Turnos a cancelar",
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Elegí al menos un turno para cancelar."},
    )
    reason = forms.CharField(
        label="Motivo para tus clientes",
        max_length=200,
        required=False,
        help_text="Opcional. Va en el email de cancelación, tal cual lo escribas.",
    )

    def __init__(self, *args, appointments, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["appointments"].queryset = appointments
        self.fields["appointments"].label_from_instance = appointment_label

    def clean_reason(self):
        return single_line(self.cleaned_data["reason"])


def appointment_label(appointment):
    start = timezone.localtime(appointment.start_at)
    return (
        f"{start:%d/%m %H:%M} · {appointment.customer_name} · {appointment.service.name} "
        f"con {appointment.professional.name}"
    )
