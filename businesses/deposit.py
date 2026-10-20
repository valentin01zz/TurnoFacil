"""The deposit (seña) customers see: only when the owner turned it on and the plan includes it."""

from billing.access import get_access
from billing.catalog import BOOKING_DEPOSIT

from .models import DepositSettings


def public_deposit(business):
    """Deposit details to show for `business`, or None.

    Checked on every request, so a business that loses the feature (another plan, read-only)
    stops showing them at once while its settings are kept.
    """
    deposit = DepositSettings.objects.filter(business=business, enabled=True).first()
    if deposit is None or not get_access(business).can(BOOKING_DEPOSIT):
        return None
    return deposit
