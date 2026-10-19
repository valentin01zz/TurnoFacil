from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from billing.models import Plan
from billing.services import (
    InvalidTransition,
    activate,
    active_professionals,
    add_months,
    set_provider_reference,
    start_trial,
)
from businesses.models import Business


class Command(BaseCommand):
    help = (
        "Operator only: activate a plan without an online payment (the free pilot plan, or a "
        "payment settled outside the app). Usage: grant_plan <slug> <plan-code> [--months N]"
    )

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("plan")
        parser.add_argument(
            "--months",
            type=int,
            help="Paid months to grant. Without it the plan has no end date (pilot only).",
        )

    def handle(self, slug, plan, months=None, **options):
        try:
            business = Business.objects.get(slug=slug)
            plan_obj = Plan.objects.get(code=plan)
        except (Business.DoesNotExist, Plan.DoesNotExist) as error:
            raise CommandError(str(error)) from error
        if months is not None and months < 1:
            raise CommandError("--months tiene que ser al menos 1")
        count = active_professionals(business)
        if count > plan_obj.max_professionals:
            raise CommandError(
                f"{business.name} tiene {count} profesionales activos y {plan_obj.name} permite "
                f"{plan_obj.max_professionals}. Desactivá los que sobren antes de otorgarlo."
            )
        subscription = start_trial(business)
        if subscription.renews_automatically:
            raise CommandError(
                f"{business.name} paga con {subscription.provider}: cancelá ese cobro antes de "
                "otorgar un plan a mano, para no cobrarle dos veces."
            )
        # A transfer for the next month extends the paid period instead of overlapping it.
        start = timezone.now()
        if subscription.current_period_end and subscription.current_period_end > start:
            start = subscription.current_period_end
        period_end = add_months(start, months) if months else None
        subscription = set_provider_reference(subscription, "", "")
        try:
            activate(
                subscription, plan_obj, period_end, f"Plan {plan_obj.name} otorgado por un operador"
            )
        except InvalidTransition as error:
            raise CommandError(f"No se puede activar desde el estado actual: {error}") from error
        until = (
            f"hasta el {timezone.localtime(period_end):%d/%m/%Y}"
            if period_end
            else "sin vencimiento"
        )
        self.stdout.write(f"{business.name}: plan {plan_obj.name} activo, {until}")
