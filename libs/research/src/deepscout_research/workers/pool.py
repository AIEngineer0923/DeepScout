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
from deepscout_core.domain.schemas import (
    ResearchTaskRead,
    SearchCandidateWrite,
    SourceWrite,
    ToolExecutionWrite,
)
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_research.budget_gate import BudgetGate
from deepscout_research.search.protocol import WebSearchProvider
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
        self._max_workers = max(1, max_workers)
        self._inline_store = inline_store

    @traceable(name="fan_out_research", run_type="chain")
    def execute_batch(
        self,
        run_id: uuid.UUID,
        tasks: list[ResearchTaskRead],
        *,
        iteration: int,
    ) -> list[WorkerResult]:
        if not tasks:
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
        budget = BudgetGate(store)
        try:
            store.update_task_status(
                task.id,
                ResearchTaskStatus.RUNNING,
                worker_id=worker_id,
            )
            if task.question_id is not None:
                store.update_question_status(task.question_id, ResearchQuestionStatus.RESEARCHING)

            memory = WorkingMemory(run_id=run_id, task_id=task.id)
            memory.remember("objective", task.objective)

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
                results = self._search.search(query, max_results=3)
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
            for result in results:
                domain = urlparse(result.url).netloc
                _, created = store.add_source(
                    run_id,
                    SourceWrite(canonical_url=result.url, title=result.title, domain=domain),
                )
                if not created:
                    continue
                try:
                    budget.reserve_source(run_id, note=f"task:{task.task_key}")
                except BudgetExhaustedError:
                    break
                sources_added += 1

            if task.question_id is not None:
                status = (
                    ResearchQuestionStatus.ANSWERED
                    if sources_added > 0
                    else ResearchQuestionStatus.INSUFFICIENT_EVIDENCE
                )
                store.update_question_status(task.question_id, status)

            store.update_task_status(task.id, ResearchTaskStatus.COMPLETED, worker_id=worker_id)
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
