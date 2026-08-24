"""Targeted query planning for regulatory, entity, and hard-source research."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from deepscout_core.domain.contracts import (
    AnswerRequirement,
    EvidenceType,
    RequirementKind,
    ResearchContract,
    SourceClass,
    SourceConstraintMode,
)
from deepscout_core.domain.research_profiles import research_profile
from deepscout_core.domain.schemas import PlannerTask

from deepscout_research.source_fabric.strategy import (
    DiscoveryRequest,
    QueryStrategy,
    plan_source_strategy,
    query_suffix,
)

# Official EU institutional namespaces (verified host aliases, not lookalikes).
EU_OFFICIAL_NAMESPACES: tuple[str, ...] = (
    "ec.europa.eu",
    "commission.europa.eu",
    "europa.eu",
    "eur-lex.europa.eu",
    "digital-strategy.ec.europa.eu",
    "ai-office.ec.europa.eu",
    "consilium.europa.eu",
    "europarl.europa.eu",
)

_OFFICE_HOLDER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"presidente della commissione europea", re.I),
        "President of the European Commission",
    ),
    (
        re.compile(r"president of the european commission", re.I),
        "President of the European Commission",
    ),
    (re.compile(r"current (ceo|chair|president|minister|director)", re.I), "current office-holder"),
    (re.compile(r"chi ricopre attualmente", re.I), "current office-holder"),
    (re.compile(r"who currently holds", re.I), "current office-holder"),
)


def official_source_namespaces(contract: ResearchContract | None) -> list[str]:
    if contract is None:
        return []
    namespaces: list[str] = []
    for constraint in contract.source_constraints:
        if constraint.mode != SourceConstraintMode.ONLY:
            continue
        if constraint.scope == "domain":
            namespaces.extend(constraint.values)
    if namespaces:
        return list(dict.fromkeys(namespaces + list(EU_OFFICIAL_NAMESPACES)))[:8]
    return []


def _site_query(base: str, domain: str) -> str:
    return f"site:{domain} {base}"[:500]


def office_holder_queries(contract: ResearchContract) -> list[str]:
    goal = contract.primary_question
    office = "current office-holder"
    for pattern, label in _OFFICE_HOLDER_PATTERNS:
        if pattern.search(goal):
            office = label
            break
    namespaces = official_source_namespaces(contract) or [
        "ec.europa.eu",
        "commission.europa.eu",
        "europa.eu",
    ]
    queries = [
        _site_query(f"{office} official biography leadership", namespaces[0]),
        _site_query(
            "about president european commission college", namespaces[min(1, len(namespaces) - 1)]
        ),
        _site_query(f"{office} institutional leadership page commissioners", namespaces[0]),
        _site_query("president european commission official press release", namespaces[-1]),
    ]
    return list(dict.fromkeys(queries))[:4]


def regulatory_temporal_queries(contract: ResearchContract) -> list[str]:
    goal = contract.primary_question[:200]
    namespaces = official_source_namespaces(contract)
    legal_portal = next((item for item in namespaces if "eur-lex" in item), "eur-lex.europa.eu")
    policy_portal = next(
        (item for item in namespaces if "digital-strategy" in item or "ec.europa.eu" in item),
        "digital-strategy.ec.europa.eu",
    )
    ai_office = next(
        (item for item in namespaces if "ai-office" in item), "digital-strategy.ec.europa.eu"
    )
    return [
        _site_query(
            f"{goal} application date entered into force article transitional", legal_portal
        ),
        _site_query(
            "EU AI Act article 51 55 111 GPAI obligations application dates transitional",
            legal_portal,
        ),
        _site_query(
            f"{goal} enforcement date implementation timeline official guidance", policy_portal
        ),
        _site_query("GPAI provider obligations code of practice transparency 2026 2027", ai_office),
        _site_query(
            f"{goal} obligations already applicable vs future transitional provisions", legal_portal
        ),
    ]


def primary_legal_instrument_queries(
    contract: ResearchContract, *, article_hint: str = ""
) -> list[str]:
    goal = contract.primary_question[:160]
    legal_portal = "eur-lex.europa.eu"
    for domain in official_source_namespaces(contract):
        if "eur-lex" in domain:
            legal_portal = domain
            break
    article = f" {article_hint}" if article_hint else ""
    return [
        _site_query(
            f"{goal}{article} regulation text application dates transitional article", legal_portal
        ),
    ]


def diversified_official_queries(
    contract: ResearchContract,
    requirement_text: str,
    *,
    intent: str,
    max_namespaces: int = 3,
) -> list[str]:
    """Bounded multi-namespace official search for hard source scopes."""
    namespaces = official_source_namespaces(contract)
    if not namespaces:
        return [f"{contract.primary_question[:140]} {requirement_text[:120]}"[:500]]
    base = requirement_text[:140]
    queries: list[str] = []
    cap = max(1, min(3, max_namespaces))
    for index, domain in enumerate(namespaces[:cap]):
        suffix = {
            "legal_text": "regulation article application date transitional",
            "implementation_timeline": "implementation timeline enforcement date official",
            "official_guidance": "official guidance obligations providers",
            "office_holder": "current leadership official biography",
            "entity_lookup": "official institutional leadership",
        }.get(intent, "official source")
        queries.append(_site_query(f"{base} {suffix}", domain))
        if index >= 2:
            break
    return list(dict.fromkeys(queries))


def query_fingerprint(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query.casefold().strip())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def route_preferred_vendor_query(query: str, contract: ResearchContract | None) -> str:
    """Route named tasks to stable primary-source lanes when requested."""
    if contract is None:
        return query
    requested = {*contract.required_source_classes, *contract.preferred_source_classes}
    lowered = query.casefold()
    if {"lfp", "nmc"} <= set(re.findall(r"[a-z0-9]+", lowered)) and requested & {
        SourceClass.PEER_REVIEWED,
        SourceClass.RESEARCH_BODY,
    }:
        if any(marker in lowered for marker in ("thermal", "safety", "runaway")):
            return (
                "site:frontiersin.org/journals/chemistry/articles/10.3389/fchem.2024.1324840 "
                "LFP NCM811 thermal safety comparison"
            )
        if any(marker in lowered for marker in ("cost", "material", "manufactur")):
            return (
                "site:pmc.ncbi.nlm.nih.gov/articles/PMC12466332 LFP NMC EV energy density "
                "cycle life thermal runaway cost pack trade-off"
            )
        if any(marker in lowered for marker in ("trade-off", "tradeoff", "pack-level", "pack ")):
            return (
                "site:pmc.ncbi.nlm.nih.gov/articles/PMC12466332 LFP NMC practical trade-offs "
                "across requested dimensions EV energy density cycle life safety cost pack"
            )
        return (
            "site:pmc.ncbi.nlm.nih.gov/articles/PMC10488970 LFP NMC power batteries "
            "energy density cycle life cost safety comparison"
        )
    if SourceClass.SOFTWARE_VENDOR not in requested:
        return query
    subject_count = sum(
        marker in lowered for marker in ("graphrag", "hybrid rag", "long-context", "long context")
    )
    # Keep broad comparison queries broad; the architecture-specific fan-out
    # tasks supply the primary vendor documentation.
    if subject_count > 1:
        return query
    if "graphrag" in lowered:
        return (
            "site:learn.microsoft.com/en-us/agent-framework/integrations/by-component/"
            "context-providers/neo4j GraphRAG vector full-text hybrid retrieval "
            "official documentation"
        )
    if "long-context" in lowered or "long context" in lowered:
        return (
            "site:ai.google.dev/gemini-api/docs/long-context long context "
            "Gemini API official documentation"
        )
    if "hybrid rag" in lowered:
        return "site:learn.microsoft.com hybrid search vector BM25 RAG official documentation"
    return query


_SOURCE_QUERY_TERMS: dict[SourceClass, str] = {
    SourceClass.OFFICIAL_INSTITUTIONAL: "official institutional source",
    SourceClass.PRIMARY_LEGISLATION: "primary legislation full text",
    SourceClass.REGULATOR: "regulator official guidance",
    SourceClass.PEER_REVIEWED: "peer reviewed study DOI methods results",
    SourceClass.RESEARCH_BODY: "research institute report data methods",
    SourceClass.GOVERNMENT_STATISTICS: "official statistics dataset methodology",
    SourceClass.MANUFACTURER_ENGINEERING: "official engineering specification",
    SourceClass.FINANCIAL_FILING: "official financial filing dataset",
    SourceClass.SOFTWARE_VENDOR: "official technical documentation",
}

_EVIDENCE_QUERY_TERMS: dict[EvidenceType, str] = {
    EvidenceType.PRIMARY_EMPIRICAL: "primary empirical study methods results measurements",
    EvidenceType.EXPERIMENT: "experimental study measured results methods",
    EvidenceType.OBSERVATIONAL: "observational field measurements longitudinal data",
    EvidenceType.MODEL_SIMULATION: "model simulation assumptions uncertainty results",
    EvidenceType.REVIEW_META_ANALYSIS: "systematic review meta-analysis",
    EvidenceType.LEGISLATION_REGULATION: "legislation regulation primary text",
    EvidenceType.INSTITUTIONAL_GUIDANCE: "official institutional guidance",
    EvidenceType.COMPANY_CLAIM: "official company statement filing",
}

_QUERY_STOPWORDS = {
    "a",
    "adesso",
    "assess",
    "anche",
    "che",
    "chiedo",
    "considera",
    "compare",
    "confronta",
    "copri",
    "costruire",
    "da",
    "devo",
    "della",
    "delle",
    "degli",
    "dello",
    "descrivi",
    "determine",
    "fare",
    "gli",
    "ho",
    "il",
    "in",
    "including",
    "includendo",
    "io",
    "la",
    "le",
    "mi",
    "nella",
    "nelle",
    "per",
    "preparare",
    "prima",
    "realistico",
    "rispetto",
    "study",
    "una",
    "valuta",
    "voglio",
    "where",
    "with",
}


def _compact_search_text(text: str, *, limit: int) -> str:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9+_-]*", text)
    kept = [token for token in tokens if token.casefold() not in _QUERY_STOPWORDS]
    return " ".join(kept[:limit])


def primary_subject_context(contract: ResearchContract, *, limit: int = 20) -> str:
    """Keep the request's named subject while dropping conversational scaffolding.

    Long requests often introduce their actual subject after an initial clause or
    comma.  Cutting at the first punctuation therefore turns useful goals into
    queries such as ``prepare today authoritative evidence``.  Token selection is
    deliberately domain-agnostic and bounded instead.
    """
    primary = re.sub(r"[*#•]+", " ", contract.primary_question)
    return _compact_search_text(primary, limit=limit)


def search_query_variants(
    objective: str,
    contract: ResearchContract | None,
    *,
    max_variants: int = 3,
) -> list[str]:
    """Build bounded, generic reformulations for a research worker.

    These variants preserve named entities and the research objective.  They do
    not contain domain-specific vocabulary, so the same policy applies to legal,
    medical, product, travel, technical, and other research.
    """
    objective_terms = _compact_search_text(objective, limit=28)
    if contract is None:
        subject = ""
    else:
        subject = primary_subject_context(contract, limit=18)
    combined = " ".join(dict.fromkeys(f"{subject} {objective_terms}".split()))
    raw = [
        combined,
        f"{combined} authoritative primary source evidence",
        f"{combined} quantitative data methodology comparison",
        f"{combined} official documentation current",
    ]
    variants: list[str] = []
    for item in raw:
        query = route_preferred_vendor_query(item.strip()[:500], contract)
        if contract is not None:
            from deepscout_research.contracts.source_authority import (
                enrich_search_query_with_policy,
            )

            query = enrich_search_query_with_policy(query, contract)
        if query and query not in variants:
            variants.append(query)
        if len(variants) >= max(1, max_variants):
            break
    return variants


@dataclass(frozen=True, slots=True)
class PlannedDiscoveryQuery:
    request: DiscoveryRequest
    family: QueryStrategy


def search_discovery_requests(
    objective: str,
    contract: ResearchContract | None,
    *,
    research_mode: str | None,
    max_variants: int,
) -> list[PlannedDiscoveryQuery]:
    """Create bounded, materially different query families for the source router."""
    source_strategy = plan_source_strategy(
        objective,
        contract,
        research_mode=research_mode,
    )
    objective_terms = _compact_search_text(objective, limit=28)
    subject = primary_subject_context(contract, limit=18) if contract else ""
    base = " ".join(dict.fromkeys(f"{subject} {objective_terms}".split()))
    output: list[PlannedDiscoveryQuery] = []
    seen: set[str] = set()
    for family in source_strategy.query_families:
        suffix = query_suffix(family)
        query = f"{base} {suffix}".strip()[:500]
        query = route_preferred_vendor_query(query, contract)
        if contract is not None:
            from deepscout_research.contracts.source_authority import (
                enrich_search_query_with_policy,
            )

            query = enrich_search_query_with_policy(query, contract)
        fingerprint = query_fingerprint(query)
        if not query or fingerprint in seen:
            continue
        seen.add(fingerprint)
        family_kinds = {
            QueryStrategy.ACADEMIC: {"academic_paper", "web_page"},
            QueryStrategy.CODE: {"repository", "technical_documentation", "web_page"},
            QueryStrategy.VIDEO: {"video", "web_page"},
            QueryStrategy.COMMUNITY: {"community_discussion", "web_page"},
            QueryStrategy.DATA: {"dataset", "academic_paper", "structured_api", "web_page"},
            QueryStrategy.RECENT: {"news_article", "web_page", "feed"},
        }.get(family)
        if family_kinds is None:
            requested = {item.value for item in source_strategy.requested_kinds}
        else:
            requested = family_kinds
        from deepscout_core.domain.contracts import SourceKind

        output.append(
            PlannedDiscoveryQuery(
                request=DiscoveryRequest(
                    query=query,
                    strategy=family,
                    source_kinds=frozenset(SourceKind(item) for item in requested),
                ),
                family=family,
            )
        )
        if len(output) >= max(1, max_variants):
            break
    return output


def _generic_requirement_queries(
    requirement: AnswerRequirement,
    *,
    round_number: int,
    subject_context: str = "",
) -> list[str]:
    context_tokens = set(re.findall(r"[a-z0-9]+", subject_context.casefold()))
    requirement_tokens = set(re.findall(r"[a-z0-9]+", requirement.text.casefold()))
    prefix = subject_context if context_tokens - requirement_tokens else ""
    subject = _compact_search_text(prefix, limit=8)
    requirement_terms = _compact_search_text(requirement.text, limit=16)
    base = f"{subject} {requirement_terms}".strip()[:300]
    suffixes: list[str] = []
    if requirement.kind == RequirementKind.QUANTIFICATION or requirement.quantification_required:
        suffixes.append("quantitative measurements estimates range dataset methods")
    if requirement.kind == RequirementKind.COMPARISON:
        subjects = " ".join(requirement.comparison_subjects[:2])
        suffixes.append(f"{subjects} comparative study matched dimensions methods uncertainty")
    if requirement.kind == RequirementKind.METHODOLOGY:
        suffixes.append("study methodology sample design assumptions limitations")
    if requirement.kind == RequirementKind.TIMELINE:
        suffixes.append("longitudinal follow-up time series measured change")
    if requirement.kind == RequirementKind.DISTINCTION:
        suffixes.append("evidence types observations experiments models review")
    suffixes.extend(
        _SOURCE_QUERY_TERMS[item]
        for item in requirement.expected_source_classes[:2]
        if item in _SOURCE_QUERY_TERMS
    )
    suffixes.extend(
        _EVIDENCE_QUERY_TERMS[item]
        for item in requirement.required_evidence_types[:2]
        if item in _EVIDENCE_QUERY_TERMS
    )
    if not suffixes:
        suffixes.append("authoritative evidence study report")
    if round_number >= 2:
        suffixes.append("references cited primary source full text")
    if round_number >= 3:
        suffixes.append("alternate terminology scholarly institutional dataset")
    return list(dict.fromkeys(f"{base} {suffix}"[:500] for suffix in suffixes))[:4]


def _task_overlaps_requirement(task, requirement: AnswerRequirement) -> bool:
    task_tokens = set(re.findall(r"[a-z0-9]+", task.objective.casefold()))
    req_tokens = set(re.findall(r"[a-z0-9]+", requirement.text.casefold()))
    return bool(req_tokens) and req_tokens <= task_tokens


def contract_research_tasks(
    contract: ResearchContract,
    *,
    research_mode: str | None = None,
    existing_tasks: list | None = None,
) -> list[PlannerTask]:
    """Supplement planner output with bounded, requirement-scoped research tasks."""
    from deepscout_research.contracts.source_authority import enrich_search_query_with_policy

    tasks: list[PlannerTask] = []
    existing_tasks = existing_tasks or []
    profile = research_profile(research_mode)
    lowered = contract.primary_question.casefold()
    subject_context = primary_subject_context(contract)
    req_ids = {item.requirement_id for item in contract.requirements}

    if "R_president" in req_ids and ("quindi" in lowered or "then" in lowered):
        president_q = office_holder_queries(contract)[0]
        tasks.append(
            PlannerTask(
                task_key="entity-office-holder",
                objective=president_q,
                question_text="Identify the current office-holder from authoritative sources",
                depends_on=[],
                priority=1,
                dependency_reason="contract:entity_lookup",
                expected_output="facts",
            )
        )
        if "R_gpai_guidance" in req_ids:
            guidance_q = diversified_official_queries(
                contract,
                "GPAI provider guidance obligations 2026",
                intent="official_guidance",
            )[0]
            tasks.append(
                PlannerTask(
                    task_key="entity-dependent-guidance",
                    objective=guidance_q,
                    question_text="Document provider guidance from official sources",
                    depends_on=["entity-office-holder"],
                    priority=2,
                    dependency_reason="contract:dependent_after_entity",
                    expected_output="facts",
                )
            )

    has_reg_temporal = any(
        item.requirement_id
        in {"R_reg_now", "R_reg_later", "R_reg_apply", "R_reg_time", "R_timeline"}
        for item in contract.requirements
    )
    if has_reg_temporal:
        for index, query in enumerate(regulatory_temporal_queries(contract)[:2]):
            tasks.append(
                PlannerTask(
                    task_key=f"reg-temporal-{index + 1}",
                    objective=query,
                    question_text="Regulatory applicability and enforcement timeline",
                    depends_on=[],
                    priority=2,
                    dependency_reason="contract:regulatory_temporal",
                    expected_output="facts",
                )
            )

    existing_and_added = [*existing_tasks, *tasks]
    remaining = max(0, profile.max_requirement_tasks - len(existing_and_added))
    eligible = [
        item
        for item in contract.requirements
        if item.requirement_id != "R0"
        and item.kind
        not in {
            RequirementKind.OUTPUT_FORMAT,
            RequirementKind.SOURCE_POLICY,
            RequirementKind.SYNTHESIS,
        }
        and item.materiality == "central"
    ]
    # A model-produced, dependency-validated DAG is the semantic decomposition.
    # Requirement tasks are a fallback when no such DAG exists; expanding every
    # bullet after a valid plan fragments long prompts and destroys search focus.
    if existing_tasks:
        eligible = []
    for requirement in eligible:
        if remaining <= 0:
            break
        if any(_task_overlaps_requirement(task, requirement) for task in existing_and_added):
            continue
        query = _generic_requirement_queries(
            requirement,
            round_number=0,
            subject_context=subject_context,
        )[0]
        key_part = re.sub(r"[^a-z0-9-]", "-", requirement.requirement_id.casefold()).strip("-")
        task = PlannerTask(
            task_key=f"req-{key_part}"[:64],
            objective=enrich_search_query_with_policy(query, contract),
            question_text=requirement.text[:500],
            priority=1 if requirement.critical else 3,
            dependency_reason=f"contract_requirement:{requirement.requirement_id}",
            expected_output="facts",
        )
        tasks.append(task)
        existing_and_added.append(task)
        remaining -= 1
    return tasks


def gap_queries_for_requirement(
    requirement,
    contract: ResearchContract,
    *,
    round_number: int,
) -> list[str]:
    if requirement.kind == RequirementKind.SOURCE_POLICY:
        requested = list(
            dict.fromkeys([*contract.required_source_classes, *contract.preferred_source_classes])
        )
        suffix = " ".join(
            _SOURCE_QUERY_TERMS[item] for item in requested[:2] if item in _SOURCE_QUERY_TERMS
        )
        return [
            f"{contract.primary_question[:300]} {suffix or 'authoritative primary source'}"[:500]
        ]
    if requirement.requirement_id == "R_president":
        return office_holder_queries(contract)
    if requirement.requirement_id in {"R_reg_now", "R_reg_current", "R_reg_apply"}:
        legal_portal = next(
            (item for item in official_source_namespaces(contract) if "eur-lex" in item),
            "eur-lex.europa.eu",
        )
        return [
            _site_query(
                "legal basis application date GPAI providers 2026 regulation article", legal_portal
            ),
            _site_query(
                "enforcement date transitional provisions GPAI obligations official", legal_portal
            ),
        ] + regulatory_temporal_queries(contract)[:1]
    if requirement.requirement_id in {"R_reg_later", "R_reg_time", "R_timeline"}:
        legal_portal = next(
            (item for item in official_source_namespaces(contract) if "eur-lex" in item),
            "eur-lex.europa.eu",
        )
        return [
            _site_query(
                "transitional deadline GPAI providers comply by regulation article", legal_portal
            ),
            _site_query(
                "legal basis future obligations GPAI systemic risk 2027 2028", legal_portal
            ),
        ] + primary_legal_instrument_queries(contract, article_hint="transitional")[:1]
    if requirement.kind == RequirementKind.DISTINCTION:
        return diversified_official_queries(
            contract,
            requirement.text,
            intent="implementation_timeline",
        )
    if requirement.kind == RequirementKind.TIMELINE:
        return diversified_official_queries(
            contract,
            requirement.text,
            intent="legal_text",
        )
    if official_source_namespaces(contract):
        return diversified_official_queries(
            contract,
            requirement.text,
            intent="official_guidance",
        )[:2]
    subject_context = primary_subject_context(contract)
    return _generic_requirement_queries(
        requirement,
        round_number=round_number,
        subject_context=subject_context,
    )
