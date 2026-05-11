from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.debts.models import Counterparty, Debt, DebtPayment
from app.modules.debts.repository import DebtRepository
from app.modules.debts.schemas import (
    CounterpartyResponse,
    DebtPaymentResponse,
    DebtResponse,
    DebtSummaryResponse,
)
from app.modules.users.models import User
from app.shared.constants import DebtStatus, DebtType

ZERO = Decimal("0.00")


class DebtService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DebtRepository(db)

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
    ) -> DebtResponse:
        counterparty = self._require_counterparty(current_user.id, counterparty_id)
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
    ) -> DebtResponse:
        debt = self._require_debt(current_user.id, debt_id)
        paid_amount = self._paid_amount(debt)

        if counterparty_id is not None:
            counterparty = self._require_counterparty(current_user.id, counterparty_id)
            debt.counterparty_id = counterparty.id
        if due_date is not None:
            debt.due_date = due_date
        if original_amount is not None:
            if original_amount < paid_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Original amount cannot be less than the amount already paid.",
                )
            debt.original_amount = original_amount
        if description is not None:
            debt.description = description.strip()
        debt.notes = notes

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
    ) -> DebtPaymentResponse:
        debt = self._require_debt(current_user.id, debt_id)
        if debt.status == DebtStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot register a payment on a cancelled debt.",
            )

        remaining_amount = self._remaining_amount(debt)
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

        debt.payments.append(payment)
        self._recalculate_debt_status(debt)
        self.repository.save_debt(debt)
        self.db.commit()
        self.db.refresh(payment)
        return DebtPaymentResponse.model_validate(payment)

    def list_payments(self, current_user: User, debt_id: str) -> list[DebtPaymentResponse]:
        debt = self._require_debt(current_user.id, debt_id)
        payments = self.repository.list_payments(current_user.id, debt.id)
        return [DebtPaymentResponse.model_validate(payment) for payment in payments]

    def get_summary(self, current_user: User) -> DebtSummaryResponse:
        remaining_by_type = dict(self.repository.aggregate_remaining_by_type(current_user.id))
        today = date.today()
        return DebtSummaryResponse(
            total_receivable_pending=self._as_decimal(remaining_by_type.get(DebtType.RECEIVABLE, ZERO)),
            total_payable_pending=self._as_decimal(remaining_by_type.get(DebtType.PAYABLE, ZERO)),
            overdue_receivable_count=self.repository.count_overdue(current_user.id, DebtType.RECEIVABLE, today),
            overdue_payable_count=self.repository.count_overdue(current_user.id, DebtType.PAYABLE, today),
            active_debt_count=self.repository.count_active_debts(current_user.id),
        )

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

    def _remaining_amount(self, debt: Debt) -> Decimal:
        return self._as_decimal(debt.original_amount) - self._paid_amount(debt)

    def _recalculate_debt_status(self, debt: Debt) -> None:
        paid_amount = self._paid_amount(debt)
        original_amount = self._as_decimal(debt.original_amount)

        if debt.status == DebtStatus.CANCELLED:
            return
        if paid_amount == ZERO:
            debt.status = DebtStatus.PENDING
            debt.closed_at = None
            return
        if paid_amount >= original_amount:
            debt.status = DebtStatus.PAID
            debt.closed_at = datetime.now(timezone.utc)
            return
        debt.status = DebtStatus.PARTIALLY_PAID
        debt.closed_at = None

    def _to_debt_response(self, debt: Debt) -> DebtResponse:
        paid_amount = self._paid_amount(debt)
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
            remaining_amount=self._as_decimal(debt.original_amount) - paid_amount,
            description=debt.description,
            notes=debt.notes,
            created_at=debt.created_at,
            updated_at=debt.updated_at,
            closed_at=debt.closed_at,
        )

    @staticmethod
    def _as_decimal(value) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value)).quantize(Decimal("0.01"))
