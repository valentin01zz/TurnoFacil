import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from businesses.models import Business

from .availability import available_slots
from .emails import send_confirmation, send_rescheduled
from .forms import BookingForm, RescheduleQueryForm, SlotForm, SlotQueryForm
from .models import Appointment

TAKEN_MESSAGE = "Ese horario se acaba de ocupar. Elegí otro."


def booking_page(request, slug):
    business = get_object_or_404(Business, slug=slug)
    selection = SlotQueryForm(request.GET or None, business=business)
    return render_booking_page(request, business, selection)


@require_POST
def book(request, slug):
    business = get_object_or_404(Business, slug=slug)
    selection = SlotQueryForm(request.POST, business=business)
    if not selection.is_valid():
        return render_booking_page(request, business, selection, status=400)

    service = selection.cleaned_data["service"]
    professional = selection.cleaned_data["professional"]
    slots = available_slots(professional, service, selection.cleaned_data["date"])
    booking = BookingForm(request.POST, slots=slots)
    if booking.is_valid():
        appointment = create_appointment(business, professional, service, booking.cleaned_data)
        if appointment:
            manage_path = reverse("appointment_detail", args=[appointment.manage_token])
            send_confirmation(appointment, request.build_absolute_uri(manage_path))
            return redirect(manage_path)
        booking.add_error("start_at", TAKEN_MESSAGE)
    return render_booking_page(request, business, selection, booking=booking)


def create_appointment(business, professional, service, data):
    """Create a confirmed appointment, or return None if the slot was taken meanwhile."""
    start_at = data["start_at"]
    reminder_due_at = start_at - timedelta(hours=settings.REMINDER_HOURS_BEFORE)
    try:
        with transaction.atomic():
            return Appointment.objects.create(
                business=business,
                professional=professional,
                service=service,
                customer_name=data["customer_name"],
                customer_phone=data["customer_phone"],
                customer_email=data["customer_email"],
                start_at=start_at,
                end_at=start_at + timedelta(minutes=service.duration_minutes),
                source=Appointment.ONLINE,
                manage_token=secrets.token_urlsafe(32),
                reminder_due_at=reminder_due_at if reminder_due_at > timezone.now() else None,
            )
    except IntegrityError:
        return None


def render_booking_page(request, business, selection, booking=None, status=200):
    is_taking_bookings = (
        business.services.filter(is_active=True).exists()
        and business.professionals.filter(is_active=True).exists()
    )
    slots = None
    if is_taking_bookings and selection.is_bound and selection.is_valid():
        slots = available_slots(
            selection.cleaned_data["professional"],
            selection.cleaned_data["service"],
            selection.cleaned_data["date"],
        )
        booking = booking or BookingForm(slots=slots)
    return render(
        request,
        "bookings/booking_page.html",
        {
            "business": business,
            "is_taking_bookings": is_taking_bookings,
            "selection": selection,
            "slots": slots,
            "booking": booking,
        },
        status=status,
    )


def get_appointment(token, for_update=False):
    queryset = Appointment.objects.select_related("business", "service", "professional")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    return queryset.filter(manage_token=token).first()


def render_appointment(request, appointment, template="bookings/appointment_detail.html", **extra):
    if appointment is None:
        return render(request, "bookings/appointment_not_found.html", status=404)
    context = {
        "appointment": appointment,
        "can_change": appointment.customer_can_change(),
        "change_limit_hours": settings.CUSTOMER_CHANGE_LIMIT_HOURS,
        **extra,
    }
    return render(request, template, context)


def appointment_detail(request, token):
    return render_appointment(request, get_appointment(token))


def cancel_appointment(request, token):
    if request.method != "POST":
        appointment = get_appointment(token)
        if appointment and appointment.customer_can_change():
            return render_appointment(request, appointment, "bookings/cancel_confirm.html")
        return render_appointment(request, appointment)

    with transaction.atomic():
        appointment = get_appointment(token, for_update=True)
        if appointment is None:
            return render_appointment(request, None)
        if not appointment.is_confirmed:
            return render_appointment(
                request, appointment, notice="Este turno ya estaba cancelado."
            )
        if not appointment.customer_can_change():
            return render_appointment(request, appointment)
        appointment.cancel()
    return redirect("appointment_detail", token=token)


def reschedule_slots(appointment, professional, date):
    """Free times for the same service with `professional`, other than the current one."""
    slots = available_slots(professional, appointment.service, date, ignore=appointment)
    if professional != appointment.professional:
        return slots
    return [slot for slot in slots if slot != appointment.start_at]


def render_reschedule(request, appointment, query, slot_form=None, status=200):
    return render(
        request,
        "bookings/reschedule.html",
        {
            "appointment": appointment,
            "query": query,
            "slot_form": slot_form,
            "change_limit_hours": settings.CUSTOMER_CHANGE_LIMIT_HOURS,
        },
        status=status,
    )


def reschedule_appointment(request, token):
    if request.method != "POST":
        appointment = get_appointment(token)
        if appointment is None or not appointment.customer_can_change():
            return render_appointment(request, appointment)
        query = RescheduleQueryForm(request.GET or None, appointment=appointment)
        slot_form = None
        if query.is_bound and query.is_valid():
            slots = reschedule_slots(
                appointment, query.cleaned_data["professional"], query.cleaned_data["date"]
            )
            slot_form = SlotForm(slots=slots)
        return render_reschedule(request, appointment, query, slot_form)

    with transaction.atomic():
        appointment = get_appointment(token, for_update=True)
        if appointment is None or not appointment.customer_can_change():
            return render_appointment(request, appointment)
        query = RescheduleQueryForm(request.POST, appointment=appointment)
        if not query.is_valid():
            return render_reschedule(request, appointment, query, status=400)

        professional = query.cleaned_data["professional"]
        slots = reschedule_slots(appointment, professional, query.cleaned_data["date"])
        slot_form = SlotForm(request.POST, slots=slots)
        if not slot_form.is_valid():
            return render_reschedule(request, appointment, query, slot_form)
        try:
            with transaction.atomic():
                appointment.move_to(slot_form.cleaned_data["start_at"], professional=professional)
        except IntegrityError:
            appointment.refresh_from_db()
            slot_form.add_error("start_at", TAKEN_MESSAGE)
            return render_reschedule(request, appointment, query, slot_form)

    manage_path = reverse("appointment_detail", args=[token])
    send_rescheduled(appointment, request.build_absolute_uri(manage_path))
    return redirect(manage_path)
