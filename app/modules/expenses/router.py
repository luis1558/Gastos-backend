from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.expenses.schemas import (
    ExpenseCategoryCreateRequest,
    ExpenseCategoryResponse,
    ExpenseCategoryUpdateRequest,
    ExpenseCreateRequest,
    ExpenseListItemResponse,
    ExpenseResponse,
    ExpenseUpdateRequest,
)
from app.modules.expenses.service import ExpenseService
from app.modules.users.models import User

router = APIRouter(tags=["expenses"])


def get_expense_service(db: Session = Depends(get_db)) -> ExpenseService:
    return ExpenseService(db)


@router.get("/expense-categories", response_model=list[ExpenseCategoryResponse])
def list_expense_categories(
    active_only: Optional[bool] = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> list[ExpenseCategoryResponse]:
    return service.list_categories(current_user, active_only)


@router.post(
    "/expense-categories",
    response_model=ExpenseCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense_category(
    payload: ExpenseCategoryCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> ExpenseCategoryResponse:
    return service.create_category(
        current_user=current_user,
        name=payload.name,
        slug=payload.slug,
        color=payload.color,
        icon=payload.icon,
    )


@router.patch("/expense-categories/{category_id}", response_model=ExpenseCategoryResponse)
def update_expense_category(
    category_id: str,
    payload: ExpenseCategoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> ExpenseCategoryResponse:
    return service.update_category(
        current_user=current_user,
        category_id=category_id,
        name=payload.name,
        color=payload.color,
        icon=payload.icon,
        is_active=payload.is_active,
    )


@router.get("/expenses", response_model=list[ExpenseListItemResponse])
def list_expenses(
    year: int = Query(..., ge=2000, le=2100),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> list[ExpenseListItemResponse]:
    return service.list_expenses(current_user, year, month)


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> ExpenseResponse:
    return service.create_expense(
        current_user=current_user,
        category_id=payload.category_id,
        expense_date=payload.expense_date,
        amount=payload.amount,
        description=payload.description,
        payment_method=payload.payment_method,
        notes=payload.notes,
        period_year=payload.period_year,
        period_month=payload.period_month,
    )


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: str,
    payload: ExpenseUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> ExpenseResponse:
    return service.update_expense(
        current_user=current_user,
        expense_id=expense_id,
        category_id=payload.category_id,
        expense_date=payload.expense_date,
        amount=payload.amount,
        description=payload.description,
        payment_method=payload.payment_method,
        notes=payload.notes,
        period_year=payload.period_year,
        period_month=payload.period_month,
    )


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: str,
    current_user: User = Depends(get_current_user),
    service: ExpenseService = Depends(get_expense_service),
) -> Response:
    service.delete_expense(current_user, expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
