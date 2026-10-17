from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ProfessionalForm, ServiceForm, working_hours_formset
from .models import Business, Professional, Service


def get_owned_or_404(request, model, pk):
    """Fetch an object only if it belongs to the logged-in owner's business."""
    return get_object_or_404(model, pk=pk, business=request.user.business)


@login_required
def panel(request):
    business = request.user.business
    booking_url = request.build_absolute_uri(reverse("booking_page", args=[business.slug]))
    return render(
        request, "businesses/panel.html", {"business": business, "booking_url": booking_url}
    )


@login_required
def service_list(request):
    services = request.user.business.services.all()
    return render(request, "businesses/service_list.html", {"services": services})


@login_required
def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.business = request.user.business
        service.save()
        return redirect("service_list")
    return render(request, "businesses/service_form.html", {"form": form, "is_new": True})


@login_required
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
def professional_create(request):
    professional = Professional(business=request.user.business)
    return professional_form(request, professional, extra=7, is_new=True)


@login_required
def professional_edit(request, pk):
    professional = get_owned_or_404(request, Professional, pk)
    return professional_form(request, professional, extra=2, is_new=False)


def professional_form(request, professional, extra, is_new):
    form = ProfessionalForm(request.POST or None, instance=professional)
    formset = working_hours_formset(extra)(
        request.POST or None, instance=professional, prefix="hours"
    )
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


def booking_page(request, slug):
    business = get_object_or_404(Business, slug=slug)
    services = business.services.filter(is_active=True)
    professionals = business.professionals.filter(is_active=True)
    return render(
        request,
        "businesses/booking_page.html",
        {
            "business": business,
            "services": services,
            "professionals": professionals,
            "is_taking_bookings": services.exists() and professionals.exists(),
        },
    )
