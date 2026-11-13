"""A professional's own email for appointment notices (ADR-0006).

The owner types it; notices only go there after the professional opens the signed link we send to
that address, so a typo never sends customer data to a stranger.
"""

import logging
from datetime import timedelta

from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

SALT = "businesses.professional-email"
MAX_AGE = timedelta(days=3)


def make_token(professional):
    return signing.dumps({"p": professional.pk, "e": professional.email.lower()}, salt=SALT)


def read_token(token):
    try:
        return signing.loads(token, salt=SALT, max_age=MAX_AGE.total_seconds())
    except signing.BadSignature:
        return None


def send_confirmation(request, professional):
    """Email the confirmation link. Returns whether it was sent; never raises."""
    link = request.build_absolute_uri(
        reverse("confirm_professional_email", args=[make_token(professional)])
    )
    context = {"professional": professional, "business": professional.business, "link": link}
    try:
        send_mail(
            subject=f"Confirmá tu email para los avisos de {professional.business.name}",
            message=render_to_string("businesses/emails/professional_email.txt", context),
            from_email=None,
            recipient_list=[professional.email],
        )
    except Exception:
        logger.exception(
            "Could not send the email confirmation to professional %s", professional.pk
        )
        return False
    return True


def confirm(token):
    """Mark the address in `token` as confirmed. Returns the professional, or None if the link is
    altered, expired, or the email changed since it was sent."""
    from .models import Professional

    data = read_token(token)
    if data is None:
        return None
    professional = Professional.objects.filter(pk=data.get("p")).select_related("business").first()
    if professional is None or professional.email.lower() != data.get("e"):
        return None
    if professional.email_verified_at is None:
        professional.email_verified_at = timezone.now()
        professional.save(update_fields=["email_verified_at"])
    return professional
