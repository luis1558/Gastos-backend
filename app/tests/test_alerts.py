from datetime import date

from app.modules.alerts.service import _next_month, _severity
from app.modules.fixed_payments.service import due_date_for


def test_severity_follows_days_left():
    assert _severity(-3) == "overdue"
    assert _severity(0) == "today"
    assert _severity(5) == "soon"


def test_next_month_wraps_the_year():
    assert _next_month(2026, 11) == (2026, 12)
    assert _next_month(2026, 12) == (2027, 1)


def test_due_date_is_clamped_in_short_months():
    assert due_date_for(2027, 2, 31) == date(2027, 2, 28)
    assert due_date_for(2028, 2, 31) == date(2028, 2, 29)
    assert due_date_for(2026, 4, 31) == date(2026, 4, 30)
    assert due_date_for(2026, 11, 5) == date(2026, 11, 5)
