"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.admin_routes import router as admin_router
from backend.api.payments_api import router as payments_create_router
from backend.api.requests_routes import router as requests_router
from core.config import get_settings
from core.logger import setup_logging
from database.connection import AsyncSessionLocal
from database.init_db import create_all
from payments.tbc.webhook import router as tbc_webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for the API process")
    await create_all()

    from parsing.scheduler import start_parse_scheduler, start_payment_sweep_scheduler

    start_parse_scheduler(AsyncSessionLocal, minutes=5)
    if settings.tbc_enabled:
        start_payment_sweep_scheduler(AsyncSessionLocal, minutes=7)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(requests_router)
    app.include_router(payments_create_router)
    app.include_router(tbc_webhook_router)
    app.include_router(admin_router)

    from admin_panel.routes import router as admin_ui_router

    app.include_router(admin_ui_router)
    app.mount("/admin/static", StaticFiles(directory="admin_panel/static"), name="admin_static")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
