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
    # Seed background pools on startup - run in background, don't block server
    import asyncio
    try:
        from gui.api.listening import seed_pool_on_startup as listening_seed
        asyncio.create_task(listening_seed())
    except Exception:
        pass
    try:
        from gui.api.reading import seed_pool_on_startup as reading_seed
        asyncio.create_task(reading_seed())
    except Exception:
        pass
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="English Coach", docs_url=None, redoc_url=None, lifespan=_lifespan)

    # API routers
    from gui.api import vocab, grammar, reading, writing, chat, progress, setup as setup_api, license as license_api, history as history_api, voice as voice_api, listening as listening_api, wordbooks as wordbooks_api, warehouse as warehouse_api
    app.include_router(vocab.router)
    app.include_router(wordbooks_api.router)
    app.include_router(grammar.router)
    app.include_router(reading.router)
    app.include_router(writing.router)
    app.include_router(chat.router)
    app.include_router(progress.router)
    app.include_router(setup_api.router)
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
