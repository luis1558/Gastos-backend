from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401  (registers every table)
from app.db.base import Base
from app.modules.cards.models import Card, CardStatement
from app.modules.debts.models import Counterparty, Debt, DebtPayment
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.fixed_payments.models import FixedPayment, FixedPaymentPayment
from app.modules.income.models import MonthlyIncomeConfig
from app.modules.reports.service import ReportService
from app.modules.users.models import User
from app.shared.constants import DebtType, PaymentMethod

D = Decimal


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(email="u@example.com", password_hash="x")
    db.add(u)
    db.flush()
    return u


def _category(db, user, name):
    c = ExpenseCategory(user_id=user.id, name=name, slug=name.lower())
    db.add(c)
    db.flush()
    return c


def _expense(db, user, category, day, amount, description="gasto", **extra):
    e = Expense(
        user_id=user.id,
        category_id=category.id,
        expense_date=day,
        year=day.year,
        month=day.month,
        amount=D(str(amount)),
        description=description,
        **extra,
    )
    db.add(e)
    db.flush()
    return e


def _fixed_payment(db, user, category, name, amount, day_of_month=2):
    fp = FixedPayment(user_id=user.id, category_id=category.id, name=name, amount=D(str(amount)), day_of_month=day_of_month)
    db.add(fp)
    db.flush()
    return fp


def _pay_fixed(db, user, fp, day, amount):
    e = _expense(db, user, fp.category, day, amount, description=fp.name)
    db.add(
        FixedPaymentPayment(
            user_id=user.id, fixed_payment_id=fp.id, year=day.year, month=day.month,
            amount=D(str(amount)), paid_on=day, expense_id=e.id,
        )
    )
    db.flush()
    return e


def _pay_card(db, user, category, card, day, amount):
    e = _expense(db, user, category, day, amount, description=f"Pago tarjeta {card.name}")
    db.add(
        CardStatement(
            user_id=user.id, card_id=card.id, year=day.year, month=day.month,
            amount=D(str(amount)), paid_on=day, expense_id=e.id,
        )
    )
    db.flush()
    return e


def _pay_debt(db, user, category, day, amount, description=None):
    cp = Counterparty(user_id=user.id, name="Banco")
    db.add(cp)
    db.flush()
    debt = Debt(
        user_id=user.id, counterparty_id=cp.id, type=DebtType.PAYABLE, origin_date=date(2026, 1, 1),
        original_amount=D("5000"), description="Prestamo",
    )
    db.add(debt)
    db.flush()
    db.add(DebtPayment(user_id=user.id, debt_id=debt.id, payment_date=day, amount=D(str(amount)), description=description))
    db.flush()
    return _expense(db, user, category, day, amount, description=description or "Pago de deuda: Prestamo")


def _card(db, user, name):
    card = Card(user_id=user.id, name=name, payment_day=10)
    db.add(card)
    db.flush()
    return card


def _income(db, user, year, month, base, extra=0):
    db.add(MonthlyIncomeConfig(user_id=user.id, year=year, month=month, base_income=D(str(base)), extra_income=D(str(extra))))
    db.flush()


@pytest.fixture()
def may_data(db, user):
    """May 2026: 100 variable, rent 1000 paid, card 200 paid, debt 300 paid, internet 50 pending."""
    food = _category(db, user, "Comida")
    home = _category(db, user, "Hogar")
    _expense(db, user, food, date(2026, 5, 5), 100)
    rent = _fixed_payment(db, user, home, "Alquiler", 1000)
    _pay_fixed(db, user, rent, date(2026, 5, 2), 1000)
    _fixed_payment(db, user, home, "Internet", 50)
    _pay_card(db, user, home, _card(db, user, "Visa"), date(2026, 5, 3), 200)
    _pay_debt(db, user, home, date(2026, 5, 4), 300)
    _income(db, user, 2026, 5, 2000)
    return {"food": food, "home": home}


# --- S2 / S3: month forecast -------------------------------------------------


def test_forecast_projects_only_variable_spending_and_adds_committed(db, user, may_data):
    r = ReportService(db).get_month_forecast(user, 2026, 5, today=date(2026, 5, 10))
    assert r.period_state == "current"
    assert r.days_in_month == 31
    assert r.days_elapsed == 10
    assert r.total_spent == D("1600")
    assert r.variable_spent == D("100")
    assert r.committed_spent == D("1500")
    assert r.pending_fixed_payments == D("50")
    assert r.daily_rate == D("10")
    # 10/day * 31 days + 1500 committed + 50 pending
    assert r.projected_expenses == D("1860")
    assert r.total_income == D("2000")
    assert r.projected_balance == D("140")


def test_forecast_debt_payment_with_custom_description_is_committed(db, user):
    cat = _category(db, user, "Varios")
    _pay_debt(db, user, cat, date(2026, 5, 4), 300, description="Cuota mayo")
    r = ReportService(db).get_month_forecast(user, 2026, 5, today=date(2026, 5, 10))
    assert r.committed_spent == D("300")
    assert r.variable_spent == D("0")
    assert r.projected_expenses == D("300")


def test_forecast_past_month_reports_closed_real_totals(db, user, may_data):
    r = ReportService(db).get_month_forecast(user, 2026, 5, today=date(2026, 6, 15))
    assert r.period_state == "past"
    assert r.days_elapsed == 31
    assert r.total_spent == D("1600")
    assert r.pending_fixed_payments == D("0")
    assert r.projected_expenses == D("1600")
    assert r.projected_balance == D("400")


def test_forecast_future_month_has_no_elapsed_days(db, user, may_data):
    r = ReportService(db).get_month_forecast(user, 2026, 6, today=date(2026, 5, 10))
    assert r.period_state == "future"
    assert r.days_in_month == 30
    assert r.days_elapsed == 0
    assert r.total_spent == D("0")
    assert r.daily_rate == D("0")
    assert r.pace_pct is None
    # Nothing is paid yet in June: both active fixed payments are still pending.
    assert r.pending_fixed_payments == D("1050")
    assert r.projected_expenses == D("1050")


def test_forecast_inactive_fixed_payment_is_not_pending(db, user):
    home = _category(db, user, "Hogar")
    fp = _fixed_payment(db, user, home, "Gym", 40)
    fp.is_active = False
    db.flush()
    r = ReportService(db).get_month_forecast(user, 2026, 5, today=date(2026, 5, 10))
    assert r.pending_fixed_payments == D("0")


# --- S4: recurring expenses --------------------------------------------------


def test_recurring_excludes_fixed_card_and_debt_payments(db, user):
    food = _category(db, user, "Suscripciones")
    home = _category(db, user, "Hogar")
    rent = _fixed_payment(db, user, home, "Alquiler", 1000)
    card = _card(db, user, "Visa")
    for m in (3, 4, 5):
        _expense(db, user, food, date(2026, m, 6), 15, description="Netflix")
        _pay_fixed(db, user, rent, date(2026, m, 2), 1000)
        _pay_card(db, user, home, card, date(2026, m, 3), 200)
        _pay_debt(db, user, home, date(2026, m, 4), 300)
    r = ReportService(db).get_recurring_expenses(user, today=date(2026, 5, 20))
    assert r.checked_months == 4
    assert [i.description for i in r.items] == ["Netflix"]
    assert r.items[0].occurrence_months == 3


# --- S5: yearly savings rate -------------------------------------------------


def test_yearly_savings_rate_is_weighted(db, user):
    cat = _category(db, user, "Comida")
    _income(db, user, 2026, 1, 1000)
    _income(db, user, 2026, 2, 3000)
    _expense(db, user, cat, date(2026, 1, 5), 500)
    _expense(db, user, cat, date(2026, 2, 5), 2900)
    r = ReportService(db).get_yearly_summary(user, 2026)
    assert r.balance == D("600")
    assert r.savings_rate == D("15.0")


def test_yearly_savings_rate_none_without_income(db, user):
    assert ReportService(db).get_yearly_summary(user, 2026).savings_rate is None


# --- S13: category trend -----------------------------------------------------


def test_category_trend_top5_with_monthly_amounts(db, user):
    totals = {"A": 600, "B": 500, "C": 400, "D": 300, "E": 200, "F": 100}
    cats = {name: _category(db, user, name) for name in totals}
    for name, amount in totals.items():
        _expense(db, user, cats[name], date(2026, 1, 10), amount)
    _expense(db, user, cats["F"], date(2025, 3, 1), 9999)  # other year
    _expense(db, user, cats["A"], date(2026, 12, 1), 50)
    other = User(email="o@example.com", password_hash="x")
    db.add(other)
    db.flush()
    _expense(db, other, _category(db, other, "Z"), date(2026, 1, 1), 99999)

    r = ReportService(db).get_category_trend(user, 2026)
    assert r.year == 2026
    assert [c.category_name for c in r.categories] == ["A", "B", "C", "D", "E"]
    a = r.categories[0]
    assert a.category_id == cats["A"].id
    assert len(a.monthly) == 12
    assert a.monthly[0] == D("600")
    assert a.monthly[11] == D("50")
    assert all(v == D("0") for v in a.monthly[1:11])


def test_category_trend_empty_year(db, user):
    r = ReportService(db).get_category_trend(user, 2026)
    assert r.model_dump() == {"year": 2026, "categories": []}


# --- S14: spending breakdown -------------------------------------------------


def test_spending_breakdown_by_method_and_card(db, user):
    cat = _category(db, user, "Comida")
    visa = _card(db, user, "Visa")
    master = _card(db, user, "Master")
    _expense(db, user, cat, date(2026, 5, 1), 10, payment_method=PaymentMethod.CASH)
    _expense(db, user, cat, date(2026, 5, 2), 15, payment_method=PaymentMethod.CASH)
    _expense(db, user, cat, date(2026, 5, 3), 100, payment_method=PaymentMethod.CREDIT_CARD, card_id=visa.id)
    _expense(db, user, cat, date(2026, 5, 4), 40, payment_method=PaymentMethod.CREDIT_CARD, card_id=master.id)
    _expense(db, user, cat, date(2026, 5, 5), 30, card_id=master.id)
    _expense(db, user, cat, date(2026, 5, 6), 7)
    _expense(db, user, cat, date(2026, 4, 6), 999, payment_method=PaymentMethod.CASH, card_id=visa.id)

    r = ReportService(db).get_spending_breakdown(user, 2026, 5).model_dump(mode="json")
    assert r["by_payment_method"] == [
        {"payment_method": "credit_card", "amount": "140.00", "count": 2},
        {"payment_method": None, "amount": "37.00", "count": 2},
        {"payment_method": "cash", "amount": "25.00", "count": 2},
    ]
    assert r["by_card"] == [
        {"card_id": visa.id, "card_name": "Visa", "amount": "100.00", "count": 1},
        {"card_id": master.id, "card_name": "Master", "amount": "70.00", "count": 2},
    ]


# --- HTTP wiring -------------------------------------------------------------


def test_report_endpoints_expose_contracts(db, user, may_data):
    from app.db.session import get_db
    from app.modules.auth.dependencies import get_current_user
    from app.modules.reports.router import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)

    trend = client.get("/reports/category-trend", params={"year": 2026})
    assert trend.status_code == 200
    body = trend.json()
    assert set(body) == {"year", "categories"}
    assert set(body["categories"][0]) == {"category_id", "category_name", "monthly"}
    assert len(body["categories"][0]["monthly"]) == 12

    breakdown = client.get("/reports/spending-breakdown", params={"year": 2026, "month": 5})
    assert breakdown.status_code == 200
    assert set(breakdown.json()) == {"by_payment_method", "by_card"}

    forecast = client.get("/reports/month-forecast", params={"year": 2026, "month": 5})
    assert forecast.status_code == 200
    assert forecast.json()["period_state"] in {"past", "current", "future"}

    assert client.get("/reports/spending-breakdown", params={"year": 2026, "month": 13}).status_code == 422
