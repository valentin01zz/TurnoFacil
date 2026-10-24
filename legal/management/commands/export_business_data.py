import json

from django.core.management.base import BaseCommand, CommandError

from businesses.models import Business
from legal.data import business_data


class Command(BaseCommand):
    help = (
        "Print as JSON everything TurnoFacil keeps about one business: to answer an access "
        "request from its owner (Ley 25.326 art. 14) or to hand the business its data."
    )

    def add_arguments(self, parser):
        parser.add_argument("slug")

    def handle(self, slug, **options):
        business = Business.objects.filter(slug=slug).first()
        if business is None:
            raise CommandError(f"No business with slug {slug}.")
        self.stdout.write(json.dumps(business_data(business), ensure_ascii=False, indent=2))
