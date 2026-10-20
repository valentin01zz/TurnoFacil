"""Payment provider interface (ADR-0004, ADR-0005).

A provider keeps card data on its side and only activates a subscription after it verifies, with the
provider itself, that the payment or authorization is real. TurnoFacil never stores card or
payment-method data. `ManualProvider` is the default when no provider is configured.
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string

from . import services

logger = logging.getLogger(__name__)


@dataclass
class CheckoutResult:
    redirect_url: str | None
    message: str


class PaymentError(Exception):
    """The provider could not complete a request. Nothing was changed on our side."""


class PaymentNotFound(PaymentError):
    """The provider says the resource does not exist (for our credentials)."""


class PaymentProvider:
    name = ""
    # Whether the checkout page asks for the payer's account email at the provider.
    collects_payer_email = False

    def start_checkout(self, subscription, plan):
        """Begin paying for `plan`. Must not mark anything as paid."""
        raise NotImplementedError

    def verify_confirmation(self, payload):
        """Verify a provider notification; return (provider_subscription_id, period_end)."""
        raise NotImplementedError

    def change_plan(self, subscription, plan):
        """Charge `plan`'s price from the next payment of a renewing subscription."""
        raise NotImplementedError

    def cancel(self, subscription):
        """Stop the recurring charge at the provider."""
        raise NotImplementedError

    def sync(self, subscription):
        """Bring the subscription up to date with the provider (missed notifications)."""
        return subscription

    def reconcile(self, now=None):
        """Periodic catch-up with the provider; returns how many subscriptions it checked."""
        return 0


class ManualProvider(PaymentProvider):
    """Default until a provider is connected: records the choice and explains the next step."""

    name = "manual"

    def start_checkout(self, subscription, plan):
        return CheckoutResult(
            redirect_url=None,
            message=(
                f"Listo, elegiste el plan {plan.name}. Todavía no cobramos online: "
                "te vamos a contactar para activar el pago. Mientras tanto, tu cuenta sigue igual."
            ),
        )

    def verify_confirmation(self, payload):
        raise NotImplementedError("El proveedor manual no recibe confirmaciones")


def get_provider():
    return import_string(settings.PAYMENT_PROVIDER)()


def reconcile_subscriptions(now=None):
    """Scheduled upkeep: close ended cancellations, flag unconfirmed charges, sync the provider."""
    provider = get_provider()
    warn_about_other_providers(provider)
    return {
        "closed": services.finish_due_cancellations(now),
        "past_due": services.flag_unconfirmed_renewals(now),
        "synced": provider.reconcile(now),
    }


def warn_about_other_providers(provider):
    """Subscriptions paid through another provider cannot be synced: the setting is probably
    missing in this process (for example, the scheduled job on the hosting)."""
    from .models import Subscription

    others = (
        Subscription.objects.exclude(provider="")
        .exclude(provider=provider.name)
        .exclude(provider_subscription_id="")
        .filter(
            status__in=(Subscription.PENDING_PAYMENT, Subscription.ACTIVE, Subscription.PAST_DUE)
        )
        .count()
    )
    if others:
        logger.error(
            "%s subscriptions belong to another payment provider than %r: check PAYMENT_PROVIDER",
            others,
            provider.name,
        )


def confirm_payment(provider, payload):
    """Activate a subscription from a provider notification, only after the provider verifies it."""
    from .models import Subscription

    provider_subscription_id, period_end = provider.verify_confirmation(payload)
    subscription = Subscription.objects.get(
        provider=provider.name, provider_subscription_id=provider_subscription_id
    )
    plan = subscription.selected_plan or subscription.plan
    return services.activate(subscription, plan, period_end, f"Pago confirmado por {provider.name}")
