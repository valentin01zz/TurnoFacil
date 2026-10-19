from django.core.management.base import BaseCommand

from billing.notices import run_billing_tasks


class Command(BaseCommand):
    help = "Expire finished trials and send trial notices. Safe to run often."

    def handle(self, *args, **options):
        sent = run_billing_tasks()
        self.stdout.write(f"Trial notices sent: {sent}")
