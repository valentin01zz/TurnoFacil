from datetime import timedelta

from django.utils import timezone

from billing.models import Plan, Subscription, SubscriptionEvent
from legal.models import LegalDocument

TERMS_TEXT = "# Términos\n\n## 1. Quién presta el servicio\nTexto con **negrita**.\n\n- Uno\n- Dos"


def publish(kind=LegalDocument.TERMS, version="1.0", body=TERMS_TEXT, effective_at=None):
    return LegalDocument.objects.create(
        kind=kind, version=version, body=body, effective_at=effective_at or timezone.now()
    )


def renewing(business, contracted_days_ago=3, code="profesional"):
    """An active Mercado Pago subscription, first paid `contracted_days_ago` days ago."""
    subscription = Subscription.objects.get(business=business)
    Subscription.objects.filter(pk=subscription.pk).update(
        status=Subscription.ACTIVE,
        plan=Plan.objects.get(code=code),
        current_period_end=timezone.now() + timedelta(days=25),
        provider="mercadopago",
        provider_subscription_id=f"pre_{business.pk}",
        canceled_at=None,
    )
    event = SubscriptionEvent.objects.create(
        subscription=subscription,
        from_status=Subscription.TRIALING,
        to_status=Subscription.ACTIVE,
        reason="Primer pago",
    )
    SubscriptionEvent.objects.filter(pk=event.pk).update(
        created_at=timezone.now() - timedelta(days=contracted_days_ago)
    )
    return Subscription.objects.get(pk=subscription.pk)


class FakeProvider:
    """Stops the renewal the way the Mercado Pago provider does, without calling the API."""

    def __init__(self, fail=False):
        self.fail = fail
        self.cancelled = []

    def cancel(self, subscription):
        from billing import services
        from billing.payments import PaymentError

        if self.fail:
            raise PaymentError("down")
        self.cancelled.append(subscription.pk)
        return services.schedule_cancel(subscription, "Baja pedida por el dueño")
