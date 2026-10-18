"""Appointment management from the business panel (HU-10)."""

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .emails import send_cancelled, send_confirmation, send_rescheduled
from .forms import PanelAppointmentForm, PanelScheduleForm
from .models import Appointment
from .views import create_appointment


def overlap_message(professional):
    return f"Ese horario se superpone con otro turno de {professional.name}."


def manage_url(request, appointment):
    return request.build_absolute_uri(
        reverse("appointment_detail", args=[appointment.manage_token])
    )


def agenda_url(appointment):
    day = timezone.localdate(appointment.start_at)
    return f"{reverse('panel')}?{urlencode({'date': day.isoformat()})}"


def get_owned_appointment(request, pk, for_update=False):
    queryset = Appointment.objects.select_related("business", "service", "professional")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    return get_object_or_404(queryset, pk=pk, business=request.user.business)


@login_required
def appointment_create(request):
    business = request.user.business
    initial = {"date": request.GET.get("date") or timezone.localdate()}
    form = PanelAppointmentForm(request.POST or None, business=business, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        appointment = create_appointment(
            business, data["professional"], data["service"], data, source=Appointment.MANUAL
        )
        if appointment:
            send_confirmation(appointment, manage_url(request, appointment))
            return redirect(agenda_url(appointment))
        form.add_error(None, overlap_message(data["professional"]))
    return render(request, "bookings/panel_appointment_form.html", {"form": form, "is_new": True})


@login_required
def appointment_reschedule(request, pk):
    business = request.user.business
    appointment = get_owned_appointment(request, pk)
    if not appointment.is_confirmed:
        return redirect(agenda_url(appointment))
    local_start = timezone.localtime(appointment.start_at)
    initial = {
        "professional": appointment.professional_id,
        "date": local_start.date(),
        "time": local_start.time(),
    }
    form = PanelScheduleForm(request.POST or None, business=business, initial=initial)
    if request.method == "POST" and form.is_valid():
        professional = form.cleaned_data["professional"]
        try:
            with transaction.atomic():
                appointment = get_owned_appointment(request, pk, for_update=True)
                if not appointment.is_confirmed:
                    return redirect(agenda_url(appointment))
                appointment.move_to(form.cleaned_data["start_at"], professional=professional)
        except IntegrityError:
            appointment.refresh_from_db()
            form.add_error(None, overlap_message(professional))
        else:
            send_rescheduled(appointment, manage_url(request, appointment))
            return redirect(agenda_url(appointment))
    return render(
        request,
        "bookings/panel_appointment_form.html",
        {"form": form, "is_new": False, "appointment": appointment},
    )


@login_required
def appointment_cancel(request, pk):
    appointment = get_owned_appointment(request, pk)
    if request.method != "POST":
        if not appointment.is_confirmed:
            return redirect(agenda_url(appointment))
        return render(request, "bookings/panel_cancel_confirm.html", {"appointment": appointment})

    with transaction.atomic():
        appointment = get_owned_appointment(request, pk, for_update=True)
        was_confirmed = appointment.is_confirmed
        if was_confirmed:
            appointment.cancel()
    if was_confirmed:
        send_cancelled(appointment, manage_url(request, appointment))
    return redirect(agenda_url(appointment))
