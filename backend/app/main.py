"""VoyageMind FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    agents,
    auth,
    budget,
    copilot,
    group,
    itinerary,
    optimization,
    trips,
    weather,
)
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger, request_id_var

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all is idempotent; production runs `alembic upgrade head` on deploy.
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI Agentic Travel Planning Workspace",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid4().hex
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals; log with request id for correlation.
        logger.error("unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(auth.router)
    app.include_router(trips.router)
    app.include_router(itinerary.router)
    app.include_router(budget.router)
    app.include_router(weather.router)
    app.include_router(optimization.router)
    app.include_router(agents.router)
    app.include_router(copilot.router)
    app.include_router(group.router)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    @app.get("/health/live", tags=["health"])
    def liveness() -> dict:
        return {"status": "alive"}

    return app


app = create_app()
