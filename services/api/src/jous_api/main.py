"""Configured process and PostgreSQL connectivity foundation; no domain behavior."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .config import ConfigurationError, Settings, load_settings
from .database import Database
from .identity import AccessDenied
from .middleware import RequestBoundary
from .observability import application_logger
from .authentication import RejectingVerifier
from .auth_adapters.supabase import SupabaseVerifier


def create_app(settings: Settings | None = None) -> FastAPI:
    try:
        settings = load_settings() if settings is None else settings
    except ConfigurationError as error:
        # Invalid configuration cannot safely supply logger identity/environment.
        print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                          "severity": "ERROR", "service": "jous-api",
                          "environment": "unknown", "event": "configuration_failed",
                          "request_id": None, "detail": str(error)}), file=sys.stderr)
        raise
    logger = application_logger(settings)
    database = Database(settings)
    verifier = (SupabaseVerifier(settings.auth_issuer, settings.auth_audience, settings.auth_jwks_url)
                if settings.auth_issuer else RejectingVerifier())

    @asynccontextmanager
    async def lifespan(app):
        logger.info("", extra={"event": "startup"})
        try:
            yield
        finally:
            try:
                await verifier.aclose()
            finally:
                await database.dispose()
                logger.info("", extra={"event": "shutdown"})

    application = FastAPI(title=settings.service_name, version="0.1.0", docs_url=None,
                          redoc_url=None, openapi_url=None, lifespan=lifespan)
    application.state.settings = settings
    application.state.logger = logger
    application.state.database = database
    application.state.credential_verifier = verifier
    application.add_middleware(RequestBoundary, logger=logger)

    @application.exception_handler(AccessDenied)
    async def access_denied(request: Request, error: AccessDenied):
        logger.warning("", extra={"event": "access_denied", "status_code": error.status_code})
        unauthenticated = error.status_code == 401
        return JSONResponse(status_code=error.status_code, content={
            "error": {"code": "identity_required" if unauthenticated else "resource_unavailable",
                      "message": "Identity required" if unauthenticated else "Resource unavailable"},
            "request_id": request.state.request_id})

    @application.get("/health/live")
    async def liveness():
        return {"status": "alive"}

    @application.get("/health/ready")
    async def readiness(request: Request):
        try:
            await application.state.database.check()
        except Exception:
            # Never log the driver exception, URL, host, SQL, or traceback.
            logger.warning("", extra={"event": "database_unavailable"})
            return JSONResponse(status_code=503, content={
                "status": "not_ready", "database": "unavailable",
                "request_id": request.state.request_id})
        return {"status": "ready", "database": "reachable",
                "request_id": request.state.request_id}

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=app.state.settings.api_host, port=app.state.settings.api_port,
                access_log=False)
