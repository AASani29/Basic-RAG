"""Application factory: wiring only, no business logic.

Everything that has to happen exactly once and in a specific order lives here —
logging setup, middleware order, error handling, route registration.
"""

import time
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import auth, health, items
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger("request")
error_logger = get_logger("error")


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------
# Every failure leaves this app in the same shape, so the frontend has exactly
# one error parser instead of one per endpoint:
#     {"error": {"code": "not_found", "message": "...", "details": null}}


def _error_response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def _code_for_status(status: int) -> str:
    """Turn 404 into "not_found" so clients can branch on a stable string
    instead of hardcoding numbers."""
    try:
        return HTTPStatus(status).phrase.lower().replace(" ", "_")
    except ValueError:  # a non-standard status code
        return "error"


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Registered against Starlette's HTTPException, not FastAPI's subclass, so
    # it also catches the 404s and 405s the router raises before our code runs.
    return _error_response(exc.status_code, _code_for_status(exc.status_code), str(exc.detail))


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 body is a bare list at the top level, which breaks
    # the one-shape rule. The field-level errors are preserved under `details`
    # because forms need them to mark the offending input.
    return _error_response(
        422, "validation_error", "Request validation failed", details=exc.errors()
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback for us; return a generic message to the caller.
    # Exception text routinely contains table names, SQL and file paths, and
    # leaking those to an unauthenticated client is how attackers map a system.
    error_logger.exception(
        "unhandled exception method=%s path=%s", request.method, request.url.path
    )
    return _error_response(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


async def log_requests(request: Request, call_next):
    """Structured access log with latency.

    perf_counter, not time(), because it is monotonic — a clock adjustment
    mid-request cannot produce a negative duration.
    """
    started = time.perf_counter()
    # Pre-set to 500: if call_next raises, no response object ever exists here
    # because the exception propagates to the handler registered *outside* this
    # middleware. Logging in `finally` means a crashing request still produces
    # an access-log line — otherwise the log silently omits exactly the
    # requests you most want to see.
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info(
            "method=%s path=%s status=%d duration_ms=%.1f",
            request.method,
            request.url.path,
            status,
            (time.perf_counter() - started) * 1000,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Before FastAPI() so anything logged during startup uses our config.
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("startup app=%s", settings.app_name)
        yield
        logger.info("shutdown")

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # Starlette applies add_middleware in reverse, so the LAST one added is the
    # outermost. CORS goes last deliberately: it must wrap the error handlers,
    # or a 401 would come back without CORS headers and the browser would show
    # the frontend a generic network error instead of the real status.
    app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # Not "*": with credentials allowed the browser rejects a wildcard, and
        # an explicit list is what you want in front of a real API anyway.
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(items.router)

    return app


# Module-level instance for `uvicorn app.main:app`. The factory above is what
# tests call, so they can build an app with overridden settings.
app = create_app()
