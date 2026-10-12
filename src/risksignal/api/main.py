"""The RiskSignal FastAPI application.

Run it with::

    uvicorn risksignal.api.main:app --reload

Interactive documentation is served at /docs. All data are synthetic and all model parameters
are illustrative.
"""

import logging
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from risksignal import __version__
from risksignal.api import routes_agent, routes_simulation, routes_systems
from risksignal.api.dependencies import (
    ApiError,
    Settings,
    get_settings,
    get_tool_context,
    llm_is_configured,
)
from risksignal.api.schemas import HealthResponse
from risksignal.tools.context import ToolContext
from risksignal.tools.schemas import ToolError
from risksignal.tools.system_tools import list_systems

logger = logging.getLogger(__name__)

DESCRIPTION = """\
Backend for **RiskSignal**, an agentic Operational Risk investigation and stochastic scenario prototype.

* **All data are synthetic** (a fictional institution, "Atlas Bank") and all model parameters are illustrative.
* Simulation results are outputs under stated modelling assumptions, **not forecasts**, and not regulatory capital figures.
* The agent endpoint supports a human analyst. Risk numbers are computed by deterministic tools, not by the language model, and any number the agent writes is checked against the tool outputs (best effort). It makes no risk decisions.
* Not calibrated to, and not related to, any real institution.
"""

TAGS = [
    {"name": "system", "description": "Service status."},
    {"name": "overview", "description": "Bank-wide counts and recent incidents (observed synthetic data)."},
    {"name": "systems", "description": "Observed synthetic data about systems, incidents, KRIs, controls and dependencies."},
    {"name": "simulation", "description": "Modelled output: Monte Carlo loss simulation and stress scenario comparison."},
    {"name": "agent", "description": "The AI investigation agent."},
]


def _error(status_code: int, error_type: str, message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"type": error_type, "message": message, **extra}})


def create_app() -> FastAPI:
    app = FastAPI(title="RiskSignal API", version=__version__, description=DESCRIPTION, openapi_tags=TAGS)

    @app.get("/health", response_model=HealthResponse, tags=["system"], summary="Service status")
    def health(ctx: ToolContext = Depends(get_tool_context), settings: Settings = Depends(get_settings)) -> HealthResponse:
        """Reports whether the service, the database and the language model are available.

        The database counts as available only if it can actually be read and contains systems, so an
        empty or corrupt file is reported as degraded (Docker Compose gates the dashboard on this).
        """
        systems = list_systems(ctx)
        database_available = not isinstance(systems, ToolError) and len(systems.systems) > 0
        return HealthResponse(
            status="ok" if database_available else "degraded",
            version=__version__,
            database_available=database_available,
            llm_provider=settings.llm_provider,
            llm_configured=llm_is_configured(settings),
        )

    app.include_router(routes_systems.overview_router)
    app.include_router(routes_systems.router)
    app.include_router(routes_simulation.router)
    app.include_router(routes_agent.router)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        extra = {"suggestions": error.suggestions} if error.suggestions else {}
        return _error(error.status_code, error.error_type, error.message, **extra)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        details = [{"field": ".".join(str(part) for part in e["loc"]), "message": e["msg"]} for e in error.errors()]
        return _error(422, "validation_error", "The request is not valid.", details=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        return _error(error.status_code, "http_error", str(error.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "internal_error", "Internal server error.")

    return app


app = create_app()
