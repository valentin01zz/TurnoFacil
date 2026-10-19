"""Trial expiry notices to business owners: once per kind, only the most urgent one that applies."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .access import days_left
from .models import Subscription, TrialNotice
from .services import expire_trial_if_due

logger = logging.getLogger(__name__)

SUBJECTS = {
    TrialNotice.DAYS_7: "Te quedan 7 días de prueba en TurnoFacil",
    TrialNotice.DAYS_3: "Te quedan 3 días de prueba en TurnoFacil",
    TrialNotice.DAYS_1: "Mañana termina tu prueba de TurnoFacil",
    TrialNotice.ENDED: "Terminó tu prueba de TurnoFacil",
}


def due_notice(subscription, now):
    """The single most urgent notice for this subscription right now, or None."""
    if subscription.trial_ends_at <= now:
        return TrialNotice.ENDED
    remaining = subscription.trial_ends_at - now
    for kind, days in ((TrialNotice.DAYS_1, 1), (TrialNotice.DAYS_3, 3), (TrialNotice.DAYS_7, 7)):
        if remaining <= timedelta(days=days):
            return kind
    return None


def send_notice(subscription, kind, now):
    business = subscription.business
    context = {
        "business": business,
        "subscription": subscription,
        "kind": kind,
        "days_left": days_left(subscription.trial_ends_at, now),
        "trial_ends_at": subscription.trial_ends_at,
        "plans_url": f"{settings.SITE_URL}{reverse('plans')}",
    }
    send_mail(
        subject=SUBJECTS[kind],
        message=render_to_string("billing/emails/trial_notice.txt", context),
        from_email=None,
        recipient_list=[business.owner.email],
    )


def run_billing_tasks(now=None):
    """Expire finished trials and send due notices. Safe to run any number of times."""
    now = now or timezone.now()
    sent = 0
    candidates = Subscription.objects.select_related("business__owner").filter(
        status__in=[
            Subscription.TRIALING,
            Subscription.PENDING_PAYMENT,
            Subscription.TRIAL_EXPIRED,
        ],
        trial_ends_at__lte=now + timedelta(days=7),
    )
    for subscription in candidates:
        expire_trial_if_due(subscription, now)
        kind = due_notice(subscription, now)
        if kind is None:
            continue
        try:
            with transaction.atomic():
                # The unique constraint is the lock: a second run cannot send it again.
                notice = TrialNotice.objects.create(subscription=subscription, kind=kind)
                send_notice(subscription, kind, now)
        except IntegrityError:
            continue  # already sent
        except Exception:
            logger.exception("Could not send trial notice %s for %s", kind, subscription.pk)
            continue
        sent += 1 if notice else 0
    return sent
