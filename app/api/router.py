from fastapi import APIRouter

from app.api.v1.router import router as v1_router
from app.modules.notifications.router import router as notifications_router

api_router = APIRouter()
api_router.include_router(v1_router, prefix="/v1")
api_router.include_router(notifications_router)
