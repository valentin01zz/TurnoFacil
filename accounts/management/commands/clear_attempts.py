from django.core.management.base import BaseCommand

from accounts import throttle


class Command(BaseCommand):
    help = (
        "Delete rate-limit attempts (IP and email) older than one day. Run by the cron, so the "
        "privacy policy's 24 hours hold even when nobody uses the site."
    )

    def handle(self, **options):
        deleted = throttle.purge()
        self.stdout.write(f"Deleted {deleted} old attempt(s).")
