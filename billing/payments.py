"""Payment provider interface. No provider is connected yet (see ADR-0004).

A real provider (for example Mercado Pago subscriptions) will implement `PaymentProvider`,
keep card data on its side, and call `confirm_payment` only from a verified notification.
TurnoFacil never stores card or payment-method data.
"""

from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string

from . import services


@dataclass
class CheckoutResult:
    redirect_url: str | None
    message: str


class PaymentProvider:
    name = ""

    def start_checkout(self, subscription, plan):
        """Begin paying for `plan`. Must not mark anything as paid."""
        raise NotImplementedError

    def verify_confirmation(self, payload):
        """Verify a provider notification; return (provider_subscription_id, period_end)."""
        raise NotImplementedError


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


def confirm_payment(provider, payload):
    """Activate a subscription from a provider notification, only after the provider verifies it."""
    from .models import Subscription

    provider_subscription_id, period_end = provider.verify_confirmation(payload)
    subscription = Subscription.objects.get(
        provider=provider.name, provider_subscription_id=provider_subscription_id
    )
    plan = subscription.selected_plan or subscription.plan
    return services.activate(subscription, plan, period_end, f"Pago confirmado por {provider.name}")
