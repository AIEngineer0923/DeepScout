"""Bounded nested delegation — retrieved text cannot spawn agents."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.settings import Settings

from deepscout_research.approval import text_claims_approval

SPAWN_PATTERNS = (
    "spawn 100 agents",
    "create more workers",
    "delegate recursively",
    "delegate this recursively",
    "ignore delegation policy",
    "max_delegation_depth",
    "increase max_depth",
    "ignore max depth",
    "create children until",
    "budget does not matter",
    "ignore budget",
)


@dataclass(frozen=True, slots=True)
class DelegationPolicy:
    max_depth: int
    max_children: int
    max_total_workers: int

    @classmethod
    def from_settings(cls, settings: Settings) -> DelegationPolicy:
        return cls(
            max_depth=max(1, settings.agent_max_delegation_depth),
            max_children=2,
            max_total_workers=settings.agent_max_total_workers,
        )

    def can_delegate(
        self,
        *,
        parent_depth: int,
        existing_children: int,
        total_workers: int,
        untrusted_text: str | None = None,
    ) -> bool:
        if untrusted_text and _injection_requests_spawn(untrusted_text):
            return False
        if parent_depth >= self.max_depth:
            return False
        if existing_children >= self.max_children:
            return False
        if total_workers >= self.max_total_workers:
            return False
        return True


def _injection_requests_spawn(text: str) -> bool:
    lowered = text.casefold()
    if text_claims_approval(text):
        return True
    return any(pattern in lowered for pattern in SPAWN_PATTERNS)
