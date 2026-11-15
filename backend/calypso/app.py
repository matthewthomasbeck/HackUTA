"""Calypso⁻¹ backend: FastAPI app.

Run from `backend/`:
    uv run uvicorn calypso.app:app --host 127.0.0.1 --port 8000 --env-file ../.env
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import db
from .config import Settings
from .identity.face import get_face_embedder
from .identity.voice import get_voice_embedder
from .jobs import get_jobs
from .routes import agent_sessions, app_ingest, calls, days, health, media, people, puck, recall, recognize
from .storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.warn_if_misconfigured()
        settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        db.connect(settings.db_path).close()  # create the file and schema once
        yield

    app = FastAPI(title="Calypso⁻¹ backend", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.storage = get_storage(settings)
    app.state.jobs = get_jobs(settings)
    app.state.face_embedder = get_face_embedder(settings)  # models load lazily on first use
    app.state.voice_embedder = get_voice_embedder(settings)
    app.state.agent_sessions = {}
    app.state.claude_controller = None

    for module in (health, puck, people, media, recognize, recall, calls, days, app_ingest, agent_sessions):
        app.include_router(module.router)

    dashboard = Path(settings.dashboard_dir)
    if dashboard.is_dir():
        app.mount("/dashboard", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app


app = create_app()
