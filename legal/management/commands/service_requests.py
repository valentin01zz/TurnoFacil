from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from legal.models import ServiceRequest


class Command(BaseCommand):
    help = (
        "List cancellation and withdrawal requests that need the operator (refunds, manual review, "
        "or unconfirmed for over a day), or mark one as resolved."
    )

    def add_arguments(self, parser):
        parser.add_argument("--resolve", metavar="CODE")
        parser.add_argument("--note", default="", help="What was done (with --resolve)")

    def handle(self, resolve=None, note="", **options):
        if resolve:
            return self.resolve(resolve, note)
        day_ago = timezone.now() - timedelta(days=1)
        pending = [
            r
            for r in ServiceRequest.objects.select_related("business")
            if r.needs_operator or (r.confirmed_at is None and r.created_at < day_ago)
        ]
        if not pending:
            self.stdout.write("Nothing pending.")
            return
        for r in pending:
            state = r.get_outcome_display() if r.confirmed_at else "Sin confirmar por email"
            business = r.business.slug if r.business else "-"
            created = timezone.localtime(r.created_at)
            self.stdout.write(
                f"{r.code}  {r.get_kind_display():<17} {created:%Y-%m-%d %H:%M}  "
                f"{business:<25} {state}"
            )

    def resolve(self, code, note):
        found = ServiceRequest.objects.filter(code=code).first()
        if found is None:
            raise CommandError(f"No request with code {code}.")
        if not note:
            raise CommandError("Say what was done with --note.")
        found.resolved_at = timezone.now()
        found.resolution_note = note[:300]
        found.save(update_fields=["resolved_at", "resolution_note"])
        self.stdout.write(f"{code} resolved.")
