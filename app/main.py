"""Application factory, health probes, error contract, and request observability."""

import json
import logging
import re
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.v1 import agents, hosts, tasks
from app.config import Settings
from app.db.session import build_engine, build_session_factory
from app.services.inventory import DomainError

REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
request_logger = logging.getLogger("inventory.requests")
health_logger = logging.getLogger("inventory.health")


def error_response(request: Request, status: int, code: str, message: str, details=None):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "details": details},
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        engine.dispose()

    application = FastAPI(
        title="Automation Inventory API",
        version="0.1.0",
        description=(
            "Hosts, automation agents, and task metadata. Updates require the current version; "
            "deletes require a version query parameter. Tasks are never executed."
        ),
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.session_factory = build_session_factory(engine)
    inventory_logger = logging.getLogger("inventory")
    inventory_logger.setLevel(settings.log_level.upper())
    if not inventory_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        inventory_logger.addHandler(handler)

    @application.middleware("http")
    async def observe_request(request: Request, call_next):
        supplied_id = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            supplied_id if REQUEST_ID.fullmatch(supplied_id) else str(uuid4())
        )
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            request_logger.error(
                json.dumps(
                    {
                        "event": "unhandled_error",
                        "request_id": request.state.request_id,
                        "method": request.method,
                        "path": request.url.path,
                    }
                )
            )
            response = error_response(
                request, 500, "internal_error", "An unexpected error occurred."
            )
        response.headers["X-Request-ID"] = request.state.request_id
        request_logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
        )
        return response

    @application.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return error_response(request, exc.status_code, exc.code, exc.message)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        details = json.loads(json.dumps(exc.errors(), default=str))
        return error_response(
            request, 422, "validation_error", "Request validation failed.", details
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(request, exc.status_code, "http_error", str(exc.detail))

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        health_logger.error(
            json.dumps(
                {
                    "event": "database_unavailable",
                    "request_id": request.state.request_id,
                    "exception": type(exc).__name__,
                }
            )
        )
        return error_response(request, 503, "database_unavailable", "The database is unavailable.")

    @application.get("/health/live", tags=["Health"])
    def live():
        return {"status": "alive"}

    @application.get(
        "/health", tags=["Health"], responses={503: {"description": "Database unavailable"}}
    )
    @application.get(
        "/health/ready", tags=["Health"], responses={503: {"description": "Database unavailable"}}
    )
    def ready(request: Request):
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            health_logger.error(
                json.dumps(
                    {
                        "event": "readiness_failed",
                        "request_id": request.state.request_id,
                        "exception": type(exc).__name__,
                    }
                )
            )
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    for router in (hosts.router, agents.router, tasks.router):
        application.include_router(router, prefix="/api/v1")
    return application


app = create_app()
