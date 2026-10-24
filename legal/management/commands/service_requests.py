from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from legal.models import ServiceRequest
from legal.services import (
    notify_operator,
    operator_notice_due,
    send_record,
    send_request_received,
)


class Command(BaseCommand):
    help = (
        "List cancellation and withdrawal requests that need the operator (refunds, manual review, "
        "emails that failed, or unconfirmed for over a day), resend their email, or mark one as "
        "resolved."
    )

    def add_arguments(self, parser):
        parser.add_argument("--resolve", metavar="CODE")
        parser.add_argument("--note", default="", help="What was done (with --resolve)")
        parser.add_argument(
            "--resend",
            metavar="CODE",
            help="Send again the email that failed: the code (and link) or the written record",
        )

    def handle(self, resolve=None, note="", resend=None, **options):
        if resolve:
            return self.resolve(resolve, note)
        if resend:
            return self.resend(resend)
        day_ago = timezone.now() - timedelta(days=1)
        pending = [
            r
            for r in ServiceRequest.objects.select_related("business")
            if r.needs_operator
            or r.email_failed
            or operator_notice_due(r)
            or (r.confirmed_at is None and r.created_at < day_ago)
        ]
        if not pending:
            self.stdout.write("Nothing pending.")
            return
        for r in pending:
            state = r.get_outcome_display() if r.confirmed_at else "Sin confirmar por email"
            if r.refund_due and r.resolved_at is None:
                state += " · reembolso pendiente"
            if r.email_failed:
                state += " · EMAIL NO ENVIADO (--resend)"
            if r.confirmed_at and operator_notice_due(r):
                state += " · AVISO AL OPERADOR NO ENVIADO (--resend)"
            business = r.business.slug if r.business else "-"
            created = timezone.localtime(r.created_at)
            self.stdout.write(
                f"{r.code}  {r.get_kind_display():<17} {created:%Y-%m-%d %H:%M}  "
                f"{business:<25} {state}"
            )

    def find(self, code):
        found = ServiceRequest.objects.filter(code=code).first()
        if found is None:
            raise CommandError(f"No request with code {code}.")
        return found

    def resend(self, code):
        """Repeat only emails: the cancellation itself is never applied twice."""
        found = self.find(code)
        if found.confirmed_at is None:
            jobs = [("code and confirmation link", send_request_received)]
        else:
            jobs = []
            # The record is resent on demand even if it went out (the person may have lost it).
            if found.done_email_sent_at is None or not operator_notice_due(found):
                jobs.append(("written record", send_record))
            if operator_notice_due(found):
                jobs.append(("operator notice", notify_operator))
        for what, send in jobs:
            if not send(found):
                raise CommandError(f"The {what} email failed again; check the email settings.")
            self.stdout.write(f"Sent the {what} for {code}.")

    def resolve(self, code, note):
        found = self.find(code)
        if not note:
            raise CommandError("Say what was done with --note.")
        found.resolved_at = timezone.now()
        found.resolution_note = note[:300]
        found.save(update_fields=["resolved_at", "resolution_note"])
        self.stdout.write(f"{code} resolved.")
