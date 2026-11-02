from datetime import date
from decimal import Decimal

from app.modules.debts.interest import calculate_balance, rate_in_effect
from app.shared.constants import InterestType, RatePeriod

ORIGIN = date(2026, 1, 1)
ONE_YEAR_LATER = date(2027, 1, 1)


def balance(interest_type, rate=Decimal("12"), period=RatePeriod.ANNUAL, payments=(), changes=(), as_of=ONE_YEAR_LATER):
    return calculate_balance(
        interest_type=interest_type,
        rate_period=period,
        base_rate=rate,
        origin_date=ORIGIN,
        original_amount=Decimal("1000"),
        payments=payments,
        rate_changes=changes,
        as_of=as_of,
    )


def test_no_interest_keeps_original_amount():
    result = balance(InterestType.NONE)
    assert result.total_owed == Decimal("1000.00")
    assert result.interest_outstanding == Decimal("0.00")


def test_simple_interest_over_one_year():
    assert balance(InterestType.SIMPLE).interest_outstanding == Decimal("120.00")


def test_monthly_rate_is_equivalent_to_twelve_times_annual():
    result = balance(InterestType.SIMPLE, rate=Decimal("1"), period=RatePeriod.MONTHLY)
    assert result.interest_outstanding == Decimal("120.00")


def test_compound_interest_capitalises_monthly():
    assert balance(InterestType.COMPOUND).interest_outstanding == Decimal("126.83")


def test_simple_never_charges_interest_on_interest():
    one = balance(InterestType.SIMPLE, as_of=date(2027, 1, 1)).interest_outstanding
    two = balance(InterestType.SIMPLE, as_of=date(2028, 1, 1)).interest_outstanding
    assert two - one < Decimal("121.00")
    assert two > one * 2 - Decimal("1.00")


def test_variable_rate_is_applied_by_segments():
    changes = [(date(2026, 7, 1), Decimal("24"))]
    result = balance(InterestType.SIMPLE, changes=changes)
    assert result.interest_outstanding == Decimal("180.49")


def test_payment_settles_interest_before_principal():
    payments = [(date(2026, 7, 1), Decimal("500"))]
    result = balance(InterestType.SIMPLE, payments=payments)
    assert result.principal_remaining == Decimal("559.51")


def test_future_events_are_ignored():
    payments = [(date(2030, 1, 1), Decimal("500"))]
    result = balance(InterestType.SIMPLE, payments=payments)
    assert result.principal_remaining == Decimal("1000.00")


def test_rate_in_effect_picks_latest_applicable_change():
    changes = [(date(2026, 3, 1), Decimal("10")), (date(2026, 9, 1), Decimal("15"))]
    assert rate_in_effect(Decimal("8"), changes, date(2026, 2, 1)) == Decimal("8")
    assert rate_in_effect(Decimal("8"), changes, date(2026, 5, 1)) == Decimal("10")
    assert rate_in_effect(Decimal("8"), changes, date(2026, 12, 1)) == Decimal("15")
