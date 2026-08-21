"""Application-owned tool capability registry. Skills cannot grant tools."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.domain.enums import ToolSideEffectClass
from deepscout_core.domain.schemas import WORKER_TOOL_ALLOWLIST


@dataclass(frozen=True, slots=True)
class ToolCapability:
    tool_id: str
    version: str
    description: str
    side_effect_class: ToolSideEffectClass
    network_scope: str
    idempotent: bool
    parallel_safe: bool
    requires_review: bool
    allowed_roles: tuple[str, ...]


REGISTRY: dict[str, ToolCapability] = {
    "web_search": ToolCapability(
        tool_id="web_search",
        version="1",
        description="Search the public web for candidate sources. Read-only.",
        side_effect_class=ToolSideEffectClass.READ_NETWORK,
        network_scope="public_http",
        idempotent=True,
        parallel_safe=True,
        requires_review=False,
        allowed_roles=("research_worker",),
    )
}


def resolve_tools(requested: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in requested if name in WORKER_TOOL_ALLOWLIST and name in REGISTRY)


def describe_tools(tool_ids: tuple[str, ...]) -> str:
    lines = []
    for name in tool_ids:
        cap = REGISTRY.get(name)
        if cap:
            lines.append(f"{cap.tool_id}: {cap.description}")
    return "\n".join(lines)


class ToolAuthorization:
    ALLOW_AUTONOMOUS = "allow_autonomous"
    REQUIRE_REVIEW = "require_review"
    DENY = "deny"


def classify_tool_request(name: str, *, requester: str = "worker") -> str:
    """Application-owned authorization. Model/retrieved/skill text cannot approve."""
    _ = requester
    cap = REGISTRY.get(name)
    if cap is None:
        return ToolAuthorization.DENY
    if cap.requires_review or cap.side_effect_class.value in {"write_external", "destructive"}:
        return ToolAuthorization.REQUIRE_REVIEW
    return ToolAuthorization.ALLOW_AUTONOMOUS


def mcp_cannot_self_authorize(server_claims: dict) -> bool:
    """MCP metadata is DATA. Application registry remains the allowlist."""
    return False if server_claims else True
