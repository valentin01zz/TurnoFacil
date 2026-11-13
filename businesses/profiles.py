"""Panel profiles for separate agendas (ADR-0006).

With `Business.separate_agendas` on, everyone logs in with the business account and then picks a
profile (the owner or one professional) and types its PIN. The chosen profile lives in the session,
with the PIN version it was opened with: changing a PIN closes that profile everywhere.

A professional's profile only reaches that professional's appointments, time off and reports. The
owner's profile reaches everything, as the panel always did. With the option off, everyone is the
owner. Views use `scoped_professional(request)` to narrow every query, and the middleware keeps
professionals out of the owner's pages, so hiding a button is never the only barrier.
"""

import re
from dataclasses import dataclass

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode

from .models import Professional

SESSION_KEY = "panel_profile"
PIN_PATTERN = re.compile(r"^\d{4,6}$")
TOO_EASY = {"1234", "12345", "123456", "4321", "54321", "654321"}

# Pages that are about the whole business: only the owner's profile opens them.
OWNER_ONLY = {
    "business_edit",
    "deposit_settings",
    "agenda_settings",
    "service_list",
    "service_create",
    "service_edit",
    "professional_list",
    "professional_create",
    "professional_edit",
    "plans",
    "choose_plan",
    "checkout",
    "payment_return",
    "cancel_subscription",
}
# Reachable without a chosen profile (choosing one, the owner's PIN recovery).
NO_PROFILE_NEEDED = {"choose_profile", "switch_profile", "owner_pin_forgot", "owner_pin_reset"}


@dataclass(frozen=True)
class Profile:
    professional: Professional | None = None  # None: the owner

    @property
    def is_owner(self):
        return self.professional is None

    @property
    def name(self):
        return "Dueño" if self.is_owner else self.professional.name


OWNER = Profile()


def pin_problem(pin):
    """Why `pin` cannot be used, or None."""
    if not PIN_PATTERN.match(pin or ""):
        return "El PIN tiene entre 4 y 6 números."
    if len(set(pin)) == 1 or pin in TOO_EASY:
        return "Ese PIN es muy fácil de adivinar. Elegí otro."
    return None


def hash_pin(pin):
    return make_password(pin)


def pin_matches(pin, hashed):
    return bool(hashed) and check_password(pin, hashed)


def current_profile(request):
    """The profile in use, or None when the business has separate agendas and none is chosen."""
    business = request.user.business
    if not business.separate_agendas:
        return OWNER
    data = request.session.get(SESSION_KEY) or {}
    if data.get("business") != business.pk:
        return None
    if data.get("owner"):
        return OWNER if data.get("version") == business.owner_pin_version else None
    professional = business.professionals.filter(
        pk=data.get("professional"), is_active=True
    ).first()
    if professional and professional.pin and data.get("version") == professional.pin_version:
        return Profile(professional)
    return None


def open_profile(request, professional=None):
    business = request.user.business
    if professional is None:
        data = {"owner": True, "version": business.owner_pin_version}
    else:
        data = {"professional": professional.pk, "version": professional.pin_version}
    request.session[SESSION_KEY] = {"business": business.pk, **data}


def close_profile(request):
    request.session.pop(SESSION_KEY, None)


def scoped_professional(request):
    """The professional whose data this request may see, or None for the whole business.

    Without a chosen profile there is nothing to see: never fall back to the whole business."""
    profile = getattr(request, "panel_profile", None)
    if profile is None:
        raise PermissionDenied("No panel profile chosen")
    return profile.professional


def safe_next(request, url):
    allowed = url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    return url if url and allowed else reverse("panel")


class PanelProfileMiddleware:
    """Asks for a profile on every panel page and keeps professionals out of the owner's pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        request.panel_profile = None
        user = request.user
        if not user.is_authenticated or not hasattr(user, "business"):
            return None
        # Also outside the panel, so every page's header shows the right menu (or none).
        profile = request.panel_profile = current_profile(request)
        if not request.path.startswith("/panel/"):
            return None
        name = request.resolver_match.url_name if request.resolver_match else None
        if name in NO_PROFILE_NEEDED:
            return None
        if profile is None:
            next_url = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('choose_profile')}?{next_url}")
        if not profile.is_owner and name in OWNER_ONLY:
            return redirect("panel")
        return None
