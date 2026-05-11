from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.income.models import MonthlyIncomeConfig


class MonthlyIncomeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_year_month(
        self,
        user_id: str,
        year: int,
        month: int,
    ) -> Optional[MonthlyIncomeConfig]:
        stmt: Select[tuple[MonthlyIncomeConfig]] = select(MonthlyIncomeConfig).where(
            MonthlyIncomeConfig.user_id == user_id,
            MonthlyIncomeConfig.year == year,
            MonthlyIncomeConfig.month == month,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_year(self, user_id: str, year: int) -> list[MonthlyIncomeConfig]:
        stmt: Select[tuple[MonthlyIncomeConfig]] = (
            select(MonthlyIncomeConfig)
            .where(
                MonthlyIncomeConfig.user_id == user_id,
                MonthlyIncomeConfig.year == year,
            )
            .order_by(MonthlyIncomeConfig.month.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def save(self, income: MonthlyIncomeConfig) -> MonthlyIncomeConfig:
        self.db.add(income)
        self.db.flush()
        return income
