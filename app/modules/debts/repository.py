from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.debts.models import Counterparty, Debt, DebtPayment, DebtRateChange
from app.shared.constants import DebtStatus, DebtType


class DebtRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_counterparty_by_name(self, user_id: str, name: str) -> Optional[Counterparty]:
        stmt: Select[tuple[Counterparty]] = select(Counterparty).where(
            Counterparty.user_id == user_id,
            Counterparty.name == name,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_counterparty_by_id(self, user_id: str, counterparty_id: str) -> Optional[Counterparty]:
        stmt: Select[tuple[Counterparty]] = select(Counterparty).where(
            Counterparty.user_id == user_id,
            Counterparty.id == counterparty_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_counterparties(self, user_id: str) -> list[Counterparty]:
        stmt = (
            select(Counterparty)
            .where(Counterparty.user_id == user_id)
            .order_by(Counterparty.name.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        self.db.add(counterparty)
        self.db.flush()
        return counterparty

    def get_debt(self, user_id: str, debt_id: str) -> Optional[Debt]:
        stmt: Select[tuple[Debt]] = (
            select(Debt)
            .options(
                    joinedload(Debt.counterparty),
                    joinedload(Debt.payments),
                    selectinload(Debt.rate_changes),
                )
            .where(Debt.user_id == user_id, Debt.id == debt_id)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def list_debts(
        self,
        user_id: str,
        debt_type: Optional[DebtType] = None,
        status: Optional[DebtStatus] = None,
    ) -> list[Debt]:
        stmt = (
            select(Debt)
            .options(
                    joinedload(Debt.counterparty),
                    joinedload(Debt.payments),
                    selectinload(Debt.rate_changes),
                )
            .where(Debt.user_id == user_id)
            .order_by(Debt.origin_date.desc(), Debt.created_at.desc())
        )
        if debt_type is not None:
            stmt = stmt.where(Debt.type == debt_type)
        if status is not None:
            stmt = stmt.where(Debt.status == status)
        return list(self.db.execute(stmt).unique().scalars().all())

    def save_debt(self, debt: Debt) -> Debt:
        self.db.add(debt)
        self.db.flush()
        return debt

    def list_payments(self, user_id: str, debt_id: str) -> list[DebtPayment]:
        stmt = (
            select(DebtPayment)
            .where(DebtPayment.user_id == user_id, DebtPayment.debt_id == debt_id)
            .order_by(DebtPayment.payment_date.desc(), DebtPayment.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def save_payment(self, payment: DebtPayment) -> DebtPayment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def get_rate_change(self, debt_id: str, rate_change_id: str) -> Optional[DebtRateChange]:
        stmt: Select[tuple[DebtRateChange]] = select(DebtRateChange).where(
            DebtRateChange.debt_id == debt_id,
            DebtRateChange.id == rate_change_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_rate_change_by_date(self, debt_id: str, effective_date) -> Optional[DebtRateChange]:
        stmt: Select[tuple[DebtRateChange]] = select(DebtRateChange).where(
            DebtRateChange.debt_id == debt_id,
            DebtRateChange.effective_date == effective_date,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def save_rate_change(self, rate_change: DebtRateChange) -> DebtRateChange:
        self.db.add(rate_change)
        self.db.flush()
        return rate_change

    def delete_rate_change(self, rate_change: DebtRateChange) -> None:
        self.db.delete(rate_change)
        self.db.flush()

    def count_overdue(self, user_id: str, debt_type: DebtType, today) -> int:
        stmt = select(func.count(Debt.id)).where(
            Debt.user_id == user_id,
            Debt.type == debt_type,
            Debt.due_date.is_not(None),
            Debt.due_date < today,
            Debt.status.in_([DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID]),
        )
        return int(self.db.execute(stmt).scalar_one())

    def count_active_debts(self, user_id: str) -> int:
        stmt = select(func.count(Debt.id)).where(
            Debt.user_id == user_id,
            Debt.status.in_([DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID]),
        )
        return int(self.db.execute(stmt).scalar_one())
