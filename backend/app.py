"""Compatibility entrypoint for uvicorn.

Keeps `uvicorn backend.app:app` working while the real application lives in
backend.api.app.
"""

from backend.api.app import app, create_app

__all__ = ["app", "create_app"]