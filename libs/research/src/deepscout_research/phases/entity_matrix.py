"""Build the reusable entity/attribute evidence matrix from verified evidence."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict

from deepscout_core.domain.contracts import (
    EntityResearchEntity,
    EntityResearchField,
    EntityResearchMatrix,
    MatrixConflictState,
    MatrixFieldStatus,
    ResearchContract,
)
from deepscout_core.domain.enums import ClaimVerificationStatus
from deepscout_persistence.store import ResearchStore

from deepscout_research.contracts.deliverables import category_keys_match
from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.contracts.text_normalize import normalized_research_tokens

_NAME = re.compile(
    r"\b(?:[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’-]{2,}|[A-Z0-9]{2,})"
    r"(?:\s+(?:[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’-]{1,}|[A-Z0-9]{2,})){0,3}\b"
)
_ENTITY_NOISE = {
    "analysis",
    "august",
    "conclusion",
    "evidence",
    "executive summary",
    "fantacalcio",
    "fonti",
    "italia",
    "italy",
    "research",
    "serie a",
    "sources",
}
_GENERIC_ENTITY_TOKENS = {
    "about",
    "adeguamento",
    "affordable",
    "analysis",
    "advantages",
    "balanced",
    "best",
    "better",
    "budget",
    "build",
    "category",
    "choice",
    "check",
    "competitor",
    "considerations",
    "contents",
    "context",
    "codice",
    "current",
    "designed",
    "entry-level",
    "for",
    "feel",
    "high-quality",
    "guide",
    "guida",
    "how",
    "insights",
    "key",
    "lightest",
    "list",
    "lowest",
    "market",
    "mid-range",
    "new",
    "nuovo",
    "over",
    "portable",
    "premium",
    "price",
    "prezzo",
    "pros",
    "cons",
    "range",
    "results",
    "same",
    "service",
    "selezionare",
    "solutions",
    "supporto",
    "the",
    "this",
    "questo",
    "vat-inclusive",
    "wrap",
}


def _entity_id(name: str) -> str:
    digest = hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:16]
    return f"entity-{digest}"


def _entity_names(text: str) -> list[str]:
    names: list[str] = []
    for match in _NAME.finditer(text):
        value = re.sub(r"\s+", " ", match.group(0)).strip(" .,:;()[]")
        if not value or value.casefold() in _ENTITY_NOISE:
            continue
        if value.isdigit() or re.fullmatch(r"20\d{2}", value):
            continue
        tokens = value.split()
        normalized_tokens = [token.casefold().strip("'’-.") for token in tokens]
        # Numeric measurements and table headings are attributes, not entities.
        if tokens[0][0].isdigit() or all(
            token in _GENERIC_ENTITY_TOKENS for token in normalized_tokens
        ):
            continue
        if normalized_tokens[0] in _GENERIC_ENTITY_TOKENS:
            continue
        if len(set(normalized_tokens)) != len(normalized_tokens):
            continue
        # A capitalized sentence opener is usually prose, not an entity. Keep
        # it when it is a multi-token name, acronym, or recurs in the sentence.
        if match.start() == 0 and " " not in value and not value.isupper():
            continue
        if value not in names:
            names.append(value)
    return names[:12]


def _entity_signal(name: str) -> int:
    """Prefer stable identifiers and proper multi-token names over prose fragments."""
    tokens = name.split()
    has_number = any(any(char.isdigit() for char in token) for token in tokens)
    has_mixed_case = any(
        any(char.islower() for char in token[1:])
        and any(char.isupper() for char in token[1:])
        for token in tokens
    )
    has_acronym = any(token.isupper() and 2 <= len(token) <= 8 for token in tokens)
    return (
        (3 if has_number else 0)
        + (2 if has_mixed_case else 0)
        + (1 if has_acronym else 0)
        + (1 if len(tokens) >= 2 else -1)
    )


def _category(text: str, contract: ResearchContract) -> str:
    tokens = normalized_research_tokens(text)
    for quota in contract.deliverable.category_quotas:
        quota_tokens = normalized_research_tokens(quota.label)
        if quota_tokens and (
            tokens & quota_tokens
            or any(category_keys_match(token, quota.label) for token in tokens)
        ):
            return quota.label
    return ""


def _attribute_keys(metadata: dict, contract: ResearchContract, quote: str) -> list[str]:
    requirement_ids = {str(item) for item in metadata.get("requirement_ids", [])}
    matched = [
        goal.attribute_key
        for goal in contract.deliverable.attribute_goals
        if requirement_ids & set(goal.requirement_ids)
    ]
    if matched:
        return matched[:4]
    quote_tokens = normalized_research_tokens(quote)
    ranked: list[tuple[int, str]] = []
    for goal in contract.deliverable.attribute_goals:
        overlap = len(quote_tokens & normalized_research_tokens(goal.label))
        if overlap:
            ranked.append((overlap, goal.attribute_key))
    return [key for _, key in sorted(ranked, reverse=True)[:2]] or ["general_evidence"]


def build_entity_research_matrix(
    store: ResearchStore,
    run_id: uuid.UUID,
    *,
    contract: ResearchContract | None = None,
) -> EntityResearchMatrix:
    """Aggregate verified evidence by entity and requested attribute."""
    row = store.get_run_row(run_id)
    contract = contract or contract_from_snapshot(row.config_snapshot if row else None)
    if contract is None:
        matrix = EntityResearchMatrix()
        store.upsert_entity_research_matrix(run_id, matrix.model_dump(mode="json"))
        return matrix

    claims = {claim.id: claim for claim in store.list_claims(run_id)}
    snapshots = {item.id: item for item in store.list_snapshots_for_run(run_id)}
    sources = {source.id: source for source in store.list_sources(run_id)}
    fields_by_entity: dict[str, dict[str, list[EntityResearchField]]] = defaultdict(
        lambda: defaultdict(list)
    )
    name_by_id: dict[str, str] = {}
    category_by_id: dict[str, str] = {}

    for evidence in store.list_evidence(run_id):
        claim = claims.get(evidence.claim_id)
        if claim is None or claim.verification_status not in {
            ClaimVerificationStatus.VERIFIED,
            ClaimVerificationStatus.PARTIALLY_VERIFIED,
        }:
            continue
        snapshot = snapshots.get(evidence.snapshot_id)
        source = sources.get(snapshot.source_id) if snapshot else None
        names = _entity_names(evidence.quote)
        if not names and source is not None:
            names = _entity_names(source.title or "")[:3]
        metadata = dict(evidence.extraction_metadata or {})
        attribute_keys = _attribute_keys(metadata, contract, evidence.quote)
        category = _category(evidence.quote, contract)
        for name in names:
            entity_id = _entity_id(name)
            name_by_id[entity_id] = name
            if category:
                category_by_id[entity_id] = category
            for attribute_key in attribute_keys:
                fields_by_entity[entity_id][attribute_key].append(
                    EntityResearchField(
                        attribute_key=attribute_key,
                        value=evidence.quote[:8000],
                        confidence=float(evidence.confidence),
                        freshness=(snapshot.retrieved_at.isoformat() if snapshot else ""),
                        source_ids=[str(source.id)] if source else [],
                        evidence_ids=[str(evidence.id)],
                        requirement_ids=[str(item) for item in metadata.get("requirement_ids", [])][
                            :20
                        ],
                        status=(
                            MatrixFieldStatus.KNOWN
                            if claim.verification_status == ClaimVerificationStatus.VERIFIED
                            else MatrixFieldStatus.ESTIMATED
                        ),
                    )
                )

    entities: list[EntityResearchEntity] = []
    for entity_id, grouped in fields_by_entity.items():
        fields: list[EntityResearchField] = []
        for attribute_key, values in grouped.items():
            distinct_values = list(dict.fromkeys(item.value for item in values))
            source_ids = list(
                dict.fromkeys(source for item in values for source in item.source_ids)
            )
            evidence_ids = list(
                dict.fromkeys(evidence for item in values for evidence in item.evidence_ids)
            )
            requirement_ids = list(
                dict.fromkeys(req for item in values for req in item.requirement_ids)
            )
            fields.append(
                EntityResearchField(
                    attribute_key=attribute_key,
                    value="\n\n".join(distinct_values)[:8000],
                    confidence=max(item.confidence for item in values),
                    freshness=max((item.freshness for item in values), default=""),
                    source_ids=source_ids[:30],
                    evidence_ids=evidence_ids[:30],
                    requirement_ids=requirement_ids[:20],
                    status=(
                        MatrixFieldStatus.CONFLICTING
                        if len(distinct_values) > 1 and len(source_ids) > 1
                        else values[0].status
                    ),
                    uncertainty=(
                        "Multiple source-backed values require reconciliation."
                        if len(distinct_values) > 1 and len(source_ids) > 1
                        else ""
                    ),
                    conflict_state=(
                        MatrixConflictState.UNRESOLVED
                        if len(distinct_values) > 1 and len(source_ids) > 1
                        else MatrixConflictState.NONE
                    ),
                )
            )
        entities.append(
            EntityResearchEntity(
                entity_id=entity_id,
                entity_name=name_by_id[entity_id],
                entity_type=contract.deliverable.entity_type,
                category=category_by_id.get(entity_id, ""),
                stage="plausible" if len(fields) >= 2 else "candidate",
                fields=fields,
            )
        )

    entities.sort(
        key=lambda entity: (
            -_entity_signal(entity.entity_name),
            -len(entity.fields),
            entity.entity_name.casefold(),
        )
    )
    # Progressive narrowing is explicit and deterministic: retain the bounded
    # evidence-rich universe, while later report synthesis may focus on the top
    # viable subset requested by the deliverable.
    entities = entities[:200]
    plausible = sum(item.stage == "plausible" for item in entities)
    finalist_target = contract.deliverable.exact_item_count or min(10, len(entities))
    for entity in entities[: min(finalist_target, len(entities))]:
        if entity.stage == "plausible":
            entity.stage = "finalist"
    matrix = EntityResearchMatrix(
        entities=entities,
        attribute_goals=contract.deliverable.attribute_goals,
        candidate_count=len(entities),
        plausible_count=plausible,
        finalist_count=sum(item.stage == "finalist" for item in entities),
        fields_populated=sum(len(item.fields) for item in entities),
    )
    store.upsert_entity_research_matrix(run_id, matrix.model_dump(mode="json"))
    return matrix
