from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from billing.models import Plan


class Command(BaseCommand):
    help = (
        "Change a plan's monthly price or professional limit, e.g. set_plan esencial --price 15900"
    )

    def add_arguments(self, parser):
        parser.add_argument("code")
        parser.add_argument("--price", help="Monthly price in the plan's currency")
        parser.add_argument("--max-professionals", type=int)
        parser.add_argument("--name")

    def handle(self, code, price=None, max_professionals=None, name=None, **options):
        try:
            plan = Plan.objects.get(code=code)
        except Plan.DoesNotExist as error:
            raise CommandError(f"No existe el plan {code!r}") from error
        if price is not None:
            try:
                plan.monthly_price = Decimal(price)
            except InvalidOperation as error:
                raise CommandError("El precio tiene que ser un número") from error
            if plan.monthly_price < 0:
                raise CommandError("El precio no puede ser negativo")
        if max_professionals is not None:
            if max_professionals < 1:
                raise CommandError("El límite tiene que ser al menos 1")
            plan.max_professionals = max_professionals
        if name:
            plan.name = name
        plan.save()
        self.stdout.write(
            f"{plan.code}: {plan.name}, {plan.currency} {plan.monthly_price}, "
            f"hasta {plan.max_professionals} profesionales"
        )
