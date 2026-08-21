from contextlib import asynccontextmanager

from deepscout_core.settings import Settings, get_settings
from deepscout_research.smoke_agent import run_smoke_agent
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from deepscout_api.main import configure_observability
from deepscout_api.probes import probe_postgres, probe_redis
from deepscout_api.routes.product import router as product_router
from deepscout_api.routes.research_runs import router as research_runs_router
from deepscout_api.security import install_security_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_observability(get_settings())
    yield


app = FastAPI(
    title="DeepScout API",
    version="0.2.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
install_security_middleware(app, get_settings())
app.include_router(research_runs_router)
app.include_router(product_router)


class HealthResponse(BaseModel):
    status: str


class DependencyHealthResponse(BaseModel):
    postgres: str
    redis: str


class SmokeAgentRequest(BaseModel):
    message: str = Field(default="Verify DeepScout agent smoke path")


class SmokeAgentResponseBody(BaseModel):
    reply: str
    tool_used: bool
    provider: str
    model: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/v1/health/deps", response_model=DependencyHealthResponse)
def health_dependencies(settings: Settings = Depends(get_settings)) -> DependencyHealthResponse:
    return DependencyHealthResponse(
        postgres=probe_postgres(settings.database_url),
        redis=probe_redis(settings.redis_url),
    )


@app.post("/api/v1/smoke/agent", response_model=SmokeAgentResponseBody)
def smoke_agent(
    body: SmokeAgentRequest,
    settings: Settings = Depends(get_settings),
) -> SmokeAgentResponseBody:
    if not settings.enable_smoke_agent:
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
