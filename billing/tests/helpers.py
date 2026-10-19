from datetime import timedelta

from django.utils import timezone

from billing.models import Plan, Subscription


def end_trial(business, days_ago=1):
    """Move the business's trial into the past, as if it had already finished."""
    now = timezone.now()
    Subscription.objects.filter(business=business).update(
        trial_started_at=now - timedelta(days=14 + days_ago),
        trial_ends_at=now - timedelta(days=days_ago),
    )
    return Subscription.objects.get(business=business)


def set_active(business, plan_code, period_end=None):
    Subscription.objects.filter(business=business).update(
        status=Subscription.ACTIVE,
        plan=Plan.objects.get(code=plan_code),
        current_period_end=period_end,
    )
    return Subscription.objects.get(business=business)
