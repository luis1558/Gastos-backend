from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.income.models import MonthlyIncomeConfig
from app.modules.income.repository import MonthlyIncomeRepository
from app.modules.income.schemas import MonthlyIncomeResponse
from app.modules.users.models import User


class MonthlyIncomeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = MonthlyIncomeRepository(db)

    def upsert(
        self,
        current_user: User,
        year: int,
        month: int,
        base_income: Decimal,
        extra_income: Decimal,
        notes: Optional[str],
    ) -> MonthlyIncomeResponse:
        income = self.repository.get_by_year_month(current_user.id, year, month)
        if income is None:
            income = MonthlyIncomeConfig(
                user_id=current_user.id,
                year=year,
                month=month,
                base_income=base_income,
                extra_income=extra_income,
                notes=notes,
            )
        else:
            income.base_income = base_income
            income.extra_income = extra_income
            income.notes = notes

        self.repository.save(income)
        self.db.commit()
        self.db.refresh(income)
        return MonthlyIncomeResponse.model_validate(income)

    def get(self, current_user: User, year: int, month: int) -> MonthlyIncomeResponse:
        income = self.repository.get_by_year_month(current_user.id, year, month)
        if income is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Monthly income configuration not found.",
            )
        return MonthlyIncomeResponse.model_validate(income)

    def list_by_year(self, current_user: User, year: int) -> list[MonthlyIncomeResponse]:
        incomes = self.repository.list_by_year(current_user.id, year)
        return [MonthlyIncomeResponse.model_validate(income) for income in incomes]
