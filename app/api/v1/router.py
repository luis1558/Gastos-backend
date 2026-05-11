from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.debts.router import router as debts_router
from app.modules.expenses.router import router as expenses_router
from app.modules.income.router import router as income_router
from app.modules.reports.router import router as reports_router
from app.modules.users.router import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(income_router)
router.include_router(expenses_router)
router.include_router(debts_router)
router.include_router(reports_router)
