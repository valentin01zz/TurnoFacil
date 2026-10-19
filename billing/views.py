import json
import logging

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .access import get_access
from .catalog import feature_labels
from .mercadopago import MercadoPagoProvider, valid_signature
from .models import Plan
from .payments import PaymentError, get_provider
from .services import InvalidTransition, PlanLimitExceeded, choose_plan, first_charge_at

logger = logging.getLogger(__name__)


def plan_cards(access):
    cards = []
    for plan in Plan.objects.filter(is_public=True):
        cards.append(
            {
                "plan": plan,
                "features": feature_labels(plan.features),
                "is_current": access.plan is not None
                and access.plan.pk == plan.pk
                and not access.in_trial,
                "is_selected": access.subscription is not None
                and access.subscription.selected_plan_id == plan.pk,
                "fits": access.active_professionals <= plan.max_professionals,
                "excess": max(0, access.active_professionals - plan.max_professionals),
            }
        )
    return cards


def transfer_details():
    """Bank transfer data for the plans page, or None when it is not offered."""
    if not settings.TRANSFER_ALIAS:
        return None
    return {
        "alias": settings.TRANSFER_ALIAS,
        "holder": settings.TRANSFER_HOLDER,
        "cuit": settings.TRANSFER_CUIT,
        "contact": settings.BILLING_CONTACT_EMAIL,
    }


def limit_message(plan, error):
    return (
        f"El plan {plan.name} permite hasta {plan.max_professionals} profesional"
        f"{'es' if plan.max_professionals != 1 else ''} activo"
        f"{'s' if plan.max_professionals != 1 else ''}. Tenés {error.active_professionals}: "
        f"desactivá {error.excess} para elegirlo."
    )


@login_required
def plans(request):
    access = get_access(request.user.business)
    provider = get_provider()
    return render(
        request,
        "billing/plans.html",
        {
            "access": access,
            "cards": plan_cards(access),
            "trial_days": settings.TRIAL_DAYS,
            "pays_online": provider.collects_payer_email,
            "transfer": transfer_details(),
        },
    )


@login_required
@require_POST
def choose(request, code):
    plan = get_object_or_404(Plan, code=code, is_public=True)
    access = get_access(request.user.business)
    subscription = access.subscription
    if subscription is None:
        messages.error(request, "No encontramos tu suscripción. Escribinos para revisarlo.")
        return redirect("plans")
    provider = get_provider()
    if provider.collects_payer_email:
        if subscription.renews_automatically:
            return change_renewing_plan(request, provider, subscription, plan)
        return redirect("checkout", code=plan.code)
    try:
        subscription = choose_plan(subscription, plan)
    except PlanLimitExceeded as error:
        messages.error(request, limit_message(plan, error))
        return redirect("plans")
    except InvalidTransition:
        messages.error(request, "No pudimos cambiar tu plan ahora. Probá de nuevo en un rato.")
        return redirect("plans")
    result = provider.start_checkout(subscription, plan)
    if result.redirect_url:
        return redirect(result.redirect_url)
    messages.success(request, result.message)
    return redirect("plans")


def change_renewing_plan(request, provider, subscription, plan):
    try:
        provider.change_plan(subscription, plan)
    except PlanLimitExceeded as error:
        messages.error(request, limit_message(plan, error))
    except (InvalidTransition, PaymentError):
        logger.exception("Could not change plan for subscription %s", subscription.pk)
        messages.error(request, "No pudimos cambiar tu plan ahora. Probá de nuevo en un rato.")
    else:
        messages.success(
            request,
            f"Listo, ya tenés el plan {plan.name}. Desde el próximo cobro se te debita "
            f"$ {plan.monthly_price:,.0f} por mes.".replace(",", "."),
        )
    return redirect("plans")


class CheckoutForm(forms.Form):
    payer_email = forms.EmailField(
        label="Email de tu cuenta de Mercado Pago",
        help_text="Tiene que ser el mismo con el que entrás a Mercado Pago.",
    )


@login_required
def checkout(request, code):
    plan = get_object_or_404(Plan, code=code, is_public=True)
    provider = get_provider()
    access = get_access(request.user.business)
    subscription = access.subscription
    if not provider.collects_payer_email or subscription is None:
        return redirect("plans")
    if subscription.renews_automatically:
        return redirect("plans")
    form = CheckoutForm(request.POST or None, initial={"payer_email": request.user.email})
    if request.method == "POST" and form.is_valid():
        try:
            result = provider.start_checkout(
                subscription, plan, payer_email=form.cleaned_data["payer_email"]
            )
        except PlanLimitExceeded as error:
            messages.error(request, limit_message(plan, error))
            return redirect("plans")
        except (InvalidTransition, PaymentError):
            logger.exception("Could not start checkout for subscription %s", subscription.pk)
            form.add_error(
                None, "No pudimos conectarnos con Mercado Pago. Probá de nuevo en unos minutos."
            )
        else:
            return redirect(result.redirect_url)
    return render(
        request,
        "billing/checkout.html",
        {
            "access": access,
            "plan": plan,
            "form": form,
            "first_charge": first_charge_at(subscription),
            "charges_now": first_charge_at(subscription) <= timezone.now(),
            "transfer": transfer_details(),
        },
    )


@login_required
def payment_return(request):
    """Mercado Pago sends the owner back here; ask it right away instead of waiting."""
    subscription = get_access(request.user.business).subscription
    if subscription is not None:
        try:
            get_provider().sync(subscription)
        except PaymentError:
            logger.warning("Could not sync subscription %s on return", subscription.pk)
        subscription.refresh_from_db()
        if subscription.renews_automatically:
            messages.success(request, "¡Listo! Tu suscripción quedó activa.")
        else:
            messages.info(
                request,
                "Si completaste el pago, Mercado Pago nos lo confirma en unos minutos y tu plan "
                "se activa solo.",
            )
    return redirect("plans")


@login_required
def cancel(request):
    access = get_access(request.user.business)
    subscription = access.subscription
    if subscription is None or not subscription.renews_automatically:
        return redirect("plans")
    if request.method == "POST":
        try:
            get_provider().cancel(subscription)
        except (InvalidTransition, PaymentError):
            logger.exception("Could not cancel subscription %s", subscription.pk)
            messages.error(request, "No pudimos dar de baja ahora. Probá de nuevo en un rato.")
        else:
            messages.success(request, "Listo, diste de baja tu suscripción. No se te cobra más.")
        return redirect("plans")
    return render(request, "billing/cancel_confirm.html", {"access": access})


@csrf_exempt
@require_POST
def mercadopago_webhook(request):
    provider = get_provider()
    if not isinstance(provider, MercadoPagoProvider):
        return HttpResponse(status=404)
    if not settings.MERCADOPAGO_WEBHOOK_SECRET:
        logger.error("Mercado Pago notification received without MERCADOPAGO_WEBHOOK_SECRET")
        return HttpResponse(status=503)
    query_id = request.GET.get("data.id", "")
    if not valid_signature(
        settings.MERCADOPAGO_WEBHOOK_SECRET,
        request.headers.get("x-signature", ""),
        request.headers.get("x-request-id", ""),
        query_id,
    ):
        logger.warning("Rejected a Mercado Pago notification with an invalid signature")
        return HttpResponse(status=401)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    topic = request.GET.get("type") or request.GET.get("topic") or body.get("type", "")
    resource_id = query_id or str((body.get("data") or {}).get("id", ""))
    try:
        provider.process_notification(topic, resource_id)
    except PaymentError:
        logger.warning("Could not process Mercado Pago notification %s %s", topic, resource_id)
        return HttpResponse(status=502)  # Mercado Pago retries later
    return HttpResponse(status=200)
