from django.core.management.base import BaseCommand

from bookings.reminders import send_due_reminders


class Command(BaseCommand):
    help = "Send the appointment reminders that are due. Meant to run every 15 minutes."

    def handle(self, *args, **options):
        sent = send_due_reminders()
        self.stdout.write(f"Reminders sent: {sent}")
