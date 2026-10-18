from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .emails import send_reminder
from .models import Appointment


def due_reminders(now):
    return Appointment.objects.filter(
        status=Appointment.CONFIRMED,
        reminder_due_at__lte=now,
        reminder_sent_at__isnull=True,
        start_at__gt=now,
    ).exclude(customer_email="")


def send_due_reminders(now=None):
    """Send every reminder that is due and mark it, so each appointment gets at most one.

    Rows are locked while sending; a second run at the same time skips them. A failed send
    is left unmarked and retried on the next run.
    """
    now = now or timezone.now()
    sent = 0
    for pk in due_reminders(now).values_list("pk", flat=True):
        with transaction.atomic():
            appointment = (
                due_reminders(now)
                .select_for_update(skip_locked=True, of=("self",))
                .select_related("business", "service", "professional")
                .filter(pk=pk)
                .first()
            )
            if appointment is None:
                continue
            path = reverse("appointment_detail", args=[appointment.manage_token])
            if send_reminder(appointment, f"{settings.SITE_URL}{path}"):
                appointment.reminder_sent_at = now
                appointment.save(update_fields=["reminder_sent_at", "updated_at"])
                sent += 1
    return sent
