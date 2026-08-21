"""Field RUM — Core Web Vitals only. No research text, prompts, or secrets."""

from __future__ import annotations

from deepscout_core.domain.schemas import WebVitalWrite
from fastapi import APIRouter, Depends, HTTPException

from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/rum", tags=["rum"])

ALLOWED_DEVICE = {"unknown", "desktop", "mobile", "low-end"}
ALLOWED_NETWORK = {"unknown", "4g", "3g", "slow-2g", "2g", "wifi", "lab"}
ALLOWED_SOURCE = {"field", "lab"}
ALLOWED_NAV = {"navigate", "reload", "back_forward", "prerender"}
ALLOWED_ROUTES = {
    "/",
    "/research/new",
    "/history",
    "/reviews",
    "/settings",
    "/knowledge",
    "/monitors",
    "/compare",
    "/research",
}
ALLOWED_PREFIXES = ("/research/", "/knowledge/", "/monitors/", "/resume/", "/history")


def _route_allowed(route: str) -> bool:
    if route in ALLOWED_ROUTES:
        return True
    return any(route.startswith(prefix) for prefix in ALLOWED_PREFIXES)


@router.post("/vitals", status_code=204)
def ingest_vitals(body: WebVitalWrite, store=Depends(get_research_store)) -> None:
    if body.source not in ALLOWED_SOURCE:
        raise HTTPException(status_code=400, detail="invalid source")
    if body.device_class not in ALLOWED_DEVICE:
        body.device_class = "unknown"
    if body.network_class not in ALLOWED_NETWORK:
        body.network_class = "unknown"
    if body.navigation_type not in ALLOWED_NAV:
        body.navigation_type = "navigate"
    if "?" in body.route or "#" in body.route or not body.route.startswith("/") or not _route_allowed(body.route):
        raise HTTPException(status_code=400, detail="invalid route")
    store.record_web_vital(body)
    store.commit()
