"""
FastAPI application factory — mounts all API routers and serves static files.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Startup: Background tasks disabled for stability
    # TODO: Re-enable after fixing pool seeding issues
    yield  # Server runs here
    # Shutdown: cleanup if needed
    pass


def create_app() -> FastAPI:
    app = FastAPI(title="English Coach", docs_url=None, redoc_url=None, lifespan=_lifespan)

    # Health check endpoint - must be first for fast startup verification
    @app.get("/health")
    def health_check():
        return {"status": "ok", "service": "english-coach"}

    # Lazy import API routers to speed up startup
    from gui.api import vocab, wordbooks as wordbooks_api, grammar, reading, writing, chat, progress, setup as setup_api, history as history_api, voice as voice_api, listening as listening_api, warehouse as warehouse_api, speaking as speaking_api, practice as practice_api, mock_exam as mock_exam_api
    from gui.version import is_cloud

    app.include_router(vocab.router)
    app.include_router(wordbooks_api.router)
    app.include_router(grammar.router)
    app.include_router(reading.router)
    app.include_router(writing.router)
    app.include_router(speaking_api.router)
    app.include_router(chat.router)
    app.include_router(progress.router)
    app.include_router(setup_api.router)
    app.include_router(practice_api.router)
    app.include_router(mock_exam_api.router)

    # Only include license API in cloud version
    if is_cloud():
        from gui.api import license as license_api
        app.include_router(license_api.router)

    app.include_router(history_api.router)
    app.include_router(voice_api.router)
    app.include_router(listening_api.router)
    app.include_router(warehouse_api.router)

    # Serve static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(static_dir / "index.html"))

    return app
