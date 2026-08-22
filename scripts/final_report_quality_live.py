#!/usr/bin/env python3
"""Run frozen final-report quality regressions with live providers."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs" / "core" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs" / "persistence" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs" / "research" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs" / "providers" / "src"))

from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_persistence.session import dispose_all_engines, get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.contracts.coverage import evaluate_coverage
from deepscout_research.contracts.extract import contract_from_snapshot
from deepscout_research.langsmith_env import configure_langsmith_env
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.phases.final_critic import run_final_answer_critic
from deepscout_research.runtime.config_snapshot import build_config_snapshot
from deepscout_research.search.tavily import TavilyWebSearchProvider

REGRESSIONS = {
    "eu_gpai": (
        "Spiega gli obblighi che il Regolamento UE sull'IA impone nel 2026 ai fornitori "
        "di modelli di IA per finalità generali, distinguendo gli obblighi già applicabili "
        "da quelli successivi, e individua le fonti autorevoli della Commissione o dell'UE "
        "a supporto di ogni conclusione. Dai priorità a EUR-Lex, Commissione europea e "
        "pubblicazioni dell'EU AI Office."
    ),
    "ev_lifecycle": (
        "Confronta stime credibili delle emissioni GHG del ciclo di vita di veicoli elettrici "
        "a batteria (BEV) e veicoli a combustione interna comparabili in Europa. Quantifica "
        "dove possibile e spiega perché studi autorevoli riportano stime di break-even diverse. "
        "Preferisci ICCT, IEA, fonti peer-reviewed e istituzionali europee."
    ),
    "lfp_nmc": (
        "Confronta LFP e NMC ad alto contenuto di nichel su ciclo di vita, densità energetica, "
        "sicurezza termica, driver di costo ed effetti dell'ingegneria di pacco. Preferisci fonti "
        "peer-reviewed, DOE, laboratori nazionali e documentazione ingegneristica credibile."
    ),
    "eu_official_multihop": (
        "Identifica chi ricopre attualmente la carica di Presidente della Commissione europea, "
        "quindi determina su quali obblighi concreti relativi ai modelli di IA per finalità "
        "generali la Commissione europea ha pubblicato linee guida destinate ai fornitori per "
        "il 2026. La seconda attività deve dipendere dalla corretta identificazione del titolare "
        "della carica nella prima attività. Utilizza esclusivamente fonti istituzionali ufficiali "
        "dell'UE."
    ),
}


def _snapshot(store: ResearchStore, run_id, *, case: str, latency_ms: int) -> dict:
    row = store.get_run_row(run_id)
    report = store.get_report(run_id)
    contract = contract_from_snapshot(row.config_snapshot if row else None)
    coverage = evaluate_coverage(store, run_id, contract) if contract else None
    critic = run_final_answer_critic(store, run_id)
    return {
        "case": case,
        "run_id": str(run_id),
        "latency_ms": latency_ms,
        "goal": row.goal if row else "",
        "sources": len(store.list_sources(run_id)),
        "claims": len(store.list_claims(run_id)),
        "evidence": len(store.list_evidence(run_id)),
        "coverage_rounds": (row.config_snapshot or {}).get("coverage_research_rounds"),
        "coverage_gaps": coverage.material_gaps if coverage else [],
        "final_critic": critic.model_dump(mode="json"),
        "report_excerpt": (report.body_markdown[:2500] if report else ""),
        "report_title": report.title if report else "",
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run frozen final-report quality regressions")
    parser.add_argument("--case", choices=list(REGRESSIONS), help="Run a single regression case")
    parser.add_argument("--attempts", type=int, default=1, help="Bounded repeat attempts for robustness")
    parser.add_argument(
        "--no-early-exit",
        action="store_true",
        help="Run all attempts even after first pass (for robustness pass-rate)",
    )
    args = parser.parse_args()
    cases = {args.case: REGRESSIONS[args.case]} if args.case else REGRESSIONS

    settings = configure_langsmith_env()
    settings = settings.model_copy(
        update={
            "research_workers_inline": True,
            "research_use_legacy_path": False,
            "research_max_coverage_rounds": 2,
            "research_max_gap_queries_per_round": 3,
        }
    )
    out_path = (
        Path(__file__).resolve().parents[1]
        / "libs/evaluation/data/final_report_quality_live_results.json"
    )
    results: dict = {"started_at": datetime.now(UTC).isoformat(), "cases": {}}
    try:
        with TavilyWebSearchProvider(settings) as search:
            for case, goal in cases.items():
                attempts: list[dict] = []
                for attempt in range(1, max(1, args.attempts) + 1):
                    session = get_session_factory(settings.database_url)()
                    store = ResearchStore(session)
                    try:
                        snap = {
                            **build_config_snapshot(settings),
                            "benchmark": "final_report_quality_live_v1",
                            "case": case,
                            "attempt": attempt,
                        }
                        created = store.create_run(
                            ResearchRunCreate(
                                goal=goal,
                                budget=ResearchBudget(
                                    max_iterations=4,
                                    max_wall_time_seconds=600,
                                    max_sources=20,
                                    max_tool_calls=30,
                                ),
                                research_mode="deep",
                                output_language="it" if case.startswith("eu") else "en",
                            ),
                            settings,
                            config_snapshot=snap,
                        )
                        t0 = time.perf_counter()
                        ResearchOrchestrator(store, settings, search).execute(created.id)
                        store.commit()
                        latency = int((time.perf_counter() - t0) * 1000)
                        snapshot = _snapshot(store, created.id, case=case, latency_ms=latency)
                        snapshot["attempt"] = attempt
                        attempts.append(snapshot)
                        if snapshot["final_critic"]["verdict"] == "pass" and not args.no_early_exit:
                            break
                    except Exception as exc:
                        session.rollback()
                        attempts.append(
                            {
                                "attempt": attempt,
                                "error": str(exc)[:500],
                                "final_critic": {"verdict": "error"},
                                "coverage_gaps": [],
                                "latency_ms": 0,
                            }
                        )
                    finally:
                        session.close()
                pass_count = sum(1 for item in attempts if item["final_critic"]["verdict"] == "pass")
                best = dict(attempts[-1])
                best["pass_rate"] = f"{pass_count}/{len(attempts)}"
                best["attempt_summaries"] = [
                    {
                        "attempt": item.get("attempt", index + 1),
                        "run_id": item.get("run_id"),
                        "verdict": item["final_critic"]["verdict"],
                        "coverage_gaps": item.get("coverage_gaps", []),
                        "latency_ms": item.get("latency_ms"),
                    }
                    for index, item in enumerate(attempts)
                ]
                results["cases"][case] = best
                print(json.dumps(best, ensure_ascii=False, indent=2)[:4000])
    finally:
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        dispose_all_engines()
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
