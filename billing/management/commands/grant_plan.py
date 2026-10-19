import calendar

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from billing.models import Plan
from billing.services import InvalidTransition, activate, active_professionals, start_trial
from businesses.models import Business


def add_months(moment, months):
    index = moment.month - 1 + months
    year, month = moment.year + index // 12, index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


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
        period_end = add_months(timezone.now(), months) if months else None
        subscription = start_trial(business)
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
