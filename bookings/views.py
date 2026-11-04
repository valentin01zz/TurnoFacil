import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.throttle import client_ip, is_limited, record
from billing.access import get_access
from billing.catalog import BOOKING_ONLINE
from businesses.deposit import public_deposit
from businesses.models import Business
from businesses.pricing import deposit_breakdown, public_price

from .availability import available_slots
from .booking_calendar import long_date, month_strip, parse_month, slot_groups
from .emails import (
    notify_owner_booked,
    notify_owner_cancelled,
    notify_owner_rescheduled,
    send_confirmation,
    send_rescheduled,
)
from .forms import BookingForm, RescheduleQueryForm, SlotForm, SlotQueryForm
from .models import Appointment

TAKEN_MESSAGE = "Ese horario se acaba de ocupar. Elegí otro."
TOO_MANY_BOOKINGS_MESSAGE = (
    "Se hicieron muchas reservas desde tu conexión en la última hora. "
    "Probá más tarde o comunicate con el negocio."
)
SERVICE_ICONS = ["leaf", "sparkle", "hands", "drop", "scissors", "heart"]
PROFESSIONAL_TINTS = ["#FFB59E", "#B9A8FF", "#8EE3D8", "#FFD98A", "#FF9EC4", "#A8D8FF"]
CONFETTI_COLORS = ["#2EC4B6", "#6E4BFF", "#FFC53D", "#FF8FB1", "#1C1530", "#8EE3D8"]


def booking_page(request, slug):
    business = get_object_or_404(Business, slug=slug)
    selection = SlotQueryForm(request.GET or None, business=business)
    return render_booking_page(request, business, selection)


@require_POST
def book(request, slug):
    business = get_object_or_404(Business, slug=slug)
    selection = SlotQueryForm(request.POST, business=business)
    if not accepts_bookings(business):
        return render_booking_page(request, business, selection, status=403)
    if not selection.is_valid():
        return render_booking_page(request, business, selection, status=400)

    service = selection.cleaned_data["service"]
    professional = selection.cleaned_data["professional"]
    slots = available_slots(professional, service, selection.cleaned_data["date"])
    booking = BookingForm(request.POST, slots=slots)
    ip = client_ip(request)
    if is_limited("booking_ip", ip):
        booking.is_valid()
        booking.add_error(None, TOO_MANY_BOOKINGS_MESSAGE)
        return render_booking_page(request, business, selection, booking=booking, status=429)
    if booking.is_valid():
        appointment = create_appointment(business, professional, service, booking.cleaned_data)
        if appointment:
            record("booking_ip", ip)
            manage_path = reverse("appointment_detail", args=[appointment.manage_token])
            send_confirmation(appointment, request.build_absolute_uri(manage_path))
            notify_owner_booked(appointment)
            return redirect(f"{manage_path}?nuevo=1")
        booking.add_error("start_at", TAKEN_MESSAGE)
    return render_booking_page(request, business, selection, booking=booking)


class CrossBusinessError(ValueError):
    """The professional or service belongs to another business. Forms never allow it."""


def create_appointment(business, professional, service, data, source=Appointment.ONLINE):
    """Create a confirmed appointment, or return None if the slot was taken meanwhile."""
    if professional.business_id != business.pk or service.business_id != business.pk:
        raise CrossBusinessError(
            f"Professional {professional.pk} or service {service.pk} "
            f"is not from business {business.pk}"
        )
    start_at = data["start_at"]
    email = data.get("customer_email", "")
    reminder_due_at = start_at - timedelta(hours=settings.REMINDER_HOURS_BEFORE)
    try:
        with transaction.atomic():
            return Appointment.objects.create(
                business=business,
                professional=professional,
                service=service,
                customer_name=data["customer_name"],
                customer_phone=data["customer_phone"],
                customer_email=email,
                start_at=start_at,
                end_at=start_at + timedelta(minutes=service.duration_minutes),
                price=service.price,
                source=source,
                manage_token=secrets.token_urlsafe(32),
                reminder_due_at=(
                    reminder_due_at if email and reminder_due_at > timezone.now() else None
                ),
            )
    except IntegrityError:
        return None


def accepts_bookings(business):
    return get_access(business).can(BOOKING_ONLINE)


def selected_values(form):
    """Valid choices from a selection form even when other fields are still missing."""
    if not form.is_bound:
        return {}
    form.is_valid()
    return form.cleaned_data


def month_links(base_url, strip, params):
    def link(month):
        return f"{base_url}?{urlencode({**params, 'month': month.strftime('%Y-%m')})}"

    return {
        "previous_url": link(strip["previous"]) if strip["previous"] else None,
        "next_url": link(strip["next"]) if strip["next"] else None,
    }


def render_booking_page(request, business, selection, booking=None, status=200):
    services = list(business.services.filter(is_active=True))
    professionals = list(business.professionals.filter(is_active=True))
    is_taking_bookings = bool(services and professionals) and accepts_bookings(business)

    chosen = selected_values(selection)
    service = chosen.get("service")
    professional = chosen.get("professional") or selection.single_professional
    date = chosen.get("date")
    date_given = bool(selection.data.get("date")) if selection.is_bound else False

    strip = None
    if is_taking_bookings and service and professional:
        month = parse_month(request.GET.get("month")) or (date.replace(day=1) if date else None)
        strip = month_strip(month, [professional], selected=date)
        strip.update(
            month_links(
                reverse("booking_page", args=[business.slug]),
                strip,
                {"service": service.pk, "professional": professional.pk},
            )
        )

    slots = None
    if strip is not None and date:
        slots = available_slots(professional, service, date)
        booking = booking or BookingForm(slots=slots)
    checked = booking.data.get("start_at", "") if booking is not None and booking.is_bound else ""
    groups = slot_groups(slots or [], checked)
    checked_label = next(
        (slot["label"] for group in groups for slot in group["slots"] if slot["checked"]), ""
    )
    ticket_done = sum(bool(x) for x in (service, professional, date))
    shown_done = ticket_done + (1 if checked_label else 0)
    deposit = public_deposit(business) if is_taking_bookings else None

    return render(
        request,
        "bookings/booking_page.html",
        {
            "business": business,
            "is_taking_bookings": is_taking_bookings,
            "deposit": deposit,
            "price": public_price(service) if service else None,
            "breakdown": deposit_breakdown(deposit, service) if service else None,
            "selection": selection,
            "services": [
                {
                    "pk": s.pk,
                    "name": s.name,
                    "minutes": s.duration_minutes,
                    "price": public_price(s),
                    "icon": SERVICE_ICONS[i % len(SERVICE_ICONS)],
                    "checked": service is not None and s.pk == service.pk,
                }
                for i, s in enumerate(services)
            ],
            "professionals": [
                {
                    "pk": p.pk,
                    "name": p.name,
                    "initial": p.name[:1].upper(),
                    "tint": PROFESSIONAL_TINTS[i % len(PROFESSIONAL_TINTS)],
                    "checked": professional is not None and p.pk == professional.pk,
                }
                for i, p in enumerate(professionals)
            ],
            "choose_professional": len(professionals) > 1,
            "service": service,
            "professional": professional,
            "date": date,
            "date_label": long_date(date) if date else "",
            "date_error": selection.errors.get("date") if date_given else None,
            "strip": strip,
            "slots": slots,
            "slot_groups": groups,
            "checked_label": checked_label,
            "booking": booking,
            "ticket_done": ticket_done,
            "ticket_progress": shown_done * 20,
            "ticket_step": min(shown_done + 1, 5),
        },
        status=status,
    )


def get_appointment(token, for_update=False):
    queryset = Appointment.objects.select_related("business", "service", "professional")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    return queryset.filter(manage_token=token).first()


def confetti():
    pieces = []
    for i in range(18):
        angle = i * 20
        distance = 130 + (i % 4) * 30
        pieces.append(
            {
                "color": CONFETTI_COLORS[i % len(CONFETTI_COLORS)],
                "angle": angle,
                "distance": distance,
                "delay": (i % 5) * 30,
            }
        )
    return pieces


def render_appointment(request, appointment, template="bookings/appointment_detail.html", **extra):
    if appointment is None:
        return render(request, "bookings/appointment_not_found.html", status=404)
    just_booked = request.GET.get("nuevo") == "1" and appointment.is_confirmed
    deposit = public_deposit(appointment.business)
    context = {
        "appointment": appointment,
        "date_label": long_date(timezone.localdate(appointment.start_at)),
        "can_change": appointment.customer_can_change(),
        "can_reschedule": appointment.customer_can_change()
        and accepts_bookings(appointment.business),
        "change_limit_hours": settings.CUSTOMER_CHANGE_LIMIT_HOURS,
        "just_booked": just_booked,
        "first_name": (appointment.customer_name.split() or [""])[0],
        "confetti": confetti() if just_booked else [],
        # Always from the appointment's own business, never from the request.
        "deposit": deposit,
        "breakdown": deposit_breakdown(deposit, appointment.service, appointment.price),
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
    notify_owner_cancelled(appointment)
    return redirect("appointment_detail", token=token)


def reschedule_slots(appointment, professional, date):
    """Free times for the same service with `professional`, other than the current one."""
    slots = available_slots(professional, appointment.service, date, ignore=appointment)
    if professional != appointment.professional:
        return slots
    return [slot for slot in slots if slot != appointment.start_at]


def render_reschedule(request, appointment, query, slot_form=None, status=200):
    chosen = selected_values(query)
    professional = chosen.get("professional") or appointment.professional
    date = chosen.get("date")
    date_given = bool(query.data.get("date")) if query.is_bound else False
    month = parse_month(request.GET.get("month")) or (date.replace(day=1) if date else None)
    strip = month_strip(month, [professional], selected=date)
    strip.update(
        month_links(
            reverse("reschedule_appointment", args=[appointment.manage_token]),
            strip,
            {"professional": professional.pk},
        )
    )
    professionals = list(appointment.business.professionals.filter(is_active=True))
    checked = (
        slot_form.data.get("start_at", "") if slot_form is not None and slot_form.is_bound else ""
    )
    return render(
        request,
        "bookings/reschedule.html",
        {
            "appointment": appointment,
            "date_label_current": long_date(timezone.localdate(appointment.start_at)),
            "query": query,
            "professionals": [
                {
                    "pk": p.pk,
                    "name": p.name,
                    "initial": p.name[:1].upper(),
                    "tint": PROFESSIONAL_TINTS[i % len(PROFESSIONAL_TINTS)],
                    "checked": p.pk == professional.pk,
                }
                for i, p in enumerate(professionals)
            ],
            "choose_professional": len(professionals) > 1,
            "professional": professional,
            "date": date,
            "date_label": long_date(date) if date else "",
            "date_error": query.errors.get("date") if date_given else None,
            "strip": strip,
            "slot_form": slot_form,
            "slot_groups": slot_groups(slot_form.slots.values() if slot_form else [], checked),
            "change_limit_hours": settings.CUSTOMER_CHANGE_LIMIT_HOURS,
        },
        status=status,
    )


NOT_TAKING_BOOKINGS = (
    "Este negocio no está tomando reservas online en este momento. Podés cancelar tu turno o "
    "contactar al negocio para cambiarlo."
)


def reschedule_appointment(request, token):
    current = get_appointment(token)
    if (
        current is not None
        and current.customer_can_change()
        and not accepts_bookings(current.business)
    ):
        return render_appointment(request, current, notice=NOT_TAKING_BOOKINGS)
    if request.method != "POST":
        appointment = current
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
        previous_start, previous_professional = appointment.start_at, appointment.professional
        try:
            with transaction.atomic():
                appointment.move_to(slot_form.cleaned_data["start_at"], professional=professional)
        except IntegrityError:
            appointment.refresh_from_db()
            slot_form.add_error("start_at", TAKEN_MESSAGE)
            return render_reschedule(request, appointment, query, slot_form)

    manage_path = reverse("appointment_detail", args=[token])
    send_rescheduled(appointment, request.build_absolute_uri(manage_path))
    notify_owner_rescheduled(appointment, previous_start, previous_professional)
    return redirect(manage_path)
