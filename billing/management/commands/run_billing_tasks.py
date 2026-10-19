from django.core.management.base import BaseCommand

from billing.notices import run_billing_tasks
from billing.payments import reconcile_subscriptions


class Command(BaseCommand):
    help = (
        "Expire finished trials, send trial notices and keep paid subscriptions up to date. "
        "Safe to run often."
    )

    def handle(self, *args, **options):
        sent = run_billing_tasks()
        self.stdout.write(f"Trial notices sent: {sent}")
        result = reconcile_subscriptions()
        self.stdout.write(
            f"Subscriptions closed: {result['closed']}, past due: {result['past_due']}, "
            f"synced with provider: {result['synced']}"
        )
