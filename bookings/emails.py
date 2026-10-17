import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_confirmation(appointment, manage_url):
    send_customer_email(
        appointment,
        manage_url,
        subject=f"Turno confirmado en {appointment.business.name}",
        template="bookings/emails/confirmation.txt",
    )


def send_rescheduled(appointment, manage_url):
    send_customer_email(
        appointment,
        manage_url,
        subject=f"Turno reprogramado en {appointment.business.name}",
        template="bookings/emails/rescheduled.txt",
    )


def send_customer_email(appointment, manage_url, subject, template):
    """Email the customer about their appointment. A failure is logged, never raised."""
    if not appointment.customer_email:
        return
    context = {"appointment": appointment, "manage_url": manage_url}
    try:
        send_mail(
            subject=subject,
            message=render_to_string(template, context),
            from_email=None,
            recipient_list=[appointment.customer_email],
        )
    except Exception:
        logger.exception("Could not send email for appointment %s", appointment.pk)
