"""Parallel research worker pool with fan-out/fan-in."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlparse

from deepscout_core.domain.budget import BudgetExhaustedError
from deepscout_core.domain.enums import (
    AgentRole,
    ResearchPhase,
    ResearchQuestionStatus,
    ResearchTaskStatus,
    ToolExecutionStatus,
)
from deepscout_core.domain.events import ResearchEventType
from deepscout_core.domain.schemas import (
    ResearchTaskRead,
    SearchCandidateWrite,
    SearchResult,
    SourceWrite,
    ToolExecutionWrite,
)
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_research.budget_gate import BudgetGate
from deepscout_research.fetch.secure import public_http_url_or_none
from deepscout_research.search.protocol import WebSearchProvider
from deepscout_research.workers.langgraph_worker import run_worker_graph
from deepscout_research.working_memory import WorkingMemory
from langsmith import traceable
from sqlalchemy.orm import sessionmaker


@dataclass(frozen=True, slots=True)
class WorkerResult:
    task_id: uuid.UUID
    worker_id: uuid.UUID
    success: bool
    sources_added: int = 0
    error: str | None = None


class ResearchWorkerPool:
    def __init__(
        self,
        session_factory: sessionmaker,
        settings: Settings,
        search_provider: WebSearchProvider,
        *,
        max_workers: int = 3,
        inline_store: ResearchStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._search = search_provider
        self._max_workers = max(0, max_workers)
        self._inline_store = inline_store

    @traceable(name="fan_out_research", run_type="chain")
    def execute_batch(
        self,
        run_id: uuid.UUID,
        tasks: list[ResearchTaskRead],
        *,
        iteration: int,
    ) -> list[WorkerResult]:
        if not tasks or self._max_workers <= 0:
            return []
        capped = tasks[: self._max_workers]
        if self._inline_store is not None:
            return [
                self._execute_one(run_id, task, iteration=iteration, store=self._inline_store)
                for task in capped
            ]
        results: list[WorkerResult] = []
        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(capped))) as executor:
            futures = {
                executor.submit(self._execute_one, run_id, task, iteration=iteration): task
                for task in capped
            }
            for future in as_completed(futures):
                results.append(future.result())
        return results

    @traceable(name="worker:research", run_type="chain")
    def _execute_one(
        self,
        run_id: uuid.UUID,
        task: ResearchTaskRead,
        *,
        iteration: int,
        store: ResearchStore | None = None,
    ) -> WorkerResult:
        worker_id = uuid.uuid4()
        owns_session = store is None
        if store is None:
            session = self._session_factory()
            store = ResearchStore(session)
        else:
            session = store._session  # noqa: SLF001 — inline test execution shares fixture session

        run = store.get_run(run_id)
        if run is not None and run.status.value == "cancelled":
            store.update_task_status(
                task.id,
                ResearchTaskStatus.CANCELLED,
                worker_id=worker_id,
                error_message="run_cancelled",
            )
            self._persist(session, owns_session)
            return WorkerResult(task.id, worker_id, success=False, error="run_cancelled")

        if task.status == ResearchTaskStatus.COMPLETED:
            return WorkerResult(task.id, worker_id, success=True, sources_added=0)

        budget = BudgetGate(store)
        try:
            claimed = store.claim_ready_task(task.id, worker_id)
            if not claimed:
                self._persist(session, owns_session)
                return WorkerResult(task.id, worker_id, success=False, error="not_claimed")
            store.append_run_event(
                run_id,
                ResearchEventType.WORKER_STARTED.value,
                {
                    "task_id": str(task.id),
                    "worker_id": str(worker_id),
                    "task_key": task.task_key,
                    "layer": "worker",
                },
            )
            self._persist(session, owns_session)
            if task.question_id is not None:
                store.update_question_status(task.question_id, ResearchQuestionStatus.RESEARCHING)

            memory = WorkingMemory(run_id=run_id, task_id=task.id)
            memory.remember("objective", task.objective)
            if self._settings.agent_skills_auto:
                from deepscout_core.domain.enums import AgentNoteKind
                from deepscout_research.runtime.delegation import DelegationPolicy
                from deepscout_research.skills.router import select_skills

                policy = DelegationPolicy.from_settings(self._settings)
                if not policy.can_delegate(
                    parent_depth=1,
                    existing_children=0,
                    total_workers=1,
                    untrusted_text=task.objective,
                ):
                    store.add_agent_note(
                        run_id,
                        kind=AgentNoteKind.RISK,
                        body="Ignored spawn/delegation request in task text",
                        task_id=task.id,
                    )
                skills = select_skills(task.objective, channel="task_objective")
                for skill in skills:
                    store.bind_skill(
                        run_id,
                        skill.skill_id,
                        skill.version,
                        task_id=task.id,
                    )
                    store.append_run_event(
                        run_id,
                        ResearchEventType.SKILL_SELECTED.value,
                        {
                            "skill_id": skill.skill_id,
                            "skill_version": skill.version,
                            "task_id": str(task.id),
                            "channel": "task_objective",
                            "layer": "worker",
                        },
                    )
                    memory.remember(f"skill:{skill.skill_id}", skill.body[:1500])

            if "web_search" not in task.allowed_tools:
                store.update_task_status(
                    task.id,
                    ResearchTaskStatus.FAILED,
                    worker_id=worker_id,
                    error_message="web_search not allowed",
                )
                self._persist(session, owns_session)
                return WorkerResult(task.id, worker_id, success=False, error="tool_not_allowed")

            query = task.objective[:500]
            try:
                budget.reserve_tool_call(run_id, note=f"search:{task.task_key}")
                graph_state = run_worker_graph(
                    run_id=run_id,
                    task_id=task.id,
                    worker_id=worker_id,
                    objective=task.objective,
                    search_provider=self._search,
                    resume=True,
                    database_url=self._settings.database_url,
                    durable_checkpoint=self._settings.research_durable_langgraph_checkpoint,
                    cancelled=run is not None and run.status.value == "cancelled",
                )
                if graph_state.get("status") == "failed":
                    raise RuntimeError(graph_state.get("error") or "worker_graph_failed")
                run = store.get_run(run_id)
                if run is not None and run.status.value == "cancelled":
                    store.update_task_status(
                        task.id,
                        ResearchTaskStatus.CANCELLED,
                        worker_id=worker_id,
                        error_message="run_cancelled",
                    )
                    self._persist(session, owns_session)
                    return WorkerResult(task.id, worker_id, success=False, error="run_cancelled")
                query = graph_state.get("query", query)
                results = [
                    SearchResult.model_validate(item)
                    for item in graph_state.get("search_results", [])
                ]
            except BudgetExhaustedError as exc:
                store.update_task_status(
                    task.id,
                    ResearchTaskStatus.FAILED,
                    worker_id=worker_id,
                    error_message=str(exc),
                )
                self._persist(session, owns_session)
                return WorkerResult(task.id, worker_id, success=False, error=str(exc))
            except Exception as exc:
                store.save_tool_execution(
                    run_id,
                    ToolExecutionWrite(
                        tool_name="web_search",
                        input_summary=query,
                        output_summary=str(exc)[:4000],
                        status=ToolExecutionStatus.FAILED,
                    ),
                )
                if task.question_id is not None:
                    store.update_question_status(
                        task.question_id,
                        ResearchQuestionStatus.INSUFFICIENT_EVIDENCE,
                    )
                store.update_task_status(
                    task.id,
                    ResearchTaskStatus.FAILED,
                    worker_id=worker_id,
                    error_message=str(exc)[:4000],
                )
                self._persist(session, owns_session)
                return WorkerResult(task.id, worker_id, success=False, error=str(exc))

            store.save_tool_execution(
                run_id,
                ToolExecutionWrite(
                    tool_name="web_search",
                    input_summary=query,
                    output_summary=f"{len(results)} results",
                    status=ToolExecutionStatus.SUCCESS,
                ),
            )
            memory.remember_tool_summary(f"web_search:{len(results)}")
            store.add_search_candidates(
                run_id,
                SearchCandidateWrite(
                    query=query,
                    provider=self._search.provider_name,
                    results=results,
                    question_id=task.question_id,
                ),
            )

            sources_added = 0
            prefs = store.list_source_preferences(run_id)
            from deepscout_research.source_policy import is_excluded

            for result in results:
                safe_url = public_http_url_or_none(result.url)
                if safe_url is None:
                    continue
                if is_excluded(safe_url, prefs):
                    continue
                domain = urlparse(safe_url).netloc
                _, created = store.add_source(
                    run_id,
                    SourceWrite(canonical_url=safe_url, title=result.title, domain=domain),
                )
                if not created:
                    continue
                try:
                    budget.reserve_source(run_id, note=f"task:{task.task_key}")
                except BudgetExhaustedError:
                    break
                sources_added += 1
                store.append_run_event(
                    run_id,
                    ResearchEventType.SOURCE_DISCOVERED.value,
                    {
                        "task_id": str(task.id),
                        "worker_id": str(worker_id),
                        "url": safe_url,
                        "layer": "tool",
                    },
                )

            if task.question_id is not None:
                status = (
                    ResearchQuestionStatus.ANSWERED
                    if sources_added > 0
                    else ResearchQuestionStatus.INSUFFICIENT_EVIDENCE
                )
                store.update_question_status(task.question_id, status)

            store.update_task_status(task.id, ResearchTaskStatus.COMPLETED, worker_id=worker_id)
            store.append_run_event(
                run_id,
                ResearchEventType.WORKER_COMPLETED.value,
                {
                    "task_id": str(task.id),
                    "worker_id": str(worker_id),
                    "task_key": task.task_key,
                    "sources_added": sources_added,
                    "layer": "worker",
                },
            )
            store.save_task_checkpoint(
                task.id,
                {
                    "worker_id": str(worker_id),
                    "phase": ResearchPhase.RESEARCH.value,
                    "agent_role": AgentRole.RESEARCH_WORKER.value,
                    "sources_added": sources_added,
                    "memory": memory.snapshot(),
                },
            )
            self._persist(session, owns_session)
            return WorkerResult(task.id, worker_id, success=True, sources_added=sources_added)
        except Exception as exc:
            if owns_session:
                session.rollback()
            try:
                store.update_task_status(
                    task.id,
                    ResearchTaskStatus.FAILED,
                    worker_id=worker_id,
                    error_message=str(exc)[:4000],
                )
                store.append_run_event(
                    run_id,
                    ResearchEventType.WORKER_FAILED.value,
                    {
                        "task_id": str(task.id),
                        "worker_id": str(worker_id),
                        "task_key": task.task_key,
                        "layer": "worker",
                    },
                )
                if owns_session:
                    session.commit()
                else:
                    session.flush()
            except Exception:
                pass
            return WorkerResult(task.id, worker_id, success=False, error=str(exc))
        finally:
            if owns_session:
                session.close()

    @staticmethod
    def _persist(session, owns_session: bool) -> None:
        if owns_session:
            session.commit()
        else:
            session.flush()
