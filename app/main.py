"""Application entry point: all routers, middleware and server start-up.

    uvicorn app.main:app          (production; see railway.json)
    python -m app.main            (local development, with auto-reload)
"""

import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Project constants, config and dependency container
from app.constants.constants import DASHBOARD_CSP, DASHBOARD_FILE, STATIC_DIRECTORY
from app.containers.container import Container

# Routers
from app.routers import dashboard_router as dashboard_routes
from app.routers import patient_router as patient_routes
from app.routers import vapi_router as vapi_routes
from app.routers.dashboard_router import dashboard_router
from app.routers.patient_router import patient_router
from app.routers.vapi_router import vapi_router

# ---------------------------------------------------------------------------
# Container & Logging Setup
# ---------------------------------------------------------------------------
container = Container()
container.utilities.logging_configurator().configure()
# Resolves every Depends(Provide[...]) in the router modules against this container.
container.wire(modules=[patient_routes, vapi_routes, dashboard_routes])

logger = logging.getLogger("app")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    start_t = time.perf_counter()
    try:
        # The schema itself is created by `alembic upgrade head`, which runs before the server.
        container.database().execute_scalar(container.utilities.sql_loader().load("health_check"))
        seeded = container.services.seed_service().seed_if_empty()
        logger.info("Database ready (%d demo patients seeded).", seeded)
    except Exception:
        logger.exception("Failed to initialize database. Has `alembic upgrade head` been run?")
        raise

    elapsed = (time.perf_counter() - start_t) * 1000
    logger.info("Startup complete in %.1f ms", elapsed)
    yield

    logger.info("Shutting down...")


# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Patient Registration API",
    description="REST API behind the patient registration voice agent.",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.container = container

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # reviewers query the API from anywhere; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security Headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Exception Handlers (every error uses the { data, error } envelope)
# ---------------------------------------------------------------------------
container.exception_handlers().register(app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(patient_router)
app.include_router(vapi_router)
app.include_router(dashboard_router)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")


# ---------------------------------------------------------------------------
# Health / Meta Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Meta"])
def health() -> JSONResponse:
    responses = container.utilities.response_builder()
    try:
        container.database().execute_scalar(container.utilities.sql_loader().load("health_check"))
    except Exception as exc:
        logger.warning("Health check failed: %s", exc)
        return responses.error(500, "database_unavailable", "Database is not reachable.")
    return responses.success({"status": "ok", "database": "ok"})


@app.get("/version", tags=["Meta"])
def version() -> JSONResponse:
    return container.utilities.response_builder().success({"app": app.title, "version": app.version})


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    """The web console. Its scripts and styles are served from /static."""
    return FileResponse(
        DASHBOARD_FILE,
        media_type="text/html",
        headers={"Content-Security-Policy": DASHBOARD_CSP, "Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        log_level="info",
    )
