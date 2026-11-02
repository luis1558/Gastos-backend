from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from app.shared.constants import InterestType, RatePeriod

ZERO = Decimal("0")
CENT = Decimal("0.01")
DAYS_IN_YEAR = Decimal("365")
MONTHS_IN_YEAR = Decimal("12")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class Balance:
    principal_remaining: Decimal
    interest_outstanding: Decimal
    interest_accrued_total: Decimal

    @property
    def total_owed(self) -> Decimal:
        return self.principal_remaining + self.interest_outstanding


def _to_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def monthly_rate(rate_percent: Decimal, period: RatePeriod) -> Decimal:
    """Nominal monthly rate as a fraction (12% annual -> 0.01)."""
    fraction = rate_percent / HUNDRED
    if period == RatePeriod.MONTHLY:
        return fraction
    return fraction / MONTHS_IN_YEAR


def _accrue(
    interest_type: InterestType,
    rate: Decimal,
    period: RatePeriod,
    principal: Decimal,
    interest: Decimal,
    days: int,
) -> Decimal:
    """Interest generated during `days` days on the current balance."""
    if interest_type == InterestType.NONE or days <= 0 or rate <= ZERO:
        return ZERO
    per_month = monthly_rate(rate, period)
    if interest_type == InterestType.SIMPLE:
        # Interest is charged on the principal only, never on unpaid interest.
        return principal * per_month * MONTHS_IN_YEAR * days / DAYS_IN_YEAR
    # Compound: unpaid interest joins the base; monthly capitalisation,
    # with fractional months handled through the exponent.
    base = principal + interest
    exponent = Decimal(days) * MONTHS_IN_YEAR / DAYS_IN_YEAR
    return base * ((Decimal(1) + per_month) ** exponent - Decimal(1))


def calculate_balance(
    *,
    interest_type: InterestType,
    rate_period: RatePeriod,
    base_rate: Decimal,
    origin_date: date,
    original_amount: Decimal,
    payments: Iterable[tuple[date, Decimal]],
    rate_changes: Iterable[tuple[date, Decimal]],
    as_of: date,
) -> Balance:
    """Walk the debt timeline (rate changes and payments) up to `as_of`.

    Payments settle accrued interest first and then principal.
    """
    # Rate changes sort before payments on the same day (kind 0 < 1).
    events: list[tuple[date, int, Decimal]] = []
    for effective_date, rate in rate_changes:
        events.append((max(effective_date, origin_date), 0, _to_decimal(rate)))
    for payment_date, amount in payments:
        events.append((max(payment_date, origin_date), 1, _to_decimal(amount)))
    events.sort(key=lambda item: (item[0], item[1]))

    principal = _to_decimal(original_amount)
    interest = ZERO
    accrued_total = ZERO
    rate = _to_decimal(base_rate)
    cursor = origin_date

    for event_date, kind, value in events:
        if event_date > as_of:
            break
        generated = _accrue(
            interest_type, rate, rate_period, principal, interest, (event_date - cursor).days
        )
        interest += generated
        accrued_total += generated
        cursor = event_date
        if kind == 0:
            rate = value
            continue
        paid_interest = min(value, interest)
        interest -= paid_interest
        principal = max(ZERO, principal - (value - paid_interest))

    if as_of > cursor:
        generated = _accrue(
            interest_type, rate, rate_period, principal, interest, (as_of - cursor).days
        )
        interest += generated
        accrued_total += generated

    return Balance(
        principal_remaining=principal.quantize(CENT),
        interest_outstanding=interest.quantize(CENT),
        interest_accrued_total=accrued_total.quantize(CENT),
    )


def rate_in_effect(
    base_rate: Decimal,
    rate_changes: Iterable[tuple[date, Decimal]],
    as_of: date,
) -> Decimal:
    current = _to_decimal(base_rate)
    for effective_date, rate in sorted(rate_changes, key=lambda item: item[0]):
        if effective_date <= as_of:
            current = _to_decimal(rate)
    return current


def balance_for_debt(debt, as_of: date, extra_payment: Optional[tuple[date, Decimal]] = None) -> Balance:
    """Convenience wrapper that reads the inputs from a Debt ORM instance."""
    payments = [(item.payment_date, item.amount) for item in debt.payments]
    if extra_payment is not None:
        payments.append(extra_payment)
    return calculate_balance(
        interest_type=debt.interest_type,
        rate_period=debt.rate_period,
        base_rate=_to_decimal(debt.interest_rate),
        origin_date=debt.origin_date,
        original_amount=_to_decimal(debt.original_amount),
        payments=payments,
        rate_changes=[(item.effective_date, item.rate) for item in debt.rate_changes],
        as_of=as_of,
    )
