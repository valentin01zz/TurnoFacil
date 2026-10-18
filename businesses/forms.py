from django import forms

from .models import Business, Professional, Service, WorkingHours


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
    def clean(self):
        super().clean()
        if any(self.errors):
            return
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
