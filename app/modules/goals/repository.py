from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.debts.models import Debt
from app.modules.expenses.models import Expense
from app.modules.goals.models import Goal, GoalContribution
from app.modules.income.models import MonthlyIncomeConfig
from app.shared.constants import GoalStatus


class GoalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _goal_query(self) -> Select[tuple[Goal]]:
        return select(Goal).options(
            selectinload(Goal.contributions),
            joinedload(Goal.debt).joinedload(Debt.counterparty),
            joinedload(Goal.fixed_payment),
        )

    def list_goals(self, user_id: str, status: Optional[GoalStatus] = None) -> list[Goal]:
        stmt = self._goal_query().where(Goal.user_id == user_id).order_by(Goal.created_at.desc())
        if status is not None:
            stmt = stmt.where(Goal.status == status)
        return list(self.db.execute(stmt).unique().scalars().all())

    def get_goal(self, user_id: str, goal_id: str) -> Optional[Goal]:
        stmt = self._goal_query().where(Goal.user_id == user_id, Goal.id == goal_id)
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_active_goal_for_debt(self, user_id: str, debt_id: str) -> Optional[Goal]:
        stmt = select(Goal).where(
            Goal.user_id == user_id,
            Goal.debt_id == debt_id,
            Goal.status == GoalStatus.ACTIVE,
        )
        return self.db.execute(stmt).scalars().first()

    def get_active_goal_for_fixed_payment(self, user_id: str, fixed_payment_id: str) -> Optional[Goal]:
        stmt = select(Goal).where(
            Goal.user_id == user_id,
            Goal.fixed_payment_id == fixed_payment_id,
            Goal.status == GoalStatus.ACTIVE,
        )
        return self.db.execute(stmt).scalars().first()

    def save_goal(self, goal: Goal) -> Goal:
        self.db.add(goal)
        self.db.flush()
        return goal

    def delete_goal(self, goal: Goal) -> None:
        self.db.delete(goal)
        self.db.flush()

    def save_contribution(self, contribution: GoalContribution) -> GoalContribution:
        self.db.add(contribution)
        self.db.flush()
        return contribution

    def list_contributions(self, user_id: str, goal_id: str) -> list[GoalContribution]:
        stmt = (
            select(GoalContribution)
            .where(GoalContribution.user_id == user_id, GoalContribution.goal_id == goal_id)
            .order_by(GoalContribution.contribution_date.desc(), GoalContribution.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def reserved_total(self, user_id: str) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(GoalContribution.amount), 0))
            .join(Goal, Goal.id == GoalContribution.goal_id)
            .where(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
        )
        return Decimal(str(self.db.execute(stmt).scalar_one()))

    def total_income(self, user_id: str) -> Decimal:
        stmt = select(
            func.coalesce(func.sum(MonthlyIncomeConfig.base_income + MonthlyIncomeConfig.extra_income), 0)
        ).where(MonthlyIncomeConfig.user_id == user_id)
        return Decimal(str(self.db.execute(stmt).scalar_one()))

    def total_expenses(self, user_id: str) -> Decimal:
        stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user_id)
        return Decimal(str(self.db.execute(stmt).scalar_one()))
