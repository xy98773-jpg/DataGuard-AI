"""DataGuard AI backend entrypoint.

FastAPI service layer: orchestrates persistence + API only.
Agents are never called directly by the frontend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import approval, dashboard, database, dataset, report, settings as settings_api, trace, web, workflow
from app.config import settings
from app.logging_config import setup_logging
from app.storage.database import init_db
from app.tools import init_tools

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    init_tools()
    logger.info(f"{settings.app_name} backend started (provider={settings.llm_provider})")
    yield
    logger.info("backend shutdown")


app = FastAPI(
    title=settings.app_name,
    description="Enterprise Data Governance Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (dataset.router, workflow.router, trace.router, approval.router, database.router, web.router, dashboard.router, report.router, settings_api.router):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}
