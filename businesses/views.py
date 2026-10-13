from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Business


@login_required
def panel(request):
    business = request.user.business
    booking_url = request.build_absolute_uri(reverse("booking_page", args=[business.slug]))
    return render(
        request, "businesses/panel.html", {"business": business, "booking_url": booking_url}
    )


def booking_page(request, slug):
    business = get_object_or_404(Business, slug=slug)
    return render(request, "businesses/booking_page.html", {"business": business})
