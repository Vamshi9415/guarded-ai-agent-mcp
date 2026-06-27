# backend/api/app.py
"""FastAPI application for the policy admin backend."""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.routers.approvals import router as approvals_router
from backend.api.routers.budgets import router as budgets_router
from backend.api.routers.logs import router as logs_router
from backend.api.routers.rules import router as rules_router


def create_app() -> FastAPI:
    """Builds the FastAPI application."""
    app = FastAPI(
        title="ArmorIQ Policy Admin API",
        version="0.1.0",
        description="Admin API for managing policy rules, approvals, budgets, and audit logs.",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": "ArmorIQ Policy Admin API",
            "docs": "/docs",
            "health": "/health",
        }

    app.include_router(rules_router, prefix="/api")
    app.include_router(approvals_router, prefix="/api")
    app.include_router(budgets_router, prefix="/api")
    app.include_router(logs_router, prefix="/api")

    return app


app = create_app()