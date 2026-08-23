#!/usr/bin/env python3
"""Live, domain-neutral validation for requirement-complete research modes."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from deepscout_core.domain.contracts import AuthorityClass
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_persistence.session import dispose_all_engines, get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.contracts.source_authority import classify_source_authority
from deepscout_research.langsmith_env import configure_langsmith_env
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.phases.final_critic import run_final_answer_critic
from deepscout_research.runtime.config_snapshot import build_config_snapshot
from deepscout_research.search.tavily import TavilyWebSearchProvider

CASES = {
    "deep_sea": (
        "Valuta criticamente il deep-sea mining di noduli polimetallici. Copri composizione "
        "mineraria e contributo realistico all'offerta globale di Ni, Co, Mn e Cu; tecnologie "
        "di raccolta, riser e trattamento; impatti ecologici osservati distinguendoli da "
        "esperimenti, modelli e posizioni istituzionali; recupero a 1, 10 e 20+ anni; misure "
        "quantitative su collector tracks, sediment plumes, discharge, biodiversita bentonica, "
        "densita degli organismi, sedimentazione e water column. Confronta deep-sea e terrestrial "
        "mining, descrivi lo stato normativo e il ruolo ISA nel 2026, studi discordanti, metodi, "
        "limiti e incertezze. Concludi SUPPORTED, PARTIALLY SUPPORTED o INSUFFICIENT EVIDENCE. "
        "Preferisci letteratura peer-reviewed primaria e fonti istituzionali ufficiali."
    ),
    "scientific": (
        "Assess whether managed retreat improves long-term coastal flood resilience. Compare it "
        "with seawalls using observed outcomes, quantitative loss and displacement measures, "
        "study methods, distributional impacts, and conflicting evidence. Prefer primary "
        "peer-reviewed studies and official scientific agencies; state material evidence gaps."
    ),
    "market": (
        "Assess the 2024-2026 European heat-pump market: quantify unit sales and growth where "
        "credible, identify demand drivers and constraints, compare major national markets, and "
        "distinguish official statistics from industry estimates. Explain disagreements and gaps."
    ),
    "institutional": (
        "Explain how the International Court of Justice was created, identify the primary legal "
        "instruments and institutional predecessors, compare the PCIJ and ICJ mandates, and "
        "separate contemporaneous primary records from later historical interpretation."
    ),
    "no_answer": (
        "Determine the exact global number of individual wild earthworms alive on 1 January "
        "1900, with a primary contemporaneous census and a reproducible uncertainty interval. "
        "Do not substitute modern estimates; report insufficient evidence when warranted."
    ),
}


def _metrics(store: ResearchStore, run_id, case: str, mode: str, latency_s: float) -> dict:
    row = store.get_run_row(run_id)
    contract = contract_from_snapshot(row.config_snapshot if row else None)
    coverage = evaluate_coverage(store, run_id, contract) if contract else None
    critic = run_final_answer_critic(store, run_id)
    sources = store.list_sources(run_id)
    classes = Counter(
        classify_source_authority(url=item.canonical_url, title=item.title).source_class.value
        for item in sources
    )
    entries = coverage.entries if coverage else []
    material = (
        [item for item in contract.requirements if item.materiality == "central"]
        if contract
        else []
    )
    material_ids = {item.requirement_id for item in material}
    supported = sum(
        item.requirement_id in material_ids and item.status.value == "supported" for item in entries
    )
    partial = sum(
        item.requirement_id in material_ids and item.status.value == "partial" for item in entries
    )
    quantitative = [item for item in material if item.quantification_required]
    quantitative_supported = sum(
        item.requirement_id in {requirement.requirement_id for requirement in quantitative}
        and item.status.value == "supported"
        for item in entries
    )
    report = store.get_report(run_id)
    markdown = report.body_markdown if report else ""
    bibliography_headings = len(
        re.findall(r"(?im)^#{1,6}\s+(?:sources cited|fonti citate)\s*$", markdown)
    )
    run = store.get_run(run_id)
    usage = run.usage if run else None
    return {
        "case": case,
        "mode": mode,
        "run_id": str(run_id),
        "status": run.status.value if run else "missing",
        "termination_reason": run.termination_reason if run else None,
        "requirements": len(contract.requirements) if contract else 0,
        "material_supported": supported,
        "material_partial": partial,
        "material_total": len(material),
        "material_gaps": coverage.material_gaps if coverage else [],
        "gap_causes": Counter(
            item.gap_cause.value if item.gap_cause else "none" for item in entries
        ),
        "sources": len(sources),
        "source_classes": classes,
        "primary_source_ratio": round(
            sum(
                classify_source_authority(
                    url=item.canonical_url,
                    title=item.title,
                ).authority_class
                == AuthorityClass.PRIMARY
                for item in sources
            )
            / len(sources),
            3,
        )
        if sources
        else 0.0,
        "snapshots": len(store.list_snapshots_for_run(run_id)),
        "claims": len(store.list_claims(run_id)),
        "evidence": len(store.list_evidence(run_id)),
        "quantitative_supported": quantitative_supported,
        "quantitative_total": len(quantitative),
        "corrective_rounds": (row.config_snapshot or {}).get("coverage_research_rounds", 0)
        if row
        else 0,
        "critic_verdict": critic.verdict.value,
        "critic_reason_codes": critic.reason_codes,
        "bibliography_headings": bibliography_headings,
        "report_chars": len(markdown),
        "tokens": usage.total_tokens if usage else None,
        "cost_usd": usage.cost_usd if usage else None,
        "latency_s": round(latency_s, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", choices=CASES, dest="cases")
    parser.add_argument(
        "--mode", action="append", choices=("quick", "standard", "deep"), dest="modes"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/deepscout-research-completeness-live.json")
    )
    args = parser.parse_args()
    cases = args.cases or list(CASES)
    modes = args.modes or ["quick", "standard", "deep"]
    settings = configure_langsmith_env().model_copy(
        update={"research_workers_inline": True, "research_use_legacy_path": False}
    )
    results = {"started_at": datetime.now(UTC).isoformat(), "runs": []}
    try:
        with TavilyWebSearchProvider(settings) as search:
            for case in cases:
                for mode in modes:
                    session = get_session_factory(settings.database_url)()
                    store = ResearchStore(session)
                    try:
                        snapshot = {
                            **build_config_snapshot(settings),
                            "benchmark": "research_completeness_live_v1",
                            "case": case,
                            "mode": mode,
                        }
                        run = store.create_run(
                            ResearchRunCreate(
                                goal=CASES[case],
                                research_mode=mode,
                                output_language="it" if case == "deep_sea" else "en",
                            ),
                            settings,
                            config_snapshot=snapshot,
                        )
                        started = time.perf_counter()
                        ResearchOrchestrator(store, settings, search).execute(run.id)
                        store.commit()
                        item = _metrics(store, run.id, case, mode, time.perf_counter() - started)
                    except Exception as exc:
                        session.rollback()
                        item = {"case": case, "mode": mode, "error": str(exc)[:500]}
                    finally:
                        session.close()
                    results["runs"].append(item)
                    args.output.write_text(
                        json.dumps(results, ensure_ascii=False, indent=2, default=dict)
                    )
                    print(json.dumps(item, ensure_ascii=False, default=dict), flush=True)
    finally:
        dispose_all_engines()
    return 1 if any("error" in item for item in results["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
