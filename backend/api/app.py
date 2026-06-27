# backend/api/app.py
"""FastAPI application for the ArmorIQ policy admin + chat backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import dependencies
from backend.api.dependencies import get_policy_store
from backend.api.exceptions import register_exception_handlers
from backend.api.routers.approvals import router as approvals_router
from backend.api.routers.budgets import router as budgets_router
from backend.api.routers.chat import router as chat_router
from backend.api.routers.logs import router as logs_router
from backend.api.routers.rules import router as rules_router
from backend.api.schemas import HealthResponse

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages startup and shutdown of long-lived backend resources.

    Startup
    -------
    - Connect all MCP transports (stdio local-crud + optional Context7).
    - Discover available tools from those servers.

    Shutdown
    --------
    - Disconnect all MCP transports cleanly.
    - Close the Gemini LLM client (closes its aiohttp session).

    Both steps delegate to helpers in dependencies.py so the same singleton
    instances used by the dependency providers are the ones being managed.
    """
    logger.info("ArmorIQ backend starting up (version %s).", APP_VERSION)
    await dependencies.startup()
    yield
    logger.info("ArmorIQ backend shutting down.")
    await dependencies.shutdown()


def create_app() -> FastAPI:
    """Builds and returns the FastAPI application."""
    app = FastAPI(
        title="ArmorIQ Policy Admin API",
        version=APP_VERSION,
        description=(
            "Admin API for managing policy rules, approvals, budgets, audit "
            "logs, and conversing with the guarded agent."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],    # tighten to specific origins before production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # ------------------------------------------------------------------
    # Built-in endpoints
    # ------------------------------------------------------------------

    @app.get("/", tags=["Meta"])
    async def root() -> dict[str, str]:
        return {
            "name": "ArmorIQ Policy Admin API",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", response_model=HealthResponse, tags=["Meta"])
    async def health(store=Depends(get_policy_store)) -> HealthResponse:
        return HealthResponse(
            status="ok",
            rules=len(await store.list_rules()),
            pending_approvals=len(await store.list_pending_approvals()),
            version=APP_VERSION,
        )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------

    app.include_router(rules_router, prefix="/api")
    app.include_router(approvals_router, prefix="/api")
    app.include_router(budgets_router, prefix="/api")
    app.include_router(logs_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")

    return app


app = create_app()