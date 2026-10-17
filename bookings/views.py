import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from businesses.models import Business

from .availability import available_slots
from .forms import BookingForm, SlotQueryForm
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
            return redirect("appointment_detail", token=appointment.manage_token)
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


def appointment_detail(request, token):
    appointment = get_object_or_404(
        Appointment.objects.select_related("business", "service", "professional"),
        manage_token=token,
    )
    return render(request, "bookings/appointment_detail.html", {"appointment": appointment})
