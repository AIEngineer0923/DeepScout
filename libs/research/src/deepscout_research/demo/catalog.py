"""Curated public demo catalog metadata."""

from __future__ import annotations

from typing import TypedDict

from deepscout_core.domain.budget import ResearchBudget


class DemoCatalogEntry(TypedDict):
    slug: str
    goal: str
    category: str
    title: str
    summary: str
    why_interesting: str
    research_mode: str


def curated_demo_budget(mode: str) -> ResearchBudget:
    """Bounded operator profile — same orchestrator, higher ceilings than quick runs."""
    if mode == "deep":
        return ResearchBudget(
            max_iterations=3,
            max_wall_time_seconds=720,
            max_total_tokens=140_000,
            max_cost_usd=4.0,
            max_sources=14,
            max_tool_calls=28,
        )
    return ResearchBudget(
        max_iterations=5,
        max_wall_time_seconds=900,
        max_total_tokens=160_000,
        max_cost_usd=5.0,
        max_sources=18,
        max_tool_calls=36,
    )


DEMO_CATALOG: tuple[DemoCatalogEntry, ...] = (
    {
        "slug": "rag-architecture-2026",
        "goal": (
            "Compare hybrid RAG, GraphRAG, and long-context retrieval architectures for a "
            "production knowledge assistant in 2026. Evaluate retrieval quality, provenance, "
            "update cost, operational complexity, latency, security, evaluation strategy, and "
            "the workloads for which each architecture is most appropriate. Prefer original "
            "papers and official framework or vendor documentation."
        ),
        "category": "technical",
        "title": "Hybrid RAG vs GraphRAG vs long-context (2026)",
        "summary": "Architecture trade-offs for production knowledge assistants.",
        "why_interesting": "Technical synthesis from primary documentation and papers.",
        "research_mode": "standard",
    },
    {
        "slug": "multi-hop-research",
        "goal": (
            "Identify who currently serves as President of the European Commission, then "
            "determine what concrete general-purpose AI model obligations the European "
            "Commission has published guidance on for providers in 2026. The second task "
            "must depend on correctly identifying the office holder in the first task. Use "
            "only official EU institutional sources."
        ),
        "category": "multi-hop",
        "title": "True multi-hop EU institutional research",
        "summary": "Semantic dependency between identification and policy research tasks.",
        "why_interesting": "Demonstrates planner DAG with depends_on edges.",
        "research_mode": "standard",
    },
    {
        "slug": "ev-battery-evidence",
        "goal": (
            "Compare the current evidence on LFP and high-nickel NMC battery chemistries for "
            "passenger EVs, focusing on cycle life, energy density, thermal safety, cost "
            "drivers, and how pack-level engineering changes the practical trade-off. Prefer "
            "peer-reviewed work, DOE or national lab reports, and credible manufacturer "
            "engineering data."
        ),
        "category": "scientific",
        "title": "LFP vs NMC evidence for passenger EVs",
        "summary": "Evidence-heavy comparison of battery chemistries.",
        "why_interesting": "Scientific sources with provenance and citations.",
        "research_mode": "standard",
    },
    {
        "slug": "eu-ai-act-gpai-2026",
        "goal": (
            "Explain the obligations that the EU AI Act imposes in 2026 on providers of "
            "general-purpose AI models, distinguishing obligations already applicable from "
            "later obligations, and identify authoritative Commission or EU sources "
            "supporting each conclusion. Prioritize EUR-Lex, European Commission, and EU AI "
            "Office publications."
        ),
        "category": "regulatory",
        "title": "EU AI Act GPAI provider obligations (2026)",
        "summary": "Regulatory synthesis from official EU sources.",
        "why_interesting": "Current institutional web research with provenance.",
        "research_mode": "standard",
    },
    {
        "slug": "ev-lifecycle-evidence",
        "goal": (
            "Compare credible estimates of the lifecycle greenhouse-gas impact of "
            "battery-electric vehicles versus comparable combustion vehicles in Europe, and "
            "explain why reputable studies produce different break-even estimates. Prefer "
            "ICCT, IEA, peer-reviewed research, and European institutional sources."
        ),
        "category": "contradiction",
        "title": "EV lifecycle GHG evidence under uncertainty",
        "summary": "Methodological differences across authoritative lifecycle studies.",
        "why_interesting": "Uncertainty and contradiction without forced conclusions.",
        "research_mode": "standard",
    },
)

DEMO_BY_SLUG = {item["slug"]: item for item in DEMO_CATALOG}
