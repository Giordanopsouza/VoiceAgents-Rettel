from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker

from app.availability import AvailabilityQueryError, list_available_slots
from app.db import init_db
from app.events import list_request_events
from app.failure_lab import FailureLab, FailureLabToggle
from app.seed import reset_calendar, schedule_payload, seed_if_empty
from app.settings import Settings, get_settings

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = init_db(app.state.settings.database_path)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        seed_if_empty(session)
    app.state.engine = engine
    app.state.session_factory = session_factory
    yield
    engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(
        title="Retell Dental Booking Reliability Lab",
        lifespan=lifespan,
    )
    application.state.settings = settings or get_settings()
    application.state.failure_lab = FailureLab(
        timeout_seconds=application.state.settings.retell_function_timeout_seconds,
        delay_seconds=application.state.settings.failure_lab_delay_seconds,
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/availability")
    def get_availability(request: Request, date: str | None = None) -> dict:
        try:
            with request.app.state.session_factory() as session:
                return list_available_slots(session, date)
        except AvailabilityQueryError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": exc.error, "message": exc.message},
            ) from exc

    @application.get("/api/events")
    def get_events(request: Request) -> dict:
        with request.app.state.session_factory() as session:
            return {"events": list_request_events(session)}

    @application.get("/api/failure-lab")
    def get_failure_lab(request: Request) -> dict:
        return request.app.state.failure_lab.snapshot()

    @application.put("/api/failure-lab")
    def put_failure_lab(request: Request, body: FailureLabToggle) -> dict:
        return request.app.state.failure_lab.set_enabled(body.enabled)

    @application.post("/api/demo/reset")
    def reset_demo(request: Request) -> dict:
        if not request.app.state.settings.live_demo_enabled:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Calendar reset is unavailable while the public live demo is paused."
                ),
            )
        with request.app.state.session_factory() as session:
            reset_calendar(session)
            payload = schedule_payload(session)
        request.app.state.failure_lab.reset_attempts()
        return {"status": "reset", **payload}

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


app = create_app()
