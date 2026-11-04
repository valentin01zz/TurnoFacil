import json

from django.core.management.base import BaseCommand

from legal.data import appointment_data, customer_appointments, erase_customer


class Command(BaseCommand):
    help = (
        "Show (or with --erase, erase) the appointments booked with a customer's email, to answer "
        "that customer's access or deletion request. Only their own appointments are shown."
    )

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument(
            "--erase",
            action="store_true",
            help="Erase name, phone and email from past and cancelled appointments",
        )

    def handle(self, email, erase=False, **options):
        if erase:
            erased, future = erase_customer(email)
            self.stdout.write(f"Erased the details of {erased} appointment(s).")
            if future:
                self.stdout.write(
                    f"{future} future appointment(s) kept: the business has to cancel them first."
                )
            return
        data = [appointment_data(a, with_business=True) for a in customer_appointments(email)]
        self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
