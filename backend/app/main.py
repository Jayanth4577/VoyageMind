"""VoyageMind FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    agents,
    analytics,
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
from app.core.rate_limit import RateLimitMiddleware

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all is idempotent; production runs `alembic upgrade head` on deploy.
    init_db()
    if settings.environment == "production" and settings.jwt_secret.startswith("dev-only"):
        logger.error(
            "SECURITY: JWT_SECRET is still the development default in a production "
            "environment — set a strong JWT_SECRET before going live"
        )
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

    app.add_middleware(RateLimitMiddleware)

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
    app.include_router(analytics.router)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    @app.get("/health/services", tags=["health"])
    async def health_services() -> dict:
        """Deployment diagnostic: what this process is configured with and what
        it can actually reach. Exposes hosts only — never keys or full URLs with
        credentials."""
        from urllib.parse import urlparse

        from app.core.database import engine
        from app.llm.provider import LLMError, get_llm_provider
        from app.mcp.client import TravelMCPClient

        gateway_host = None
        try:
            gateway_host = urlparse(settings.travel_mcp_url).netloc or None
        except Exception:  # noqa: BLE001
            pass

        # Database reachability
        db_ok = False
        try:
            from sqlalchemy import text

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:  # noqa: BLE001
            db_ok = False

        # LLM provider configured?
        llm_configured = False
        llm_note = ""
        try:
            get_llm_provider()
            llm_configured = True
        except LLMError as exc:
            llm_note = str(exc)

        # Gateway reachability over the MCP protocol
        gateway_ok = False
        gateway_note = ""
        try:
            client = TravelMCPClient()
            tools = await client.list_tools()
            gateway_ok = len(tools) > 0
            if not gateway_ok:
                gateway_note = "connected but listed no tools"
        except Exception as exc:  # noqa: BLE001
            gateway_note = str(exc)[:200]

        return {
            "status": "ok",
            "environment": settings.environment,
            "database": {"ok": db_ok},
            "llm": {
                "provider": settings.llm_provider,
                "configured": llm_configured,
                **({"note": llm_note} if llm_note else {}),
            },
            "mcp_gateway": {
                "host": gateway_host,
                "reachable": gateway_ok,
                **({"note": gateway_note} if gateway_note else {}),
            },
        }

    @app.get("/health/live", tags=["health"])
    def liveness() -> dict:
        return {"status": "alive"}

    return app


app = create_app()
