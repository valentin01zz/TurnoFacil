"""Choosing a panel profile, PINs and the separate agendas setting (ADR-0006)."""

import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.throttle import is_limited, record

from .forms import AgendaSettingsForm, ChangeMyPinForm, ChooseProfileForm, NewPinForm
from .profiles import close_profile, hash_pin, open_profile, pin_matches, safe_next

logger = logging.getLogger(__name__)

TOO_MANY_PINS = "Demasiados intentos con este perfil. Probá de nuevo en 15 minutos."
RESET_SALT = "businesses.owner-pin-reset"
RESET_MAX_AGE = timedelta(hours=1)


def profile_choices(business):
    """Everyone who can open a profile now: the owner and each active professional with a PIN."""
    choices = [{"value": "owner", "name": "Dueño", "detail": "Ve y administra todo el negocio"}]
    for professional in business.professionals.filter(is_active=True):
        choices.append(
            {
                "value": str(professional.pk),
                "name": professional.name,
                "detail": "Su agenda" if professional.pin else "Sin PIN: pedíselo al dueño",
                "disabled": not professional.pin,
                "professional": professional,
            }
        )
    return choices


@login_required
def choose_profile(request):
    business = request.user.business
    if not business.separate_agendas:
        return redirect("panel")
    choices = profile_choices(business)
    next_url = request.POST.get("next") or request.GET.get("next", "")
    form = ChooseProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        value = form.cleaned_data["profile"]
        chosen = next((c for c in choices if c["value"] == value and not c.get("disabled")), None)
        if chosen is None:
            form.add_error(None, "Elegí un perfil de la lista.")
        else:
            professional = chosen.get("professional")
            key = f"{business.pk}:{value}"
            hashed = business.owner_pin if professional is None else professional.pin
            if is_limited("profile_pin", key):
                form.add_error(None, TOO_MANY_PINS)
            elif pin_matches(form.cleaned_data["pin"], hashed):
                open_profile(request, professional)
                return redirect(safe_next(request, next_url))
            else:
                record("profile_pin", key)
                form.add_error("pin", "El PIN no es correcto.")
    return render(
        request,
        "businesses/choose_profile.html",
        {
            "form": form,
            "choices": choices,
            "chosen": request.POST.get("profile", ""),
            "next": next_url,
        },
    )


@login_required
@require_POST
def switch_profile(request):
    close_profile(request)
    return redirect("choose_profile")


def reset_token(business):
    return signing.dumps(
        {"b": business.pk, "v": business.owner_pin_version}, salt=RESET_SALT, compress=True
    )


def read_reset_token(token, business):
    try:
        data = signing.loads(token, salt=RESET_SALT, max_age=RESET_MAX_AGE.total_seconds())
    except signing.BadSignature:
        return False
    # Used once: setting the new PIN bumps the version, so the same link stops working.
    return data == {"b": business.pk, "v": business.owner_pin_version}


@login_required
def owner_pin_forgot(request):
    """Mail a one-hour link to the account email. The account password is not enough: everyone
    in the business shares it."""
    business = request.user.business
    if request.method == "POST":
        key = str(business.pk)
        if not is_limited("owner_pin_reset", key):
            record("owner_pin_reset", key)
            link = request.build_absolute_uri(
                reverse("owner_pin_reset", args=[reset_token(business)])
            )
            try:
                send_mail(
                    subject="Tu PIN de dueño en TurnoFacil",
                    message=render_to_string(
                        "businesses/emails/owner_pin_reset.txt",
                        {"business": business, "link": link},
                    ),
                    from_email=None,
                    recipient_list=[request.user.email],
                )
            except Exception:
                logger.exception("Could not send the owner PIN link for business %s", business.pk)
        # Same answer either way: nothing here tells whether the limit was reached.
        messages.success(
            request,
            "Te mandamos un link al email de la cuenta para elegir un PIN nuevo. Vence en 1 hora.",
        )
        return redirect("choose_profile")
    return render(request, "businesses/owner_pin_forgot.html", {"email": request.user.email})


@login_required
def owner_pin_reset(request, token):
    business = request.user.business
    if not read_reset_token(token, business):
        messages.error(request, "El link venció o ya se usó. Pedí uno nuevo.")
        return redirect("choose_profile")
    form = NewPinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        business.owner_pin = hash_pin(form.cleaned_data["new_pin"])
        business.owner_pin_version += 1
        business.save(update_fields=["owner_pin", "owner_pin_version"])
        open_profile(request)
        messages.success(request, "Listo, guardamos tu PIN nuevo.")
        return redirect("panel")
    return render(request, "businesses/owner_pin_reset.html", {"form": form})


@login_required
def my_pin(request):
    """A professional changes their own PIN; the owner changes theirs in the agenda settings."""
    professional = request.panel_profile.professional
    if professional is None:
        return redirect("agenda_settings")
    form = ChangeMyPinForm(request.POST or None, hashed=professional.pin)
    if request.method == "POST" and form.is_valid():
        professional.pin = hash_pin(form.cleaned_data["new_pin"])
        professional.pin_version += 1
        professional.save(update_fields=["pin", "pin_version"])
        open_profile(request, professional)
        messages.success(request, "Listo, cambiamos tu PIN.")
        return redirect("panel")
    return render(request, "businesses/my_pin.html", {"form": form})


@login_required
def agenda_settings(request):
    business = request.user.business
    # A form with every box unticked posts no fields: still a submitted form.
    form = AgendaSettingsForm(
        request.POST if request.method == "POST" else None,
        business=business,
        initial={"separate_agendas": business.separate_agendas},
    )
    if request.method == "POST" and form.is_valid():
        turning_on = form.cleaned_data["separate_agendas"] and not business.separate_agendas
        business.separate_agendas = form.cleaned_data["separate_agendas"]
        fields = ["separate_agendas"]
        if form.cleaned_data["new_pin"]:
            business.owner_pin = hash_pin(form.cleaned_data["new_pin"])
            business.owner_pin_version += 1
            fields += ["owner_pin", "owner_pin_version"]
        business.save(update_fields=fields)
        if business.separate_agendas:
            # Whoever just typed (or kept) the owner's PIN here stays in as the owner.
            open_profile(request)
        messages.success(
            request,
            "Listo, cada profesional entra ahora con su PIN."
            if turning_on
            else "Listo, guardamos los cambios.",
        )
        return redirect("agenda_settings")
    professionals = business.professionals.filter(is_active=True)
    return render(
        request,
        "businesses/agenda_settings.html",
        {
            "form": form,
            "business": business,
            "without_pin": [p for p in professionals if not p.pin],
        },
    )
