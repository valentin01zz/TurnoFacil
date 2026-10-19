"""Single source of truth for what a business may do right now."""

from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Subscription


@dataclass
class Access:
    status: str
    status_label: str
    subscription: Subscription | None
    plan: object | None  # the plan whose features apply now; None means read-only
    features: set = field(default_factory=set)
    in_trial: bool = False
    trial_ends_at: object = None
    trial_days_left: int = 0
    active_professionals: int = 0

    @property
    def read_only(self):
        return self.plan is None

    @property
    def max_professionals(self):
        return self.plan.max_professionals if self.plan else 0

    @property
    def over_limit(self):
        return self.plan is not None and self.active_professionals > self.plan.max_professionals

    @property
    def can_add_professional(self):
        return self.plan is not None and self.active_professionals < self.plan.max_professionals

    def can(self, feature):
        return feature in self.features


def days_left(ends_at, now):
    """Whole days left, counting any remaining part of a day as one."""
    seconds = (ends_at - now).total_seconds()
    return max(0, -int(-seconds // 86400))


def get_access(business, now=None):
    now = now or timezone.now()
    subscription = (
        Subscription.objects.select_related("plan", "selected_plan")
        .filter(business=business)
        .first()
    )
    active_professionals = business.professionals.filter(is_active=True).count()
    if subscription is None:
        # Every business gets a subscription at signup or by migration; none means something broke.
        return Access(
            "missing", "Sin suscripción", None, None, active_professionals=active_professionals
        )

    in_trial = subscription.trial_ends_at > now and subscription.status in (
        Subscription.TRIALING,
        Subscription.PENDING_PAYMENT,
    )
    plan = None
    status = subscription.status
    if subscription.status == Subscription.ACTIVE:
        if subscription.current_period_end is None or subscription.current_period_end > now:
            plan = subscription.plan
    elif subscription.status == Subscription.PAST_DUE:
        grace_end = (subscription.current_period_end or now) + timedelta(
            days=settings.PAST_DUE_GRACE_DAYS
        )
        if grace_end > now:
            plan = subscription.plan
    elif in_trial:
        plan = subscription.plan
    elif subscription.status == Subscription.TRIALING:
        # The trial ended but the scheduled task has not updated the status yet.
        status = Subscription.TRIAL_EXPIRED

    return Access(
        status=status,
        status_label=dict(Subscription.STATUSES).get(status, status),
        subscription=subscription,
        plan=plan,
        features=set(plan.features) if plan else set(),
        in_trial=in_trial,
        trial_ends_at=subscription.trial_ends_at,
        trial_days_left=days_left(subscription.trial_ends_at, now) if in_trial else 0,
        active_professionals=active_professionals,
    )
