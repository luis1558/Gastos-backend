from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.debts.repository import DebtRepository
from app.modules.goals.models import Goal, GoalContribution
from app.modules.goals.repository import GoalRepository
from app.modules.goals.schemas import (
    ContributionResponse,
    GoalOverviewResponse,
    GoalResponse,
)
from app.modules.users.models import User
from app.shared.constants import DebtStatus, DebtType, GoalKind, GoalStatus

ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")
# Kinds that need their own module (cards, fixed payments) before they can be created.
UNAVAILABLE_KINDS = {GoalKind.CARD, GoalKind.FIXED_PAYMENT}
EDITABLE_FIELDS = {"name", "target_amount", "target_date", "notes"}


def _dec(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class GoalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = GoalRepository(db)
        self.debt_repository = DebtRepository(db)

    # ---- overview -------------------------------------------------------

    def get_overview(self, current_user: User) -> GoalOverviewResponse:
        user = self._load_user(current_user)
        opening = _dec(user.opening_balance)
        income = self.repository.total_income(user.id)
        expenses = self.repository.total_expenses(user.id)
        reserved = self.repository.reserved_total(user.id)
        balance = opening + income - expenses
        return GoalOverviewResponse(
            opening_balance=opening,
            total_income=income,
            total_expenses=expenses,
            balance=balance,
            reserved=reserved,
            available=balance - reserved,
        )

    def set_opening_balance(self, current_user: User, opening_balance: Decimal) -> GoalOverviewResponse:
        user = self._load_user(current_user)
        user.opening_balance = opening_balance
        self.db.commit()
        return self.get_overview(current_user)

    # ---- goals ----------------------------------------------------------

    def list_goals(self, current_user: User, status_filter: Optional[GoalStatus]) -> list[GoalResponse]:
        goals = self.repository.list_goals(current_user.id, status_filter)
        return [self._to_response(goal) for goal in goals]

    def get_goal(self, current_user: User, goal_id: str) -> GoalResponse:
        return self._to_response(self._require_goal(current_user.id, goal_id))

    def create_goal(
        self,
        current_user: User,
        kind: GoalKind,
        name: str,
        target_amount: Decimal,
        target_date: Optional[date],
        notes: Optional[str],
        debt_id: Optional[str],
    ) -> GoalResponse:
        if kind in UNAVAILABLE_KINDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This kind of goal is not available yet.",
            )
        if kind == GoalKind.DEBT:
            debt_id = self._validate_debt(current_user.id, debt_id)
        elif debt_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only debt goals can be linked to a debt.",
            )

        goal = Goal(
            user_id=current_user.id,
            kind=kind,
            status=GoalStatus.ACTIVE,
            name=name.strip(),
            target_amount=target_amount,
            target_date=target_date,
            notes=notes,
            debt_id=debt_id,
        )
        self.repository.save_goal(goal)
        self.db.commit()
        return self._to_response(self._require_goal(current_user.id, goal.id))

    def update_goal(self, current_user: User, goal_id: str, changes: dict[str, Any]) -> GoalResponse:
        goal = self._require_goal(current_user.id, goal_id)
        for field, value in changes.items():
            if field not in EDITABLE_FIELDS:
                continue
            if value is None and field in {"name", "target_amount"}:
                continue
            setattr(goal, field, value.strip() if field == "name" else value)
        self.repository.save_goal(goal)
        self.db.commit()
        return self._to_response(self._require_goal(current_user.id, goal_id))

    def complete_goal(self, current_user: User, goal_id: str) -> GoalResponse:
        """Mark the goal as done. Its reserved money becomes available again."""
        goal = self._require_goal(current_user.id, goal_id)
        if goal.status != GoalStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The goal is already completed.",
            )
        goal.status = GoalStatus.COMPLETED
        goal.closed_at = datetime.now(timezone.utc)
        self.repository.save_goal(goal)
        self.db.commit()
        return self._to_response(self._require_goal(current_user.id, goal_id))

    def delete_goal(self, current_user: User, goal_id: str) -> None:
        goal = self._require_goal(current_user.id, goal_id)
        self.repository.delete_goal(goal)
        self.db.commit()

    # ---- contributions --------------------------------------------------

    def list_contributions(self, current_user: User, goal_id: str) -> list[ContributionResponse]:
        goal = self._require_goal(current_user.id, goal_id)
        items = self.repository.list_contributions(current_user.id, goal.id)
        return [ContributionResponse.model_validate(item) for item in items]

    def add_contribution(
        self,
        current_user: User,
        goal_id: str,
        direction: str,
        amount: Decimal,
        contribution_date: date,
        notes: Optional[str],
    ) -> ContributionResponse:
        goal = self._require_goal(current_user.id, goal_id)
        if goal.status != GoalStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move money in a completed goal.",
            )

        saved = self._saved_amount(goal)
        if direction == "deposit":
            available = self.get_overview(current_user).available
            if amount > available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Amount exceeds your available balance.",
                )
            if saved + amount > _dec(goal.target_amount):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Amount exceeds what the goal still needs.",
                )
            signed = amount
        else:
            if amount > saved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Amount exceeds what is saved in the goal.",
                )
            signed = -amount

        contribution = GoalContribution(
            user_id=current_user.id,
            goal_id=goal.id,
            contribution_date=contribution_date,
            amount=signed,
            notes=notes,
        )
        self.repository.save_contribution(contribution)
        self.db.commit()
        self.db.refresh(contribution)
        return ContributionResponse.model_validate(contribution)

    # ---- helpers --------------------------------------------------------

    def _load_user(self, current_user: User) -> User:
        user = self.db.get(User, current_user.id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    def _require_goal(self, user_id: str, goal_id: str) -> Goal:
        goal = self.repository.get_goal(user_id, goal_id)
        if goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
        return goal

    def _validate_debt(self, user_id: str, debt_id: Optional[str]) -> str:
        if not debt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A debt goal needs a debt.",
            )
        debt = self.debt_repository.get_debt(user_id, debt_id)
        if debt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found.")
        if debt.type != DebtType.PAYABLE or debt.status not in (DebtStatus.PENDING, DebtStatus.PARTIALLY_PAID):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending debts you owe can be saved for.",
            )
        if self.repository.get_active_goal_for_debt(user_id, debt.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="There is already an active goal for this debt.",
            )
        return debt.id

    @staticmethod
    def _saved_amount(goal: Goal) -> Decimal:
        return sum((_dec(item.amount) for item in goal.contributions), ZERO)

    def _to_response(self, goal: Goal) -> GoalResponse:
        saved = self._saved_amount(goal)
        target = _dec(goal.target_amount)
        progress = min(HUNDRED, saved / target * HUNDRED) if target > 0 else ZERO
        debt_label: Optional[str] = None
        if goal.debt is not None:
            debt_label = f"{goal.debt.description} · {goal.debt.counterparty.name}"
        return GoalResponse(
            id=goal.id,
            kind=goal.kind,
            status=goal.status,
            name=goal.name,
            target_amount=target,
            target_date=goal.target_date,
            notes=goal.notes,
            debt_id=goal.debt_id,
            debt_label=debt_label,
            saved_amount=saved,
            remaining_amount=max(ZERO, target - saved),
            progress_percent=progress.quantize(CENT),
            created_at=goal.created_at,
            closed_at=goal.closed_at,
        )
