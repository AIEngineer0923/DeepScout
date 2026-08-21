"""Token-aware SELECT / FILTER / RANK / COMPRESS / ISOLATE for retrieved chunks."""

from __future__ import annotations

from deepscout_research.retrieval.chunking import estimate_tokens
from deepscout_research.retrieval.models import RetrievedChunk
from deepscout_research.retrieval.security import wrap_as_untrusted_data
from deepscout_research.retrieval.spec import CONTEXT_TOKEN_BUDGET


def assemble_context(
    chunks: list[RetrievedChunk],
    *,
    token_budget: int = CONTEXT_TOKEN_BUDGET,
) -> list[RetrievedChunk]:
    """Drop near-duplicate ordinals from the same snapshot, then fit the budget."""
    selected: list[RetrievedChunk] = []
    seen_spans: set[tuple[str, int]] = set()
    used = 0
    for chunk in chunks:
        key = (str(chunk.snapshot_id), chunk.ordinal)
        neighbor = (str(chunk.snapshot_id), chunk.ordinal - 1)
        if key in seen_spans or neighbor in seen_spans:
            continue
        cost = estimate_tokens(chunk.text)
        if selected and used + cost > token_budget:
            break
        selected.append(chunk)
        seen_spans.add(key)
        used += cost
    return selected


def isolated_prompt_blocks(chunks: list[RetrievedChunk]) -> list[str]:
    blocks = []
    for chunk in assemble_context(chunks):
        locator = chunk.locator
        blocks.append(f"{locator}\n{wrap_as_untrusted_data(chunk.text)}")
    return blocks
