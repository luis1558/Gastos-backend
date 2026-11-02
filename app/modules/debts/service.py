from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.debts.interest import balance_for_debt, rate_in_effect
from app.modules.debts.models import Counterparty, Debt, DebtPayment, DebtRateChange
from app.modules.debts.repository import DebtRepository
from app.modules.debts.schemas import (
    CounterpartyResponse,
    DebtPaymentResponse,
    DebtRateChangeResponse,
    DebtResponse,
    DebtSummaryResponse,
)
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.expenses.repository import ExpenseRepository
from app.modules.users.models import User
from app.shared.constants import DebtStatus, DebtType, InterestType, RatePeriod, RateType

ZERO = Decimal("0.00")
BALANCE_TOLERANCE = Decimal("0.005")


class DebtService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DebtRepository(db)
        self.expense_repository = ExpenseRepository(db)

    def create_counterparty(
        self,
        current_user: User,
        name: str,
        counterparty_type,
        phone: Optional[str],
        email: Optional[str],
        notes: Optional[str],
    ) -> CounterpartyResponse:
        normalized_name = name.strip()
        existing = self.repository.get_counterparty_by_name(current_user.id, normalized_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A counterparty with that name already exists.",
            )
        counterparty = Counterparty(
            user_id=current_user.id,
            name=normalized_name,
            type=counterparty_type,
            phone=phone,
            email=email,
            notes=notes,
        )
        self.repository.save_counterparty(counterparty)
        self.db.commit()
        self.db.refresh(counterparty)
        return CounterpartyResponse.model_validate(counterparty)

    def list_counterparties(self, current_user: User) -> list[CounterpartyResponse]:
        counterparties = self.repository.list_counterparties(current_user.id)
        return [CounterpartyResponse.model_validate(item) for item in counterparties]

    def create_debt(
        self,
        current_user: User,
        counterparty_id: str,
        debt_type: DebtType,
        origin_date: date,
        due_date: Optional[date],
        original_amount: Decimal,
        description: str,
        notes: Optional[str],
        interest_type: InterestType = InterestType.NONE,
        rate_type: RateType = RateType.FIXED,
        rate_period: RatePeriod = RatePeriod.ANNUAL,
        interest_rate: Decimal = Decimal("0"),
    ) -> DebtResponse:
        counterparty = self._require_counterparty(current_user.id, counterparty_id)
        self._require_positive_rate(interest_type, interest_rate)
        debt = Debt(
            user_id=current_user.id,
            counterparty_id=counterparty.id,
            type=debt_type,
            status=DebtStatus.PENDING,
            origin_date=origin_date,
            due_date=due_date,
            original_amount=original_amount,
            description=description.strip(),
            notes=notes,
            interest_type=interest_type,
            rate_type=rate_type,
            rate_period=rate_period,
            interest_rate=interest_rate,
        )
        self.repository.save_debt(debt)
        self.db.commit()
        self.db.refresh(debt)
        debt = self.repository.get_debt(current_user.id, debt.id)
        return self._to_debt_response(debt)

    def update_debt(
        self,
        current_user: User,
        debt_id: str,
        counterparty_id: Optional[str],
        due_date: Optional[date],
        original_amount: Optional[Decimal],
        description: Optional[str],
        notes: Optional[str],
        requested_status: Optional[DebtStatus],
        interest_type: Optional[InterestType] = None,
        rate_type: Optional[RateType] = None,
        rate_period: Optional[RatePeriod] = None,
        interest_rate: Optional[Decimal] = None,
    ) -> DebtResponse:
        debt = self._require_debt(current_user.id, debt_id)
        paid_amount = self._paid_amount(debt)

        if counterparty_id is not None:
            counterparty = self._require_counterparty(current_user.id, counterparty_id)
            debt.counterparty_id = counterparty.id
        if due_date is not None:
            debt.due_date = due_date
        if original_amount is not None:
            if debt.interest_type == InterestType.NONE and original_amount < paid_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Original amount cannot be less than the amount already paid.",
                )
            debt.original_amount = original_amount
        if description is not None:
            debt.description = description.strip()
        debt.notes = notes
        self._apply_interest_changes(debt, interest_type, rate_type, rate_period, interest_rate)

        if requested_status == DebtStatus.CANCELLED:
            debt.status = DebtStatus.CANCELLED
            debt.closed_at = datetime.now(timezone.utc)
        else:
            self._recalculate_debt_status(debt)

        self.repository.save_debt(debt)
        self.db.commit()
        self.db.refresh(debt)
        debt = self.repository.get_debt(current_user.id, debt.id)
        return self._to_debt_response(debt)

    def list_debts(
        self,
        current_user: User,
        debt_type: Optional[DebtType],
        status_filter: Optional[DebtStatus],
    ) -> list[DebtResponse]:
        debts = self.repository.list_debts(current_user.id, debt_type, status_filter)
        return [self._to_debt_response(debt) for debt in debts]

    def get_debt(self, current_user: User, debt_id: str) -> DebtResponse:
        debt = self._require_debt(current_user.id, debt_id)
        return self._to_debt_response(debt)

    def create_payment(
        self,
        current_user: User,
        debt_id: str,
        payment_date: date,
        amount: Decimal,
        description: Optional[str],
        notes: Optional[str],
        category_id: Optional[str] = None,
    ) -> DebtPaymentResponse:
        debt = self._require_debt(current_user.id, debt_id)
        if debt.status == DebtStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot register a payment on a cancelled debt.",
            )

        remaining_amount = balance_for_debt(debt, payment_date).total_owed
        if amount > remaining_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount exceeds the remaining balance.",
            )

        payment = DebtPayment(
            user_id=current_user.id,
            debt_id=debt.id,
            payment_date=payment_date,
            amount=amount,
            description=description,
            notes=notes,
        )
        self.repository.save_payment(payment)
        self.db.flush()

        expense_id: Optional[str] = None
        if category_id:
            category = self._require_category(current_user.id, category_id)
            expense = Expense(
                user_id=current_user.id,
                category_id=category.id,
                expense_date=payment_date,
                year=payment_date.year,
                month=payment_date.month,
                amount=amount,
                description=description or f"Pago de deuda: {debt.description}",
                notes=notes,
            )
            self.expense_repository.save_expense(expense)
            expense_id = expense.id

        debt.payments.append(payment)
        self._recalculate_debt_status(debt)
        self.repository.save_debt(debt)
        self.db.commit()
        self.db.refresh(payment)
        response = DebtPaymentResponse.model_validate(payment)
        response.expense_id = expense_id
        return response

    def list_payments(self, current_user: User, debt_id: str) -> list[DebtPaymentResponse]:
        debt = self._require_debt(current_user.id, debt_id)
        payments = self.repository.list_payments(current_user.id, debt.id)
        return [DebtPaymentResponse.model_validate(payment) for payment in payments]

    def get_summary(self, current_user: User) -> DebtSummaryResponse:
        today = date.today()
        active_statuses = (DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID)
        totals = {DebtType.RECEIVABLE: ZERO, DebtType.PAYABLE: ZERO}
        for debt in self.repository.list_debts(current_user.id):
            if debt.status in active_statuses:
                totals[debt.type] += balance_for_debt(debt, today).total_owed
        return DebtSummaryResponse(
            total_receivable_pending=totals[DebtType.RECEIVABLE],
            total_payable_pending=totals[DebtType.PAYABLE],
            overdue_receivable_count=self.repository.count_overdue(current_user.id, DebtType.RECEIVABLE, today),
            overdue_payable_count=self.repository.count_overdue(current_user.id, DebtType.PAYABLE, today),
            active_debt_count=self.repository.count_active_debts(current_user.id),
        )

    def list_rate_changes(self, current_user: User, debt_id: str) -> list[DebtRateChangeResponse]:
        debt = self._require_debt(current_user.id, debt_id)
        return [DebtRateChangeResponse.model_validate(item) for item in debt.rate_changes]

    def create_rate_change(
        self,
        current_user: User,
        debt_id: str,
        effective_date: date,
        rate: Decimal,
        notes: Optional[str],
    ) -> DebtRateChangeResponse:
        debt = self._require_debt(current_user.id, debt_id)
        if debt.interest_type == InterestType.NONE or debt.rate_type != RateType.VARIABLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rate changes are only allowed on variable-rate debts.",
            )
        if effective_date < debt.origin_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Effective date cannot be before the debt origin date.",
            )
        if self.repository.get_rate_change_by_date(debt.id, effective_date):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A rate change already exists for that date.",
            )
        rate_change = DebtRateChange(
            user_id=current_user.id,
            debt_id=debt.id,
            effective_date=effective_date,
            rate=rate,
            notes=notes,
        )
        self.repository.save_rate_change(rate_change)
        self.db.commit()
        self.db.refresh(rate_change)
        return DebtRateChangeResponse.model_validate(rate_change)

    def delete_rate_change(self, current_user: User, debt_id: str, rate_change_id: str) -> None:
        debt = self._require_debt(current_user.id, debt_id)
        rate_change = self.repository.get_rate_change(debt.id, rate_change_id)
        if rate_change is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rate change not found.",
            )
        self.repository.delete_rate_change(rate_change)
        self.db.commit()

    @staticmethod
    def _require_positive_rate(interest_type: InterestType, interest_rate: Decimal) -> None:
        if interest_type != InterestType.NONE and interest_rate <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interest rate must be greater than zero when the debt has interest.",
            )

    @staticmethod
    def _apply_interest_changes(
        debt: Debt,
        interest_type: Optional[InterestType],
        rate_type: Optional[RateType],
        rate_period: Optional[RatePeriod],
        interest_rate: Optional[Decimal],
    ) -> None:
        if interest_type is not None:
            debt.interest_type = interest_type
        if rate_type is not None:
            debt.rate_type = rate_type
        if rate_period is not None:
            debt.rate_period = rate_period
        if interest_rate is not None:
            debt.interest_rate = interest_rate

        if debt.interest_type == InterestType.NONE:
            debt.rate_type = RateType.FIXED
            debt.interest_rate = Decimal("0")
        else:
            DebtService._require_positive_rate(debt.interest_type, Decimal(str(debt.interest_rate)))
        if debt.rate_type == RateType.FIXED:
            debt.rate_changes.clear()

    def _require_category(self, user_id: str, category_id: str) -> ExpenseCategory:
        category = self.expense_repository.get_category_by_id(user_id, category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense category not found.",
            )
        return category

    def _require_counterparty(self, user_id: str, counterparty_id: str) -> Counterparty:
        counterparty = self.repository.get_counterparty_by_id(user_id, counterparty_id)
        if counterparty is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Counterparty not found.",
            )
        return counterparty

    def _require_debt(self, user_id: str, debt_id: str) -> Debt:
        debt = self.repository.get_debt(user_id, debt_id)
        if debt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Debt not found.",
            )
        return debt

    def _paid_amount(self, debt: Debt) -> Decimal:
        total = ZERO
        for payment in debt.payments:
            total += self._as_decimal(payment.amount)
        return total

    def _recalculate_debt_status(self, debt: Debt) -> None:
        paid_amount = self._paid_amount(debt)

        if debt.status == DebtStatus.CANCELLED:
            return
        if paid_amount == ZERO:
            debt.status = DebtStatus.PENDING
            debt.closed_at = None
            return
        last_payment_date = max(payment.payment_date for payment in debt.payments)
        owed = balance_for_debt(debt, max(date.today(), last_payment_date)).total_owed
        if owed <= BALANCE_TOLERANCE:
            debt.status = DebtStatus.PAID
            debt.closed_at = datetime.now(timezone.utc)
            return
        debt.status = DebtStatus.PARTIALLY_PAID
        debt.closed_at = None

    def _to_debt_response(self, debt: Debt) -> DebtResponse:
        paid_amount = self._paid_amount(debt)
        today = date.today()
        balance = balance_for_debt(debt, today)
        base_rate = self._as_decimal_rate(debt.interest_rate)
        rate_changes = [(item.effective_date, item.rate) for item in debt.rate_changes]
        projected_total_at_due: Optional[Decimal] = None
        if debt.due_date and debt.interest_type != InterestType.NONE:
            projected_total_at_due = balance_for_debt(debt, max(debt.due_date, today)).total_owed
        return DebtResponse(
            id=debt.id,
            counterparty_id=debt.counterparty_id,
            counterparty_name=debt.counterparty.name,
            type=debt.type,
            status=debt.status,
            origin_date=debt.origin_date,
            due_date=debt.due_date,
            original_amount=self._as_decimal(debt.original_amount),
            paid_amount=paid_amount,
            remaining_amount=balance.total_owed,
            principal_remaining=balance.principal_remaining,
            accrued_interest=balance.interest_outstanding,
            total_interest=balance.interest_accrued_total,
            interest_type=debt.interest_type,
            rate_type=debt.rate_type,
            rate_period=debt.rate_period,
            interest_rate=base_rate,
            current_rate=rate_in_effect(base_rate, rate_changes, today),
            projected_total_at_due=projected_total_at_due,
            description=debt.description,
            notes=debt.notes,
            created_at=debt.created_at,
            updated_at=debt.updated_at,
            closed_at=debt.closed_at,
        )

    @staticmethod
    def _as_decimal_rate(value) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @staticmethod
    def _as_decimal(value) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value)).quantize(Decimal("0.01"))
