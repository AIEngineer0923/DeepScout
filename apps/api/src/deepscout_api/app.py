from contextlib import asynccontextmanager

from deepscout_core.settings import Settings, get_settings
from deepscout_research.smoke_agent import run_smoke_agent
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import create_engine, text

from deepscout_api.main import configure_observability
from deepscout_api.routes.product import router as product_router
from deepscout_api.routes.research_runs import router as research_runs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_observability(get_settings())
    yield


app = FastAPI(title="DeepScout API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
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
    postgres_status = "unavailable"
    redis_status = "unavailable"

    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        postgres_status = "ok"
    except Exception:
        postgres_status = "unavailable"

    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"

    return DependencyHealthResponse(postgres=postgres_status, redis=redis_status)


@app.post("/api/v1/smoke/agent", response_model=SmokeAgentResponseBody)
def smoke_agent(
    body: SmokeAgentRequest,
    settings: Settings = Depends(get_settings),
) -> SmokeAgentResponseBody:
    try:
        result = run_smoke_agent(settings, user_message=body.message)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="LLM provider request failed") from exc

    return SmokeAgentResponseBody(
        reply=result.structured.reply,
        tool_used=result.structured.tool_used,
        provider=result.provider,
        model=result.model,
    )
