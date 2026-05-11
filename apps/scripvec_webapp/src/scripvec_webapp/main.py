"""FastAPI app factory and static-asset wiring."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    """Build the FastAPI app with API routes and the static UI mounted at `/`."""
    app = FastAPI(
        title="scripvec",
        description="Vector search over LDS scripture — web front-end (CR-010).",
        version="0.0.0",
    )
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount(
            "/static",
            StaticFiles(directory=STATIC_DIR),
            name="static",
        )
    return app
