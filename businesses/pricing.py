"""Prices customers see (HU-36): always the final amount, "desde" when it varies, and the deposit
split into total, deposit and balance (Ley 24.240 art. 4; Res. SICyC 4/2025)."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PublicPrice:
    amount: Decimal
    varies: bool  # "desde": the final amount can be higher
    note: str  # what sets the final amount, required when it varies


@dataclass(frozen=True)
class DepositBreakdown:
    deposit: Decimal
    price: PublicPrice | None  # None when the business hides its prices

    @property
    def balance(self):
        """What is left to pay at the business (a deposit counts toward the price)."""
        if self.price is None:
            return None
        return max(self.price.amount - self.deposit, Decimal("0"))


def public_price(service, price=None):
    """The price to show for `service` (or an appointment's saved `price`), or None.

    Only when the business chose to show prices and there is one.
    """
    amount = service.price if price is None else price
    if amount is None or not service.business.show_prices:
        return None
    return PublicPrice(amount, service.price_varies, service.price_note)


def deposit_breakdown(deposit, service, price=None):
    if deposit is None:
        return None
    return DepositBreakdown(deposit.amount, public_price(service, price))
