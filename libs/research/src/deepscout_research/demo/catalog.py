"""Curated public demo catalog metadata."""

from __future__ import annotations

from typing import TypedDict


class DemoCatalogEntry(TypedDict):
    slug: str
    goal: str
    category: str
    title: str
    summary: str
    why_interesting: str
    research_mode: str


DEMO_CATALOG: tuple[DemoCatalogEntry, ...] = (
    {
        "slug": "rag-architectures-2026",
        "goal": (
            "Compare RAG, GraphRAG, and long-context retrieval architectures for a production "
            "knowledge assistant in 2026, including retrieval quality, operational complexity, "
            "evaluation, scalability, and appropriate use cases. Prefer primary technical "
            "documentation and authoritative research sources."
        ),
        "category": "technical",
        "title": "RAG vs GraphRAG vs long-context (2026)",
        "summary": "Architecture comparison for production knowledge assistants.",
        "why_interesting": "Shows evidence-heavy technical synthesis from primary docs.",
        "research_mode": "standard",
    },
    {
        "slug": "battery-chemistry-tradeoffs",
        "goal": (
            "Research the trade-offs between NMC and LFP battery chemistries for grid storage, "
            "including energy density, cycle life, thermal safety, cost trends, and supply-chain "
            "constraints. Task B must depend on the quantitative comparison produced in Task A."
        ),
        "category": "multi-hop",
        "title": "NMC vs LFP: multi-hop dependency chain",
        "summary": "Planner DAG with semantic depends_on between quantitative tasks.",
        "why_interesting": "Demonstrates real multi-hop decomposition and critical path.",
        "research_mode": "standard",
    },
    {
        "slug": "vaccine-efficacy-uncertainty",
        "goal": (
            "Summarize scientific evidence on seasonal influenza vaccine effectiveness across "
            "age groups, highlighting methodological differences, confidence intervals, and "
            "contradictory findings between observational and randomized studies."
        ),
        "category": "contradiction",
        "title": "Vaccine effectiveness under uncertainty",
        "summary": "Contradictory evidence and uncertainty across study designs.",
        "why_interesting": "Shows contradiction detection without forced conclusions.",
        "research_mode": "standard",
    },
    {
        "slug": "eu-ai-act-gpai-providers",
        "goal": (
            "Explain how the EU AI Act classifies general-purpose AI systems for providers as of "
            "2026, including obligations, timelines, and official guidance. Use current regulatory "
            "sources and institutional publications."
        ),
        "category": "regulatory",
        "title": "EU AI Act GPAI provider obligations",
        "summary": "Current regulatory synthesis with provenance to official sources.",
        "why_interesting": "Demonstrates fresh web research with institutional sources.",
        "research_mode": "quick",
    },
    {
        "slug": "transformer-attention-evidence",
        "goal": (
            "Review peer-reviewed evidence on scaling laws for transformer attention in large "
            "language models, citing primary papers, official datasets, and "
            "reproducible benchmarks."
        ),
        "category": "scientific",
        "title": "Transformer scaling evidence review",
        "summary": "Paper-first evidence chain with quote resolution.",
        "why_interesting": "Evidence-heavy scientific workflow with citations.",
        "research_mode": "deep",
    },
    {
        "slug": "event-driven-research-runtime",
        "goal": (
            "Compare event-driven workers versus request/response APIs for long-running research "
            "jobs, focusing on reliability, backpressure, observability, and operational cost."
        ),
        "category": "technical",
        "title": "Event-driven vs request/response runtimes",
        "summary": "Systems research on async job orchestration patterns.",
        "why_interesting": "Shows engineering trade-off analysis with diverse sources.",
        "research_mode": "quick",
    },
)

DEMO_BY_SLUG = {item["slug"]: item for item in DEMO_CATALOG}
