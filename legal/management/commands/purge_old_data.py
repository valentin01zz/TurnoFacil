from django.conf import settings
from django.core.management.base import BaseCommand

from legal.data import purge_appointments


class Command(BaseCommand):
    help = (
        "Delete appointments that ended more than APPOINTMENT_RETENTION_DAYS days ago. Does "
        "nothing while that setting is empty (the retention period is the Founder's decision)."
    )

    def handle(self, **options):
        days = settings.APPOINTMENT_RETENTION_DAYS
        if days is None:
            self.stdout.write("APPOINTMENT_RETENTION_DAYS is not set: nothing deleted.")
            return
        deleted = purge_appointments(days)
        self.stdout.write(f"Deleted {deleted} appointment(s) older than {days} days.")
