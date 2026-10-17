import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_confirmation(appointment, manage_url):
    """Email the customer their booking details. A failure is logged, never raised."""
    if not appointment.customer_email:
        return
    context = {"appointment": appointment, "manage_url": manage_url}
    try:
        send_mail(
            subject=f"Turno confirmado en {appointment.business.name}",
            message=render_to_string("bookings/emails/confirmation.txt", context),
            from_email=None,
            recipient_list=[appointment.customer_email],
        )
    except Exception:
        logger.exception("Could not send confirmation email for appointment %s", appointment.pk)
