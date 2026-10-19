"""The only place where subscriptions are created or change state."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Plan, Subscription, SubscriptionEvent

TRIAL_PLAN_CODE = "profesional"

ALLOWED_TRANSITIONS = {
    Subscription.TRIALING: {
        Subscription.PENDING_PAYMENT,
        Subscription.TRIAL_EXPIRED,
        Subscription.ACTIVE,
    },
    Subscription.TRIAL_EXPIRED: {Subscription.PENDING_PAYMENT, Subscription.ACTIVE},
    Subscription.PENDING_PAYMENT: {
        Subscription.PENDING_PAYMENT,
        Subscription.ACTIVE,
        Subscription.TRIAL_EXPIRED,
    },
    Subscription.ACTIVE: {
        Subscription.PAST_DUE,
        Subscription.CANCELED,
        Subscription.PENDING_PAYMENT,
    },
    Subscription.PAST_DUE: {Subscription.ACTIVE, Subscription.CANCELED},
    Subscription.CANCELED: {Subscription.PENDING_PAYMENT, Subscription.ACTIVE},
}


class InvalidTransition(Exception):
    pass


class PlanLimitExceeded(Exception):
    def __init__(self, plan, active_professionals):
        self.plan = plan
        self.active_professionals = active_professionals
        self.excess = active_professionals - plan.max_professionals
        super().__init__(
            f"{plan.name} permite {plan.max_professionals} profesionales activos y hay "
            f"{active_professionals}."
        )


def start_trial(business, now=None):
    """Create the business's only subscription, in trial. Calling it again changes nothing."""
    now = now or timezone.now()
    subscription, created = Subscription.objects.get_or_create(
        business=business,
        defaults={
            "plan": Plan.objects.get(code=TRIAL_PLAN_CODE),
            "status": Subscription.TRIALING,
            "trial_started_at": now,
            "trial_ends_at": now + timedelta(days=settings.TRIAL_DAYS),
        },
    )
    if created:
        SubscriptionEvent.objects.create(
            subscription=subscription, to_status=Subscription.TRIALING, reason="Prueba iniciada"
        )
    return subscription


def transition(subscription, to_status, reason, **fields):
    """Move to `to_status` if the transition is allowed, saving `fields` and logging the change."""
    from_status = subscription.status
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise InvalidTransition(f"{from_status} -> {to_status} no está permitido")
    with transaction.atomic():
        locked = Subscription.objects.select_for_update().get(pk=subscription.pk)
        if locked.status != from_status:
            raise InvalidTransition("La suscripción cambió mientras se procesaba")
        locked.status = to_status
        for name, value in fields.items():
            setattr(locked, name, value)
        locked.save()
        SubscriptionEvent.objects.create(
            subscription=locked, from_status=from_status, to_status=to_status, reason=reason
        )
    subscription.refresh_from_db()
    return subscription


def active_professionals(business):
    return business.professionals.filter(is_active=True).count()


def choose_plan(subscription, plan):
    """Record the owner's choice. It never activates anything: payment must be confirmed first."""
    if not plan.is_public:
        raise InvalidTransition("Ese plan no se puede elegir")
    count = active_professionals(subscription.business)
    if count > plan.max_professionals:
        raise PlanLimitExceeded(plan, count)
    return transition(
        subscription,
        Subscription.PENDING_PAYMENT,
        f"Eligió el plan {plan.name}",
        selected_plan=plan,
    )


def expire_trial_if_due(subscription, now=None):
    now = now or timezone.now()
    if subscription.status == Subscription.TRIALING and subscription.trial_ends_at <= now:
        return transition(subscription, Subscription.TRIAL_EXPIRED, "La prueba terminó")
    return subscription


def activate(subscription, plan, period_end, reason):
    """Mark as paid. Only a confirmed payment (payments.py) or an operator grant may call this."""
    return transition(
        subscription,
        Subscription.ACTIVE,
        reason,
        plan=plan,
        selected_plan=None,
        current_period_end=period_end,
        canceled_at=None,
    )
