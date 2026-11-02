from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.modules.fixed_payments.models import FixedPayment, FixedPaymentPayment


class FixedPaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_fixed_payments(self, user_id: str) -> list[FixedPayment]:
        stmt = (
            select(FixedPayment)
            .options(joinedload(FixedPayment.category), joinedload(FixedPayment.payments))
            .where(FixedPayment.user_id == user_id)
            .order_by(FixedPayment.day_of_month.asc(), FixedPayment.name.asc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def get_fixed_payment(self, user_id: str, fixed_payment_id: str) -> Optional[FixedPayment]:
        stmt: Select[tuple[FixedPayment]] = (
            select(FixedPayment)
            .options(joinedload(FixedPayment.category), joinedload(FixedPayment.payments))
            .where(FixedPayment.user_id == user_id, FixedPayment.id == fixed_payment_id)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_period_payment(
        self, fixed_payment_id: str, year: int, month: int
    ) -> Optional[FixedPaymentPayment]:
        stmt = select(FixedPaymentPayment).where(
            FixedPaymentPayment.fixed_payment_id == fixed_payment_id,
            FixedPaymentPayment.year == year,
            FixedPaymentPayment.month == month,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def save_fixed_payment(self, fixed_payment: FixedPayment) -> FixedPayment:
        self.db.add(fixed_payment)
        self.db.flush()
        return fixed_payment

    def delete_fixed_payment(self, fixed_payment: FixedPayment) -> None:
        self.db.delete(fixed_payment)
        self.db.flush()

    def save_period_payment(self, payment: FixedPaymentPayment) -> FixedPaymentPayment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def delete_period_payment(self, payment: FixedPaymentPayment) -> None:
        self.db.delete(payment)
        self.db.flush()
