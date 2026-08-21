"""Compile run-scoped wiki knowledge from persisted claims/evidence."""

from __future__ import annotations

import logging
import uuid

from deepscout_persistence.knowledge import lint_wiki, rebuild_wiki_from_claims
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

logger = logging.getLogger(__name__)


@traceable(name="phase:compile_knowledge", run_type="chain")
def compile_knowledge_for_run(store: ResearchStore, run_id: uuid.UUID) -> dict:
    session = store._session
    stats = rebuild_wiki_from_claims(session, run_id)
    lint = lint_wiki(session, run_id)
    session.flush()
    return {**stats, "lint": lint}
