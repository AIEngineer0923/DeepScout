"""Targeted query planning for regulatory, entity, and hard-source research."""

from __future__ import annotations

import hashlib
import re

from deepscout_core.domain.contracts import (
    RequirementKind,
    ResearchContract,
    SourceConstraintMode,
)
from deepscout_core.domain.schemas import PlannerTask

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
    (re.compile(r"presidente della commissione europea", re.I), "President of the European Commission"),
    (re.compile(r"president of the european commission", re.I), "President of the European Commission"),
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
    namespaces = official_source_namespaces(contract) or ["ec.europa.eu", "commission.europa.eu", "europa.eu"]
    queries = [
        _site_query(f"{office} official biography leadership", namespaces[0]),
        _site_query("about president european commission college", namespaces[min(1, len(namespaces) - 1)]),
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
    ai_office = next((item for item in namespaces if "ai-office" in item), "digital-strategy.ec.europa.eu")
    return [
        _site_query(f"{goal} application date entered into force article transitional", legal_portal),
        _site_query("EU AI Act article 51 55 111 GPAI obligations application dates transitional", legal_portal),
        _site_query(f"{goal} enforcement date implementation timeline official guidance", policy_portal),
        _site_query("GPAI provider obligations code of practice transparency 2026 2027", ai_office),
        _site_query(f"{goal} obligations already applicable vs future transitional provisions", legal_portal),
    ]


def primary_legal_instrument_queries(contract: ResearchContract, *, article_hint: str = "") -> list[str]:
    goal = contract.primary_question[:160]
    legal_portal = "eur-lex.europa.eu"
    for domain in official_source_namespaces(contract):
        if "eur-lex" in domain:
            legal_portal = domain
            break
    article = f" {article_hint}" if article_hint else ""
    return [
        _site_query(f"{goal}{article} regulation text application dates transitional article", legal_portal),
    ]


def diversified_official_queries(
    contract: ResearchContract,
    requirement_text: str,
    *,
    intent: str,
) -> list[str]:
    """Bounded multi-namespace official search for hard source scopes."""
    namespaces = official_source_namespaces(contract)
    if not namespaces:
        return [f"{contract.primary_question[:140]} {requirement_text[:120]}"[:500]]
    base = requirement_text[:140]
    queries: list[str] = []
    for index, domain in enumerate(namespaces[:3]):
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


def contract_research_tasks(contract: ResearchContract) -> list[PlannerTask]:
    """Supplement planner tasks for entity lookup and regulatory temporal research."""
    tasks: list[PlannerTask] = []
    lowered = contract.primary_question.casefold()
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
        item.requirement_id in {"R_reg_now", "R_reg_later", "R_reg_apply", "R_reg_time", "R_timeline"}
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
    return tasks


def gap_queries_for_requirement(
    requirement,
    contract: ResearchContract,
    *,
    round_number: int,
) -> list[str]:
    if requirement.requirement_id == "R_president":
        return office_holder_queries(contract)
    if requirement.requirement_id in {"R_reg_now", "R_reg_current", "R_reg_apply"}:
        legal_portal = next(
            (item for item in official_source_namespaces(contract) if "eur-lex" in item),
            "eur-lex.europa.eu",
        )
        return [
            _site_query("legal basis application date GPAI providers 2026 regulation article", legal_portal),
            _site_query("enforcement date transitional provisions GPAI obligations official", legal_portal),
        ] + regulatory_temporal_queries(contract)[:1]
    if requirement.requirement_id in {"R_reg_later", "R_reg_time", "R_timeline"}:
        legal_portal = next(
            (item for item in official_source_namespaces(contract) if "eur-lex" in item),
            "eur-lex.europa.eu",
        )
        return [
            _site_query("transitional deadline GPAI providers comply by regulation article", legal_portal),
            _site_query("legal basis future obligations GPAI systemic risk 2027 2028", legal_portal),
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
    return [f"{contract.primary_question[:140]} {requirement.text[:160]}"[:500]]
