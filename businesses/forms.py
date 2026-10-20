from django import forms

from .models import Business, Professional, Service, WorkingHours

# Working-hour ranges a professional can have (several per day are allowed).
MAX_WORKING_HOURS = 50


def single_line(value):
    """Collapse line breaks, tabs and repeated spaces: these values end up in emails."""
    return " ".join(value.split())


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["name", "address"]
        help_texts = {"address": "Calle, número y barrio. La ven tus clientes al reservar."}

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
        fields = ["name", "duration_minutes", "is_active"]

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]
        if duration <= 0:
            raise forms.ValidationError("La duración tiene que ser mayor a cero.")
        return duration


class ProfessionalForm(forms.ModelForm):
    class Meta:
        model = Professional
        fields = ["name", "is_active"]


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
