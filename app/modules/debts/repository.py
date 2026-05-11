from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.debts.models import Counterparty, Debt, DebtPayment
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
            .options(joinedload(Debt.counterparty), joinedload(Debt.payments))
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
            .options(joinedload(Debt.counterparty), joinedload(Debt.payments))
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

    def aggregate_remaining_by_type(self, user_id: str) -> list[tuple[DebtType, Optional[float]]]:
        paid_subquery = (
            select(
                DebtPayment.debt_id.label("debt_id"),
                func.coalesce(func.sum(DebtPayment.amount), 0).label("paid_amount"),
            )
            .where(DebtPayment.user_id == user_id)
            .group_by(DebtPayment.debt_id)
            .subquery()
        )

        stmt = (
            select(
                Debt.type,
                func.coalesce(func.sum(Debt.original_amount - func.coalesce(paid_subquery.c.paid_amount, 0)), 0),
            )
            .outerjoin(paid_subquery, Debt.id == paid_subquery.c.debt_id)
            .where(
                Debt.user_id == user_id,
                Debt.status.in_([DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID]),
            )
            .group_by(Debt.type)
        )
        return list(self.db.execute(stmt).all())

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
