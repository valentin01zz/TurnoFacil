import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from businesses.deposit import public_deposit

logger = logging.getLogger(__name__)


def send_confirmation(appointment, manage_url):
    send_customer_email(
        appointment,
        manage_url,
        subject=f"Turno confirmado en {appointment.business.name}",
        template="bookings/emails/confirmation.txt",
        deposit=public_deposit(appointment.business),
    )


def send_rescheduled(appointment, manage_url):
    send_customer_email(
        appointment,
        manage_url,
        subject=f"Turno reprogramado en {appointment.business.name}",
        template="bookings/emails/rescheduled.txt",
    )


def send_cancelled(appointment, manage_url, reason=""):
    """`reason` is the owner's note for the customer, shown as written (one line)."""
    return send_customer_email(
        appointment,
        manage_url,
        subject=f"Turno cancelado en {appointment.business.name}",
        template="bookings/emails/cancelled.txt",
        reason=reason,
    )


def send_reminder(appointment, manage_url):
    return send_customer_email(
        appointment,
        manage_url,
        subject=f"Recordatorio: tu turno en {appointment.business.name}",
        template="bookings/emails/reminder.txt",
    )


def send_customer_email(appointment, manage_url, subject, template, deposit=None, reason=""):
    """Email the customer about their appointment. Returns whether it was sent; never raises."""
    if not appointment.customer_email:
        return False
    context = {
        "appointment": appointment,
        "manage_url": manage_url,
        "change_limit_hours": settings.CUSTOMER_CHANGE_LIMIT_HOURS,
        "deposit": deposit,
        "reason": reason,
    }
    try:
        send_mail(
            # A line break in a header makes the send fail, so subjects are kept on one line.
            subject=" ".join(subject.split()),
            message=render_to_string(template, context),
            from_email=None,
            recipient_list=[appointment.customer_email],
        )
    except Exception:
        logger.exception("Could not send email for appointment %s", appointment.pk)
        return False
    return True
