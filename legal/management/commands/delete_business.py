from django.core.management.base import BaseCommand, CommandError

from businesses.models import Business
from legal.data import delete_business


class Command(BaseCommand):
    help = (
        "Delete a business, its owner account and all its data (services, professionals, "
        "appointments with their customers' details, subscription, acceptances). Irreversible: "
        "export it first with export_business_data if the owner wants a copy."
    )

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--yes", action="store_true", help="Confirm the deletion")

    def handle(self, slug, yes=False, **options):
        business = Business.objects.filter(slug=slug).first()
        if business is None:
            raise CommandError(f"No business with slug {slug}.")
        subscription = getattr(business, "subscription", None)
        if subscription is not None and subscription.renews_automatically:
            raise CommandError("Its subscription still renews: cancel it at the provider first.")
        if not yes:
            count = business.appointments.count()
            raise CommandError(
                f"This deletes {business.name} ({business.owner.email}) and {count} "
                "appointment(s). Run again with --yes to do it."
            )
        delete_business(business)
        self.stdout.write(f"Deleted {slug}.")
