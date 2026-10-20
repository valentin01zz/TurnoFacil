from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from billing.catalog import BOOKING_DEPOSIT, PANEL_EDIT
from billing.decorators import requires_feature
from bookings.models import Appointment

from .forms import (
    AgendaForm,
    BusinessForm,
    DepositSettingsForm,
    ProfessionalForm,
    ServiceForm,
    working_hours_formset,
)
from .models import DepositSettings, Professional, Service

DEPOSIT_NOT_IN_PLAN = (
    "La seña por transferencia está en los planes Profesional y Negocio. "
    "Cambiá de plan para usarla."
)

PROFESSIONAL_TINTS = ["#FFB59E", "#B9A8FF", "#8EE3D8", "#FFD98A", "#FF9EC4", "#A8D8FF"]
WEEKDAY_INITIALS = ["L", "M", "M", "J", "V", "S", "D"]


def get_owned_or_404(request, model, pk):
    """Fetch an object only if it belongs to the logged-in owner's business."""
    return get_object_or_404(model, pk=pk, business=request.user.business)


def day_start(date):
    return timezone.make_aware(datetime.combine(date, datetime.min.time()))


def agenda_url(date, professional=None):
    url = f"{reverse('panel')}?date={date.isoformat()}"
    return f"{url}&professional={professional.pk}" if professional else url


def week_chart(business, date, professional):
    """Confirmed appointments per day for the Monday-to-Sunday week that contains `date`."""
    monday = date - timedelta(days=date.weekday())
    appointments = Appointment.objects.filter(
        business=business,
        status=Appointment.CONFIRMED,
        start_at__gte=day_start(monday),
        start_at__lt=day_start(monday + timedelta(days=7)),
    )
    if professional:
        appointments = appointments.filter(professional=professional)
    counts = [0] * 7
    for start_at in appointments.values_list("start_at", flat=True):
        counts[timezone.localtime(start_at).weekday()] += 1
    peak = max(counts) or 1
    return [
        {
            "date": monday + timedelta(days=i),
            "initial": WEEKDAY_INITIALS[i],
            "count": counts[i],
            "height": max(round(counts[i] / peak * 100), 6),
            "selected": monday + timedelta(days=i) == date,
            "url": agenda_url(monday + timedelta(days=i), professional),
        }
        for i in range(7)
    ]


@login_required
def panel(request):
    business = request.user.business
    booking_url = request.build_absolute_uri(reverse("booking_page", args=[business.slug]))

    today = timezone.localdate()
    now = timezone.now()
    data = request.GET.copy()
    if not data.get("date"):
        data["date"] = today.isoformat()
    form = AgendaForm(data, business=business)
    date, professional = today, None
    if form.is_valid():
        date = form.cleaned_data["date"] or today
        professional = form.cleaned_data["professional"]

    professionals = list(business.professionals.all())
    tints = {
        pro.pk: PROFESSIONAL_TINTS[i % len(PROFESSIONAL_TINTS)]
        for i, pro in enumerate(professionals)
    }

    appointments = (
        Appointment.objects.filter(
            business=business,
            status=Appointment.CONFIRMED,
            start_at__gte=day_start(date),
            start_at__lt=day_start(date + timedelta(days=1)),
        )
        .select_related("service", "professional")
        .order_by("start_at", "professional__name")
    )
    if professional:
        appointments = appointments.filter(professional=professional)
    appointments = list(appointments)

    next_appointment = next((a for a in appointments if a.start_at >= now), None)
    for appointment in appointments:
        appointment.tint = tints.get(appointment.professional_id, PROFESSIONAL_TINTS[0])
        appointment.ended = appointment.end_at <= now
        appointment.is_next = appointment is next_appointment

    filters = [{"label": "Todos", "url": agenda_url(date), "selected": professional is None}]
    filters += [
        {
            "label": pro.name,
            "url": agenda_url(date, pro),
            "selected": professional is not None and pro.pk == professional.pk,
            "tint": tints[pro.pk],
        }
        for pro in professionals
    ]

    return render(
        request,
        "businesses/panel.html",
        {
            "business": business,
            "booking_url": booking_url,
            "form": form,
            "date": date,
            "today": today,
            "previous_url": agenda_url(date - timedelta(days=1), professional),
            "next_url": agenda_url(date + timedelta(days=1), professional),
            "today_url": agenda_url(today, professional),
            "professional": professional,
            "show_professional": len(professionals) > 1,
            "filters": filters,
            "appointments": appointments,
            "manual_count": sum(1 for a in appointments if a.source == Appointment.MANUAL),
            "next_appointment": next_appointment if date == today else None,
            "first_appointment": appointments[0] if appointments else None,
            "week": week_chart(business, date, professional),
        },
    )


@login_required
@requires_feature(PANEL_EDIT)
def business_edit(request):
    form = BusinessForm(request.POST or None, instance=request.user.business)
    saved = False
    if request.method == "POST" and form.is_valid():
        form.save()
        saved = True
    return render(request, "businesses/business_form.html", {"form": form, "saved": saved})


@login_required
@requires_feature(PANEL_EDIT)
def deposit_settings(request):
    """Deposit by bank transfer: only plans with the feature, checked here on every request."""
    business = request.user.business
    allowed = request.access.can(BOOKING_DEPOSIT)
    deposit = DepositSettings.objects.filter(business=business).first()
    deposit = deposit or DepositSettings(business=business)
    if not allowed:
        if request.method == "POST":
            messages.error(request, DEPOSIT_NOT_IN_PLAN)
            return redirect("deposit_settings")
        return render(
            request, "businesses/deposit_settings.html", {"allowed": False, "deposit": deposit}
        )
    form = DepositSettingsForm(request.POST or None, instance=deposit)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Listo, guardamos los cambios.")
        return redirect("deposit_settings")
    saved = DepositSettings.objects.filter(business=business).first()
    return render(
        request,
        "businesses/deposit_settings.html",
        {"allowed": True, "form": form, "preview": saved if saved and saved.enabled else None},
    )


@login_required
def service_list(request):
    services = request.user.business.services.all()
    return render(request, "businesses/service_list.html", {"services": services})


@login_required
@requires_feature(PANEL_EDIT)
def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.business = request.user.business
        service.save()
        return redirect("service_list")
    return render(request, "businesses/service_form.html", {"form": form, "is_new": True})


@login_required
@requires_feature(PANEL_EDIT)
def service_edit(request, pk):
    service = get_owned_or_404(request, Service, pk)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("service_list")
    return render(request, "businesses/service_form.html", {"form": form, "is_new": False})


@login_required
def professional_list(request):
    professionals = request.user.business.professionals.prefetch_related("working_hours")
    return render(request, "businesses/professional_list.html", {"professionals": professionals})


@login_required
@requires_feature(PANEL_EDIT)
def professional_create(request):
    if not request.access.can_add_professional:
        messages.warning(request, limit_message(request.access))
        return redirect("professional_list")
    professional = Professional(business=request.user.business)
    return professional_form(request, professional, extra=7, is_new=True)


@login_required
@requires_feature(PANEL_EDIT)
def professional_edit(request, pk):
    professional = get_owned_or_404(request, Professional, pk)
    return professional_form(request, professional, extra=3, is_new=False)


def limit_message(access):
    limit = access.max_professionals
    return (
        f"Tu plan permite hasta {limit} profesional{'es' if limit != 1 else ''} "
        f"activo{'s' if limit != 1 else ''} y ya tenés {access.active_professionals}. "
        "Desactivá uno o pasate a un plan más grande."
    )


def professional_form(request, professional, extra, is_new):
    was_active = bool(professional.pk) and professional.is_active
    form = ProfessionalForm(request.POST or None, instance=professional)
    formset = working_hours_formset(extra)(
        request.POST or None, instance=professional, prefix="hours"
    )
    if request.method == "POST" and form.is_valid():
        # Creating or reactivating a professional must respect the plan limit (server-side).
        becomes_active = form.cleaned_data["is_active"] and not was_active
        if becomes_active and not request.access.can_add_professional:
            form.add_error("is_active", limit_message(request.access))
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
        return redirect("professional_list")
    return render(
        request,
        "businesses/professional_form.html",
        {"form": form, "formset": formset, "is_new": is_new},
    )
