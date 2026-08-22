"""Research orchestrator — deterministic supervisor with parallel workers."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from deepscout_core.domain.budget import BudgetExhaustedError
from deepscout_core.domain.enums import (
    ResearchPhase,
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
)
from deepscout_core.domain.events import ResearchEvent, ResearchEventType
from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.budget_gate import BudgetGate
from deepscout_research.exceptions import RunCancelledError
from deepscout_research.phases.compile_knowledge import compile_knowledge_for_run
from deepscout_research.phases.contradiction import detect_contradictions_for_run
from deepscout_research.phases.critic import run_critic_for_run
from deepscout_research.phases.extract import extract_claims_for_run
from deepscout_research.phases.fetch import fetch_sources_for_run
from deepscout_research.phases.final_critic import run_final_answer_critic
from deepscout_research.phases.report import generate_report
from deepscout_research.phases.synthesis import synthesize_decision
from deepscout_research.phases.verify import verify_claims_for_run
from deepscout_research.planner import build_research_plan, planner_output_to_write
from deepscout_research.retrieval.enabled import retrieval_enabled
from deepscout_research.retrieval.indexer import index_snapshots_for_run
from deepscout_research.retrieval.service import RetrievalService
from deepscout_research.search.protocol import WebSearchProvider
from deepscout_research.termination import TerminationDecision, evaluate_termination
from deepscout_research.workers.pool import ResearchWorkerPool

logger = logging.getLogger(__name__)

EventSink = Callable[[ResearchEvent], None]


@dataclass
class OrchestratorResult:
    run_id: uuid.UUID
    final_status: ResearchRunStatus
    iterations: int
    events: list[ResearchEvent] = field(default_factory=list)


class ResearchOrchestrator:
    """Global deterministic supervisor — bounded workers execute ready tasks."""

    def __init__(
        self,
        store: ResearchStore,
        settings: Settings,
        search_provider: WebSearchProvider,
        *,
        event_sink: EventSink | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._search = search_provider
        self._budget = BudgetGate(store)
        self._events: list[ResearchEvent] = []
        self._sink = event_sink
        self._max_correction_rounds = 1

    def _seed_institutional_profiles(self, run_id: uuid.UUID) -> None:
        from urllib.parse import urlparse

        from deepscout_core.domain.schemas import SourceWrite

        from deepscout_research.contracts.extract import contract_from_snapshot
        from deepscout_research.contracts.legal_reference import institutional_profile_url_hints
        from deepscout_research.contracts.office_holder import office_title_from_goal
        from deepscout_research.fetch.secure import public_http_url_or_none

        row = self._store.get_run_row(run_id)
        contract = contract_from_snapshot(row.config_snapshot if row else None)
        if contract is None:
            return
        req_ids = {item.requirement_id for item in contract.requirements}
        if "R_president" not in req_ids:
            return
        for url in institutional_profile_url_hints(
            office_title_from_goal(contract.primary_question)
        ):
            safe_url = public_http_url_or_none(url)
            if safe_url is None:
                continue
            self._store.add_source(
                run_id,
                SourceWrite(
                    canonical_url=safe_url,
                    title="institutional profile",
                    domain=urlparse(safe_url).netloc,
                ),
            )

    def _seed_pinned_sources(self, run_id: uuid.UUID) -> None:
        from urllib.parse import urlparse

        from deepscout_core.domain.schemas import SourceWrite

        from deepscout_research.fetch.secure import public_http_url_or_none

        for pref in self._store.list_source_preferences(run_id):
            if pref.action != "pin" or pref.identity_kind != "url":
                continue
            safe_url = public_http_url_or_none(pref.identity_value)
            if safe_url is None:
                continue
            self._store.add_source(
                run_id,
                SourceWrite(
                    canonical_url=safe_url,
                    title=pref.identity_value,
                    domain=urlparse(safe_url).netloc,
                ),
            )

    def _record_monitor_change(self, run_id: uuid.UUID) -> None:
        row = self._store.get_run_row(run_id)
        if row is None or row.monitor_id is None:
            return
        previous = [
            item
            for item in self._store.list_monitor_runs(row.monitor_id)
            if item.id != run_id and item.status.value == "completed"
        ]
        if not previous:
            return
        from datetime import UTC, datetime

        from deepscout_research.monitors.change import detect_run_change

        result = detect_run_change(self._store, previous[0].id, run_id)
        if result["changed"]:
            self._store.record_monitor_change(row.monitor_id, now=datetime.now(UTC))

    def _ensure_active(self, run_id: uuid.UUID) -> None:
        run = self._store.get_run(run_id)
        if run is not None and run.status == ResearchRunStatus.CANCELLED:
            raise RunCancelledError(f"Research run {run_id} cancelled")

    def _emit(self, event: ResearchEvent) -> None:
        self._events.append(event)
        if self._sink is not None:
            self._sink(event)
        self._store.append_run_event(
            event.run_id,
            event.event_type.value,
            {
                "phase": event.phase.value if event.phase else None,
                "iteration": event.iteration,
                **(event.payload or {}),
            },
        )

    def _has_unfinished_research(self, run_id: uuid.UUID) -> bool:
        return any(
            task.status.value in {"pending", "ready", "running"}
            for task in self._store.list_tasks(run_id)
        )

    def _pause_for_budget_review(
        self, run_id: uuid.UUID, iterations: int
    ) -> OrchestratorResult | None:
        from deepscout_core.domain.enums import ReviewReasonCode

        from deepscout_research.hitl import HumanReviewService, PolicyVerdict, evaluate_policy

        if not self._has_unfinished_research(run_id):
            return None
        if (
            evaluate_policy(ReviewReasonCode.BUDGET_EXTENSION, self._settings)
            != PolicyVerdict.REQUIRE_REVIEW
        ):
            return None
        service = HumanReviewService(self._store, self._settings)
        review_id = service.create_budget_extension_review(run_id)
        self._store.set_termination_reason(run_id, "awaiting_budget_extension")
        self._store.update_run_status(run_id, ResearchRunStatus.PAUSED)
        self._store.append_review_event(
            review_id,
            run_id,
            event_type="paused",
            actor_source="system",
            actor_identity="orchestrator",
        )
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.RUN_PAUSED,
                run_id=run_id,
                payload={
                    "reason": "awaiting_budget_extension",
                    "review_request_id": str(review_id),
                },
            )
        )
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.REVIEW_REQUESTED,
                run_id=run_id,
                payload={"review_request_id": str(review_id)},
            )
        )
        self._store.commit()
        return OrchestratorResult(
            run_id=run_id,
            final_status=ResearchRunStatus.PAUSED,
            iterations=iterations,
            events=list(self._events),
        )

    @traceable(name="research_run_execute", run_type="chain")
    def execute(self, run_id: uuid.UUID) -> OrchestratorResult:
        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")

        # Durable HITL pause: do not auto-claim or continue until review is resolved.
        if run.status == ResearchRunStatus.PAUSED:
            return OrchestratorResult(
                run_id=run_id,
                final_status=ResearchRunStatus.PAUSED,
                iterations=0,
                events=list(self._events),
            )

        self._store.update_run_status(run_id, ResearchRunStatus.RUNNING)
        self._store.reclaim_stale_running_tasks(
            run_id, stale_after_seconds=self._settings.research_task_stale_after_s
        )
        self._seed_pinned_sources(run_id)
        self._emit(ResearchEvent(event_type=ResearchEventType.RUN_STARTED, run_id=run_id))

        iterations = 0
        try:
            self.build_plan(run_id, goal=run.goal)
            self._seed_institutional_profiles(run_id)
            self._store.commit()
            while True:
                self._ensure_active(run_id)
                iterations += 1
                decision = self.execute_research_batch(run_id, iteration=iterations)
                if decision.should_stop:
                    if decision.reason == "budget_exhausted":
                        paused = self._pause_for_budget_review(run_id, iterations)
                        if paused is not None:
                            return paused
                    break
                tasks = self._store.list_tasks(run_id)
                from deepscout_research.contracts.dependency_gate import (
                    ready_tasks_with_verified_deps,
                )

                if tasks and not ready_tasks_with_verified_deps(self._store, run_id, tasks):
                    break

            self._ensure_active(run_id)
            self._run_evidence_pipeline(run_id)
            iterations_box = [iterations]
            self._run_corrective_research_loops(run_id, iterations_ref=iterations_box)
            iterations = iterations_box[0]
            self._run_finalize_phases(run_id)
            from deepscout_evaluation.persist import persist_research_evaluations

            persist_research_evaluations(self._store, run_id)
            self._store.commit()

            final = evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
                tasks=self._store.list_tasks(run_id),
            )
            terminal_status = (
                final.terminal_status if final.should_stop else ResearchRunStatus.COMPLETED
            )
            reason = final.reason if final.should_stop else "pipeline_complete"
            self._store.set_termination_reason(run_id, reason)
            self._store.update_run_status(run_id, terminal_status)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_COMPLETED,
                    run_id=run_id,
                    payload={"reason": reason},
                )
            )
            self._record_monitor_change(run_id)
            return OrchestratorResult(
                run_id=run_id,
                final_status=terminal_status,
                iterations=iterations,
                events=list(self._events),
            )
        except RunCancelledError:
            self._store.set_termination_reason(run_id, "cancelled")
            self._store.update_run_status(run_id, ResearchRunStatus.CANCELLED)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_CANCELLED,
                    run_id=run_id,
                    payload={"reason": "cancelled"},
                )
            )
            return OrchestratorResult(
                run_id=run_id,
                final_status=ResearchRunStatus.CANCELLED,
                iterations=iterations,
                events=list(self._events),
            )
        except BudgetExhaustedError:
            paused = self._pause_for_budget_review(run_id, iterations)
            if paused is not None:
                return paused
            if self._settings.research_finalize_on_budget_exhausted:
                try:
                    self._ensure_active(run_id)
                    self._run_evidence_pipeline(run_id)
                    iterations_box = [iterations]
                    self._run_corrective_research_loops(run_id, iterations_ref=iterations_box)
                    iterations = iterations_box[0]
                    self._run_finalize_phases(run_id)
                    from deepscout_evaluation.persist import persist_research_evaluations

                    persist_research_evaluations(self._store, run_id)
                    self._store.commit()
                except RunCancelledError:
                    self._store.set_termination_reason(run_id, "cancelled")
                    self._store.update_run_status(run_id, ResearchRunStatus.CANCELLED)
                    return OrchestratorResult(
                        run_id=run_id,
                        final_status=ResearchRunStatus.CANCELLED,
                        iterations=iterations,
                        events=list(self._events),
                    )
                except Exception:
                    logger.exception(
                        "Finalization after budget exhaustion failed",
                        extra={"run_id": str(run_id)},
                    )
            self._store.set_termination_reason(run_id, "budget_exhausted")
            self._store.update_run_status(run_id, ResearchRunStatus.BUDGET_EXHAUSTED)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_COMPLETED,
                    run_id=run_id,
                    payload={"reason": "budget_exhausted"},
                )
            )
            return OrchestratorResult(
                run_id=run_id,
                final_status=ResearchRunStatus.BUDGET_EXHAUSTED,
                iterations=iterations,
                events=list(self._events),
            )
        except Exception:
            logger.exception("Research run failed", extra={"run_id": str(run_id)})
            self._store.set_termination_reason(run_id, "unexpected_failure")
            self._store.update_run_status(run_id, ResearchRunStatus.FAILED)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_FAILED,
                    run_id=run_id,
                    payload={"error": "unexpected_failure"},
                )
            )
            return OrchestratorResult(
                run_id=run_id,
                final_status=ResearchRunStatus.FAILED,
                iterations=iterations,
                events=list(self._events),
            )

    @traceable(name="phase:plan", run_type="chain")
    def build_plan(self, run_id: uuid.UUID, *, goal: str) -> None:
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.PLAN,
            )
        )
        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")

        if self._store.list_questions(run_id):
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_COMPLETED,
                    run_id=run_id,
                    phase=ResearchPhase.PLAN,
                )
            )
            return

        budget_summary = (
            f"iterations={run.budget.max_iterations}, "
            f"sources={run.budget.max_sources}, "
            f"tool_calls={run.budget.max_tool_calls}"
        )
        plan_output = build_research_plan(
            self._settings,
            run_id=run_id,
            goal=goal,
            budget_summary=budget_summary,
            output_language=run.output_language,
            store=self._store,
        )
        from deepscout_research.contracts.extract import (
            build_research_contract,
            derive_report_contract,
        )

        research_contract = build_research_contract(
            goal=goal,
            planner=plan_output,
            output_language=run.output_language,
        )
        report_contract = derive_report_contract(research_contract)
        self._store.merge_config_snapshot(
            run_id,
            {
                "research_contract": research_contract.model_dump(mode="json"),
                "report_contract": report_contract.model_dump(mode="json"),
            },
        )
        plan_write = planner_output_to_write(plan_output)
        if research_contract.user_facing_questions:
            plan_write.questions = research_contract.user_facing_questions
        self._store.save_plan(run_id, plan_write)
        from deepscout_research.contracts.query_planning import contract_research_tasks

        supplemental = contract_research_tasks(research_contract)
        if supplemental:
            self._store.append_tasks(run_id, supplemental)
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.PLAN,
            )
        )

    def execute_research_batch(self, run_id: uuid.UUID, *, iteration: int) -> TerminationDecision:
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.RESEARCH,
                iteration=iteration,
            )
        )
        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")

        tasks = self._store.list_tasks(run_id)
        if not tasks or self._settings.research_use_legacy_path:
            return self._legacy_single_question_iteration(run_id, iteration=iteration)

        from deepscout_research.contracts.dependency_gate import ready_tasks_with_verified_deps

        ready = ready_tasks_with_verified_deps(self._store, run_id, tasks)
        for task in ready:
            if task.status == ResearchTaskStatus.PENDING:
                self._store.update_task_status(task.id, ResearchTaskStatus.READY)
                self._emit(
                    ResearchEvent(
                        event_type=ResearchEventType.TASK_READY,
                        run_id=run_id,
                        phase=ResearchPhase.RESEARCH,
                        iteration=iteration,
                        payload={
                            "task_id": str(task.id),
                            "task_key": task.task_key,
                            "layer": "orchestrator",
                        },
                    )
                )

        consumption = self._store.get_consumption(run_id)
        pre_decision = evaluate_termination(
            budget=run.budget,
            consumption=consumption,
            questions=self._store.list_questions(run_id),
            tasks=self._store.list_tasks(run_id),
        )
        if pre_decision.should_stop:
            return pre_decision

        if not ready:
            return evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
                tasks=self._store.list_tasks(run_id),
            )

        remaining_tools = max(0, run.budget.max_tool_calls - consumption.tool_calls)
        from deepscout_research.runtime.allocation import allocate_workers

        allocation = allocate_workers(
            tasks,
            settings=self._settings,
            concurrency_limit=self._store.get_concurrency_limit(run_id),
            remaining_tool_calls=remaining_tools,
        )
        if allocation.max_workers <= 0:
            return evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
                tasks=self._store.list_tasks(run_id),
            )

        self._store.commit()
        self._budget.reserve_iteration(run_id, note=f"iteration:{iteration}")
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.WORKERS_ALLOCATED,
                run_id=run_id,
                phase=ResearchPhase.RESEARCH,
                iteration=iteration,
                payload={
                    "class": allocation.allocation_class.value,
                    "max_workers": allocation.max_workers,
                    "ready_count": allocation.ready_count,
                    "reason": allocation.reason,
                },
            )
        )
        self._store.commit()
        pool = ResearchWorkerPool(
            get_session_factory(self._settings.database_url),
            self._settings,
            self._search,
            max_workers=allocation.max_workers,
            inline_store=self._store if self._settings.research_workers_inline else None,
        )
        results = pool.execute_batch(run_id, ready, iteration=iteration)
        self._store.refresh()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.RESEARCH,
                iteration=iteration,
                payload={"workers": len(results), "ready_tasks": len(ready)},
            )
        )
        refreshed_tasks = self._store.list_tasks(run_id)
        evidence_count = len(self._store.list_evidence(run_id))
        from deepscout_research.runtime.replan import evaluate_replan
        from deepscout_research.runtime.sufficiency import evaluate_sufficiency

        row = self._store.get_run_row(run_id)
        replans_used = int(getattr(row, "replans_used", 0) or 0) if row else 0
        last_sources = sum(item.sources_added for item in results)
        replan = evaluate_replan(
            settings=self._settings,
            replans_used=replans_used,
            tasks=refreshed_tasks,
            last_batch_sources=last_sources,
            evidence_count=evidence_count,
        )
        if replan.apply:
            added = self._store.append_tasks(run_id, list(replan.new_tasks))
            self._store.increment_replans(run_id)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.REPLAN_APPLIED,
                    run_id=run_id,
                    payload={"added": added, "reason": replan.reason},
                )
            )
        sufficiency = evaluate_sufficiency(
            tasks=self._store.list_tasks(run_id),
            batch=results,
            remaining_iterations=max(0, run.budget.max_iterations - iteration),
            evidence_count=evidence_count,
        )
        terminal = evaluate_termination(
            budget=run.budget,
            consumption=self._store.get_consumption(run_id),
            questions=self._store.list_questions(run_id),
            tasks=self._store.list_tasks(run_id),
        )
        if (
            not terminal.should_stop
            and sufficiency.action.value == "finalize"
            and sufficiency.reason == "low_marginal_yield"
        ):
            return TerminationDecision(
                should_stop=True,
                reason="sufficient_evidence",
                terminal_status=ResearchRunStatus.COMPLETED,
            )
        return terminal

    def _legacy_single_question_iteration(
        self, run_id: uuid.UUID, *, iteration: int
    ) -> TerminationDecision:
        """Backward-compatible path when no task rows exist."""
        from urllib.parse import urlparse

        from deepscout_core.domain.schemas import (
            SearchCandidateWrite,
            SourceWrite,
        )

        from deepscout_research.fetch.secure import public_http_url_or_none

        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")
        consumption = self._store.get_consumption(run_id)
        questions = self._store.list_questions(run_id)
        pre_decision = evaluate_termination(
            budget=run.budget,
            consumption=consumption,
            questions=questions,
        )
        if pre_decision.should_stop:
            return pre_decision
        self._budget.reserve_iteration(run_id, note=f"iteration:{iteration}")
        pending = [q for q in questions if q.status == ResearchQuestionStatus.PENDING]
        if not pending:
            return evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
            )
        question = pending[0]
        self._store.update_question_status(question.id, ResearchQuestionStatus.RESEARCHING)
        query = question.text[:500]
        try:
            from deepscout_research.preferences.search_context import search_for_run

            results = search_for_run(self._store, run_id, self._search, query, max_results=3)
            self._budget.reserve_tool_call(run_id, note=f"search:{iteration}")
        except Exception:
            self._store.update_question_status(
                question.id, ResearchQuestionStatus.INSUFFICIENT_EVIDENCE
            )
            return evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
            )
        self._store.add_search_candidates(
            run_id,
            SearchCandidateWrite(
                query=query,
                provider=self._search.provider_name,
                results=results,
                question_id=question.id,
            ),
        )
        from deepscout_research.contracts.extract import contract_from_snapshot
        from deepscout_research.contracts.source_authority import is_source_admissible

        row = self._store.get_run_row(run_id)
        contract = contract_from_snapshot(row.config_snapshot if row else None)
        prefs = self._store.list_source_preferences(run_id)
        for result in results:
            safe_url = public_http_url_or_none(result.url)
            if safe_url is None:
                continue
            from deepscout_research.source_policy import is_excluded

            if is_excluded(safe_url, prefs):
                continue
            admissible, _ = is_source_admissible(
                safe_url,
                contract=contract,
                preferences=prefs,
                title=result.title,
            )
            if not admissible:
                continue
            domain = urlparse(safe_url).netloc
            _, created = self._store.add_source(
                run_id,
                SourceWrite(canonical_url=safe_url, title=result.title, domain=domain),
            )
            if created:
                try:
                    self._budget.reserve_source(run_id, note=f"iteration:{iteration}")
                except BudgetExhaustedError:
                    return TerminationDecision(
                        should_stop=True,
                        reason="budget_exhausted",
                        terminal_status=ResearchRunStatus.BUDGET_EXHAUSTED,
                    )
        self._store.update_question_status(question.id, ResearchQuestionStatus.ANSWERED)
        return evaluate_termination(
            budget=run.budget,
            consumption=self._store.get_consumption(run_id),
            questions=self._store.list_questions(run_id),
        )

    def _compile_knowledge_phase(self, run_id: uuid.UUID) -> None:
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.COMPILE_KNOWLEDGE,
            )
        )
        try:
            compile_stats = compile_knowledge_for_run(self._store, run_id)
        except Exception:
            logger.exception("Compile knowledge phase failed", extra={"run_id": str(run_id)})
            compile_stats = {"statements_created": 0}
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.COMPILE_KNOWLEDGE,
                payload=compile_stats,
            )
        )

    def _run_evidence_pipeline(self, run_id: uuid.UUID, *, incremental: bool = False) -> None:
        run = self._store.get_run(run_id)
        if run is None:
            return

        self._ensure_active(run_id)
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.FETCH,
            )
        )
        try:
            fetched = fetch_sources_for_run(
                self._store,
                run_id,
                max_sources=min(8, run.budget.max_sources),
            )
        except Exception:
            logger.exception("Fetch phase failed", extra={"run_id": str(run_id)})
            fetched = 0
        primary_legal_stats: dict[str, int] = {}
        try:
            from deepscout_research.phases.primary_legal import (
                follow_primary_legal_and_profile_urls,
            )

            primary_legal_stats = follow_primary_legal_and_profile_urls(
                self._store,
                run_id,
                max_additions=4,
            )
            if primary_legal_stats.get("sources_added"):
                fetched += fetch_sources_for_run(
                    self._store,
                    run_id,
                    max_sources=min(8, run.budget.max_sources),
                )
        except Exception:
            logger.exception("Primary legal follow-up failed", extra={"run_id": str(run_id)})
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.FETCH,
                payload={
                    "snapshots_created": fetched,
                    "incremental": incremental,
                    "primary_legal": primary_legal_stats,
                },
            )
        )
        self._store.commit()

        retriever: RetrievalService | None = None
        index_stats: dict[str, int] = {"indexed": 0, "failed": 0, "skipped": 0, "seen": 0}
        if retrieval_enabled(self._settings):
            self._ensure_active(run_id)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_STARTED,
                    run_id=run_id,
                    phase=ResearchPhase.INDEX,
                )
            )
            try:
                index_stats = index_snapshots_for_run(self._store, self._settings, run_id)
                retriever = RetrievalService(self._store, self._settings)
            except Exception:
                logger.exception("Index phase failed", extra={"run_id": str(run_id)})
                index_stats = {"indexed": 0, "failed": 0, "skipped": 0, "seen": 0}
            self._store.commit()
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_COMPLETED,
                    run_id=run_id,
                    phase=ResearchPhase.INDEX,
                    payload=index_stats,
                )
            )

        self._ensure_active(run_id)
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.EXTRACT,
            )
        )
        try:
            extract_stats = extract_claims_for_run(self._store, run_id, retriever=retriever)
        except Exception:
            logger.exception("Extract phase failed", extra={"run_id": str(run_id)})
            extract_stats = {"claims_created": 0, "evidence_created": 0}
        structured_stats: dict[str, int] = {}
        try:
            from deepscout_research.phases.structured_extract import enrich_structured_evidence

            structured_stats = enrich_structured_evidence(self._store, run_id)
            extract_stats = {
                **extract_stats,
                "structured_temporal_claims": structured_stats.get("temporal_claims", 0),
                "structured_verified_entities": structured_stats.get("verified_entities", 0),
            }
        except Exception:
            logger.exception("Structured extract failed", extra={"run_id": str(run_id)})
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.EXTRACT,
                payload={**extract_stats, "structured": structured_stats},
            )
        )

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.VERIFY,
            )
        )
        try:
            verify_stats = verify_claims_for_run(self._store, run_id)
        except Exception:
            logger.exception("Verify phase failed", extra={"run_id": str(run_id)})
            verify_stats = {}
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.VERIFY,
                payload=verify_stats,
            )
        )

    def _run_corrective_research_loops(
        self,
        run_id: uuid.UUID,
        *,
        iterations_ref: list[int],
    ) -> None:
        from deepscout_research.runtime.corrective_research import (
            evaluate_corrective_research,
            record_coverage_attempt,
        )

        while True:
            self._ensure_active(run_id)
            run = self._store.get_run(run_id)
            if run is None:
                return
            decision = evaluate_corrective_research(
                self._store,
                run_id,
                settings=self._settings,
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
            )
            if not decision.apply:
                if decision.coverage is not None:
                    self._store.merge_config_snapshot(
                        run_id,
                        {"coverage_map": decision.coverage.model_dump(mode="json")},
                    )
                break

            added = self._store.append_tasks(run_id, list(decision.new_tasks))
            row = self._store.get_run_row(run_id)
            round_number = int((row.config_snapshot or {}).get("coverage_research_rounds") or 0) + 1
            record_coverage_attempt(
                self._store,
                run_id,
                coverage=decision.coverage,  # type: ignore[arg-type]
                queries=[task.objective for task in decision.new_tasks],
                round_number=round_number,
            )
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.REPLAN_APPLIED,
                    run_id=run_id,
                    payload={
                        "added": added,
                        "reason": decision.reason,
                        "coverage_round": round_number,
                    },
                )
            )
            self._store.commit()

            while True:
                iterations_ref[0] += 1
                batch_decision = self.execute_research_batch(run_id, iteration=iterations_ref[0])
                tasks = self._store.list_tasks(run_id)
                from deepscout_research.contracts.dependency_gate import (
                    ready_tasks_with_verified_deps,
                )

                ready = ready_tasks_with_verified_deps(self._store, run_id, tasks)
                pending = [
                    task for task in tasks if task.status.value in {"pending", "ready", "running"}
                ]
                if not pending:
                    break
                if not ready:
                    break
                if batch_decision.should_stop:
                    break
            self._run_evidence_pipeline(run_id, incremental=True)

    def _run_finalize_phases(self, run_id: uuid.UUID) -> None:
        self._run_post_research_phases(run_id)

    def _run_post_research_phases(self, run_id: uuid.UUID) -> None:
        run = self._store.get_run(run_id)
        if run is None:
            return

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.CONTRADICTION,
            )
        )
        try:
            contradictions = detect_contradictions_for_run(self._store, run_id)
        except Exception:
            logger.exception("Contradiction phase failed", extra={"run_id": str(run_id)})
            contradictions = 0
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.CONTRADICTION,
                payload={"contradictions_detected": contradictions},
            )
        )

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.CRITIC,
            )
        )
        claims = self._store.list_claims(run_id)
        critic_result = None
        if claims:
            critic_result = run_critic_for_run(self._store, run_id)
            correction_round = 0
            while not critic_result.passed and correction_round < self._max_correction_rounds:
                correction_round += 1
                self._ensure_active(run_id)
                verify_claims_for_run(self._store, run_id)
                critic_result = run_critic_for_run(self._store, run_id)
        else:
            from deepscout_core.domain.schemas import CriticResult

            critic_result = CriticResult(
                passed=True,
                artifact_type="research_pipeline",
                severity="pass",
                issues=[],
            )
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.CRITIC,
                payload={
                    "passed": critic_result.passed,
                    "issues": critic_result.issues,
                },
            )
        )

        decision_id = None
        if critic_result.passed:
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_STARTED,
                    run_id=run_id,
                    phase=ResearchPhase.SYNTHESIS,
                )
            )
            try:
                decision_id = synthesize_decision(self._store, self._settings, run_id)
            except Exception:
                logger.exception("Synthesis phase failed", extra={"run_id": str(run_id)})
            self._store.commit()
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_COMPLETED,
                    run_id=run_id,
                    phase=ResearchPhase.SYNTHESIS,
                    payload={"decision_id": str(decision_id) if decision_id else None},
                )
            )

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.REPORT,
            )
        )
        revision_notes = ""
        report_id = generate_report(
            self._store,
            self._settings,
            run_id,
            revision_notes=revision_notes,
        )
        final_critic = run_final_answer_critic(self._store, run_id)
        row = self._store.get_run_row(run_id)
        max_rewrites = self._settings.research_max_report_rewrites
        try:
            from deepscout_evaluation.learning.policy_runtime import (
                effective_report_rewrite_limit,
                policy_from_run_snapshot,
            )

            effective = policy_from_run_snapshot(row.config_snapshot if row else None)
            owner_id = row.owner_principal_id if row else None
            max_rewrites = effective_report_rewrite_limit(
                self._store,
                self._settings,
                owner_principal_id=owner_id,
                effective=effective,
            )
        except Exception:
            pass
        for _rewrite_round in range(1, max_rewrites):
            self._store.merge_config_snapshot(
                run_id,
                {"final_critic": final_critic.model_dump(mode="json")},
            )
            if final_critic.verdict.value == "pass":
                break
            if final_critic.verdict.value == "revision_required":
                revision_notes = final_critic.revision_notes or "; ".join(final_critic.issues[:3])
                report_id = generate_report(
                    self._store,
                    self._settings,
                    run_id,
                    revision_notes=revision_notes,
                )
                final_critic = run_final_answer_critic(self._store, run_id)
                continue
            break
        self._store.merge_config_snapshot(
            run_id,
            {"final_critic": final_critic.model_dump(mode="json")},
        )
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.REPORT,
                payload={
                    "report_id": str(report_id),
                    "final_critic_verdict": final_critic.verdict.value,
                    "final_critic_issues": final_critic.issues[:5],
                },
            )
        )
        # Derived Wiki must not block report delivery. Compile after REPORT so
        # SSE can surface the trustworthy report while compilation continues.
        self._compile_knowledge_phase(run_id)
