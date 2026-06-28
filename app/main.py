import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import install_exception_handlers


def _run_migrations() -> None:
    from alembic.config import Config
    from alembic.command import upgrade

    alembic_cfg = Config("alembic.ini")
    upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    is_vercel = os.environ.get("VERCEL_ENV") is not None

    if not is_vercel:
        _run_migrations()

        from app.modules.notifications.scheduler import start_scheduler, stop_scheduler

        start_scheduler()
        yield
        stop_scheduler()
    else:
        _run_migrations()
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_exception_handlers(app)

    @app.get("/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
