from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker

from app.db import init_db
from app.settings import Settings, get_settings

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = init_db(app.state.settings.database_path)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine)
    yield
    engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(
        title="Retell Dental Booking Reliability Lab",
        lifespan=lifespan,
    )
    application.state.settings = settings or get_settings()

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


app = create_app()
