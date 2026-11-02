from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.goals.schemas import (
    ContributionCreateRequest,
    ContributionResponse,
    GoalCreateRequest,
    GoalOverviewResponse,
    GoalResponse,
    GoalUpdateRequest,
    OpeningBalanceRequest,
)
from app.modules.goals.service import GoalService
from app.modules.users.models import User
from app.shared.constants import GoalStatus

router = APIRouter(tags=["goals"])


def get_goal_service(db: Session = Depends(get_db)) -> GoalService:
    return GoalService(db)


@router.get("/goals/overview", response_model=GoalOverviewResponse)
def get_overview(
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> GoalOverviewResponse:
    return service.get_overview(current_user)


@router.put("/goals/opening-balance", response_model=GoalOverviewResponse)
def set_opening_balance(
    payload: OpeningBalanceRequest,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> GoalOverviewResponse:
    return service.set_opening_balance(current_user, payload.opening_balance)


@router.get("/goals", response_model=list[GoalResponse])
def list_goals(
    status_filter: Optional[GoalStatus] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> list[GoalResponse]:
    return service.list_goals(current_user, status_filter)


@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreateRequest,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    return service.create_goal(
        current_user=current_user,
        kind=payload.kind,
        name=payload.name,
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        notes=payload.notes,
        debt_id=payload.debt_id,
    )


@router.get("/goals/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    return service.get_goal(current_user, goal_id)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: str,
    payload: GoalUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    return service.update_goal(current_user, goal_id, payload.model_dump(exclude_unset=True))


@router.post("/goals/{goal_id}/complete", response_model=GoalResponse)
def complete_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    return service.complete_goal(current_user, goal_id)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> None:
    service.delete_goal(current_user, goal_id)


@router.get("/goals/{goal_id}/contributions", response_model=list[ContributionResponse])
def list_contributions(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> list[ContributionResponse]:
    return service.list_contributions(current_user, goal_id)


@router.post(
    "/goals/{goal_id}/contributions",
    response_model=ContributionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_contribution(
    goal_id: str,
    payload: ContributionCreateRequest,
    current_user: User = Depends(get_current_user),
    service: GoalService = Depends(get_goal_service),
) -> ContributionResponse:
    return service.add_contribution(
        current_user=current_user,
        goal_id=goal_id,
        direction=payload.direction,
        amount=payload.amount,
        contribution_date=payload.contribution_date,
        notes=payload.notes,
    )
