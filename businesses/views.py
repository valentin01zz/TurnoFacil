from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ServiceForm
from .models import Business, Service


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


def booking_page(request, slug):
    business = get_object_or_404(Business, slug=slug)
    services = business.services.filter(is_active=True)
    return render(
        request, "businesses/booking_page.html", {"business": business, "services": services}
    )
