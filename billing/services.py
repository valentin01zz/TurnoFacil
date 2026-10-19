"""The only place where subscriptions are created or change state."""

import calendar
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
        Subscription.ACTIVE,  # renewal, plan change or scheduled cancellation
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


def ensure_plan_fits(subscription, plan):
    """An owner may only pick a public plan that holds their active professionals."""
    if not plan.is_public:
        raise InvalidTransition("Ese plan no se puede elegir")
    count = active_professionals(subscription.business)
    if count > plan.max_professionals:
        raise PlanLimitExceeded(plan, count)


def choose_plan(subscription, plan):
    """Record the owner's choice. It never activates anything: payment must be confirmed first."""
    ensure_plan_fits(subscription, plan)
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


def add_months(moment, months):
    index = moment.month - 1 + months
    year, month = moment.year + index // 12, index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def first_charge_at(subscription, now=None):
    """When a new recurring payment should first charge: never before the time already granted."""
    now = now or timezone.now()
    candidates = [now]
    if subscription.status in (Subscription.TRIALING, Subscription.PENDING_PAYMENT):
        candidates.append(subscription.trial_ends_at)
    if subscription.current_period_end:
        candidates.append(subscription.current_period_end)
    return max(candidates)


def set_provider_reference(subscription, provider, reference):
    """Remember the provider's id for the checkout just started. It grants nothing by itself."""
    Subscription.objects.filter(pk=subscription.pk).update(
        provider=provider, provider_subscription_id=reference, updated_at=timezone.now()
    )
    subscription.refresh_from_db()
    return subscription


def change_active_plan(subscription, plan):
    """Switch a renewing subscription to `plan` now; the provider charges the new price next."""
    if subscription.status != Subscription.ACTIVE:
        raise InvalidTransition("Solo se cambia de plan con la suscripción al día")
    ensure_plan_fits(subscription, plan)
    return transition(subscription, Subscription.ACTIVE, f"Cambió al plan {plan.name}", plan=plan)


def schedule_cancel(subscription, reason, now=None):
    """Stop renewing. Access lasts until the paid period ends (see finish_due_cancellations)."""
    now = now or timezone.now()
    if subscription.status == Subscription.PAST_DUE:
        return transition(subscription, Subscription.CANCELED, reason, canceled_at=now)
    return transition(subscription, Subscription.ACTIVE, reason, canceled_at=now)


def mark_past_due(subscription, reason):
    return transition(subscription, Subscription.PAST_DUE, reason)


def finish_due_cancellations(now=None):
    """Close subscriptions whose owners canceled, once the period they paid for is over."""
    now = now or timezone.now()
    closed = 0
    for subscription in Subscription.objects.filter(
        status=Subscription.ACTIVE, canceled_at__isnull=False, current_period_end__lte=now
    ):
        transition(subscription, Subscription.CANCELED, "Terminó el período pago tras la baja")
        closed += 1
    return closed


def flag_unconfirmed_renewals(now=None):
    """Renewing subscriptions whose charge was not confirmed a day after the period ended."""
    now = now or timezone.now()
    flagged = 0
    for subscription in Subscription.objects.filter(
        status=Subscription.ACTIVE,
        canceled_at__isnull=True,
        current_period_end__lte=now - timedelta(days=1),
    ).exclude(provider_subscription_id=""):
        mark_past_due(subscription, "No recibimos la confirmación del cobro mensual")
        flagged += 1
    return flagged
