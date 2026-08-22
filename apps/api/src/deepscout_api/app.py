import os
from contextlib import asynccontextmanager

from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.session import dispose_all_engines
from deepscout_research.smoke_agent import run_smoke_agent
from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from deepscout_api.main import configure_observability
from deepscout_api.probes import probe_postgres, probe_postgres_schema, probe_redis
from deepscout_api.routes.account import router as account_router
from deepscout_api.routes.auth import router as auth_router
from deepscout_api.routes.demos import router as demos_router
from deepscout_api.routes.knowledge import router as knowledge_router
from deepscout_api.routes.monitors import router as monitors_router
from deepscout_api.routes.product import router as product_router
from deepscout_api.routes.research_runs import router as research_runs_router
from deepscout_api.routes.reviews import router as reviews_router
from deepscout_api.routes.rum import router as rum_router
from deepscout_api.routes.templates import router as templates_router
from deepscout_api.security import install_security_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_observability(get_settings())
    try:
        yield
    finally:
        dispose_all_engines()


app = FastAPI(
    title="DeepScout API",
    version="0.2.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
install_security_middleware(app, get_settings())
app.include_router(demos_router)
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(research_runs_router)
app.include_router(product_router)
app.include_router(reviews_router)
app.include_router(templates_router)
app.include_router(knowledge_router)
app.include_router(monitors_router)
app.include_router(rum_router)


class HealthResponse(BaseModel):
    status: str
    git_sha: str | None = None


class DependencyHealthResponse(BaseModel):
    postgres: str
    redis: str
    redis_required: bool = False


class ReadinessResponse(BaseModel):
    status: str
    postgres: str


class SmokeAgentRequest(BaseModel):
    message: str = Field(default="Verify DeepScout agent smoke path")


class SmokeAgentResponseBody(BaseModel):
    reply: str
    tool_used: bool
    provider: str
    model: str


@app.get("/health", response_model=HealthResponse)
@app.get("/live", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness: process is up. Does not probe optional deps (LangSmith/Redis)."""
    git_sha = (
        os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("VERCEL_GIT_COMMIT_SHA")
        or os.environ.get("GIT_SHA")
    )
    return HealthResponse(status="ok", git_sha=git_sha)


@app.get("/ready", response_model=ReadinessResponse)
def ready(response: Response, settings: Settings = Depends(get_settings)) -> ReadinessResponse:
    """Readiness: authoritative Postgres must be available. Redis is optional MODE A probe."""
    postgres = probe_postgres(settings.database_url)
    if postgres != "ok":
        response.status_code = 503
        return ReadinessResponse(status="unavailable", postgres=postgres)
    if settings.is_hosted():
        schema = probe_postgres_schema(settings.database_url)
        if schema != "ok":
            response.status_code = 503
            return ReadinessResponse(status="unavailable", postgres=schema)
    if settings.is_hosted() and not settings.hosted_auth_ready():
        response.status_code = 503
        return ReadinessResponse(status="unavailable", postgres=postgres)
    return ReadinessResponse(status="ok", postgres=postgres)


@app.get("/api/v1/health/deps", response_model=DependencyHealthResponse)
def health_dependencies(settings: Settings = Depends(get_settings)) -> DependencyHealthResponse:
    return DependencyHealthResponse(
        postgres=probe_postgres(settings.database_url),
        redis=probe_redis(settings.redis_url),
        redis_required=False,
    )


@app.post("/api/v1/smoke/agent", response_model=SmokeAgentResponseBody)
def smoke_agent(
    body: SmokeAgentRequest,
    settings: Settings = Depends(get_settings),
) -> SmokeAgentResponseBody:
    if settings.is_hosted() or not settings.enable_smoke_agent:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        result = run_smoke_agent(settings, user_message=body.message)
    except ValueError:
        raise HTTPException(status_code=503, detail="Smoke agent is not configured") from None
    except Exception:
        raise HTTPException(status_code=502, detail="LLM provider request failed") from None

    return SmokeAgentResponseBody(
        reply=result.structured.reply,
        tool_used=result.structured.tool_used,
        provider=result.provider,
        model=result.model,
    )
