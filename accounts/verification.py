"""Email verification: a signed, expiring link proves the owner controls the mailbox."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)
SALT = "accounts.verify-email"


def make_token(user):
    return signing.dumps({"u": user.pk, "e": user.email_canonical}, salt=SALT)


def read_token(token):
    """Return the token payload, or None if it was altered or has expired."""
    max_age = timedelta(days=settings.EMAIL_VERIFICATION_DAYS).total_seconds()
    try:
        return signing.loads(token, salt=SALT, max_age=max_age)
    except signing.BadSignature:
        return None


def can_resend(user, now=None):
    now = now or timezone.now()
    if user.verification_sent_at is None:
        return True
    wait = timedelta(seconds=settings.EMAIL_VERIFICATION_RESEND_SECONDS)
    return user.verification_sent_at + wait <= now


def send_verification(request, user):
    """Email the verification link. Returns whether it was sent; never raises."""
    link = request.build_absolute_uri(reverse("verify_email", args=[make_token(user)]))
    context = {"user": user, "link": link, "days": settings.EMAIL_VERIFICATION_DAYS}
    try:
        send_mail(
            subject="Confirmá tu email para empezar con TurnoFacil",
            message=render_to_string("accounts/emails/verify_email.txt", context),
            from_email=None,
            recipient_list=[user.email],
        )
    except Exception:
        logger.exception("Could not send verification email to user %s", user.pk)
        return False
    user.verification_sent_at = timezone.now()
    user.save(update_fields=["verification_sent_at"])
    return True


def verify(user):
    """Mark the email as verified and start the business's single free trial (once)."""
    from billing.services import start_trial

    with transaction.atomic():
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
        business = getattr(user, "business", None)
        if business is not None:
            start_trial(business)
