"""Deterministic monitor change detection — no LLM authority."""

from __future__ import annotations

from uuid import UUID

from deepscout_persistence.store import ResearchStore


def detect_run_change(store: ResearchStore, previous_id: UUID, current_id: UUID) -> dict:
    prev_sources = {row.canonical_url for row in store.list_sources(previous_id)}
    curr_sources = {row.canonical_url for row in store.list_sources(current_id)}
    prev_hashes = {row.content_hash for row in store.list_snapshots_for_run(previous_id)}
    curr_hashes = {row.content_hash for row in store.list_snapshots_for_run(current_id)}
    prev_claims = {row.statement.strip().lower() for row in store.list_claims(previous_id)}
    curr_claims = {row.statement.strip().lower() for row in store.list_claims(current_id)}
    signals = []
    if curr_sources - prev_sources:
        signals.append("new_sources")
    if prev_sources - curr_sources:
        signals.append("removed_sources")
    if curr_hashes - prev_hashes:
        signals.append("changed_snapshot_hash")
    if curr_claims - prev_claims:
        signals.append("new_claims")
    if prev_claims - curr_claims:
        signals.append("removed_claims")
    if store.list_contradictions(current_id):
        signals.append("contradictions")
    return {
        "changed": bool(signals),
        "signals": signals,
        "added_sources": sorted(curr_sources - prev_sources)[:20],
        "removed_sources": sorted(prev_sources - curr_sources)[:20],
    }
