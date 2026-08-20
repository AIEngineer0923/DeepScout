"""Parallel research worker pool with fan-out/fan-in."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlparse

from deepscout_core.domain.budget import BudgetExhaustedError
from deepscout_core.domain.enums import AgentRole, ResearchPhase, ResearchQuestionStatus, ResearchTaskStatus
from deepscout_core.domain.schemas import ResearchTaskRead, SearchCandidateWrite, SourceWrite, ToolExecutionWrite
from deepscout_core.domain.enums import ToolExecutionStatus
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.budget_gate import BudgetGate
from deepscout_research.search.protocol import WebSearchProvider
from deepscout_research.working_memory import WorkingMemory


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
        store: ResearchStore,
        search: WebSearchProvider,
        budget: BudgetGate,
        *,
        max_workers: int = 3,
    ) -> None:
        self._store = store
        self._search = search
        self._budget = budget
        self._max_workers = max(1, max_workers)

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
    ) -> WorkerResult:
        worker_id = uuid.uuid4()
        self._store.update_task_status(
            task.id,
            ResearchTaskStatus.RUNNING,
            worker_id=worker_id,
        )
        if task.question_id is not None:
            self._store.update_question_status(task.question_id, ResearchQuestionStatus.RESEARCHING)

        memory = WorkingMemory(run_id=run_id, task_id=task.id)
        memory.remember("objective", task.objective)

        if "web_search" not in task.allowed_tools:
            self._store.update_task_status(
                task.id,
                ResearchTaskStatus.FAILED,
                worker_id=worker_id,
                error_message="web_search not allowed",
            )
            return WorkerResult(task.id, worker_id, success=False, error="tool_not_allowed")

        query = task.objective[:500]
        try:
            self._budget.reserve_tool_call(run_id, note=f"search:{task.task_key}")
            results = self._search.search(query, max_results=3)
        except BudgetExhaustedError as exc:
            self._store.update_task_status(
                task.id,
                ResearchTaskStatus.FAILED,
                worker_id=worker_id,
                error_message=str(exc),
            )
            return WorkerResult(task.id, worker_id, success=False, error=str(exc))
        except Exception as exc:
            self._store.save_tool_execution(
                run_id,
                ToolExecutionWrite(
                    tool_name="web_search",
                    input_summary=query,
                    output_summary=str(exc)[:4000],
                    status=ToolExecutionStatus.FAILED,
                ),
            )
            if task.question_id is not None:
                self._store.update_question_status(
                    task.question_id,
                    ResearchQuestionStatus.INSUFFICIENT_EVIDENCE,
                )
            self._store.update_task_status(
                task.id,
                ResearchTaskStatus.FAILED,
                worker_id=worker_id,
                error_message=str(exc)[:4000],
            )
            return WorkerResult(task.id, worker_id, success=False, error=str(exc))

        self._store.save_tool_execution(
            run_id,
            ToolExecutionWrite(
                tool_name="web_search",
                input_summary=query,
                output_summary=f"{len(results)} results",
                status=ToolExecutionStatus.SUCCESS,
            ),
        )
        self._store.add_search_candidates(
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
            _, created = self._store.add_source(
                run_id,
                SourceWrite(canonical_url=result.url, title=result.title, domain=domain),
            )
            if not created:
                continue
            try:
                self._budget.reserve_source(run_id, note=f"task:{task.task_key}")
            except BudgetExhaustedError:
                break
            sources_added += 1

        if task.question_id is not None:
            status = (
                ResearchQuestionStatus.ANSWERED
                if sources_added > 0
                else ResearchQuestionStatus.INSUFFICIENT_EVIDENCE
            )
            self._store.update_question_status(task.question_id, status)

        self._store.update_task_status(task.id, ResearchTaskStatus.COMPLETED, worker_id=worker_id)
        self._store.save_task_checkpoint(
            task.id,
            {
                "worker_id": str(worker_id),
                "phase": ResearchPhase.RESEARCH.value,
                "agent_role": AgentRole.RESEARCH_WORKER.value,
                "sources_added": sources_added,
                "memory": memory.snapshot(),
            },
        )
        return WorkerResult(task.id, worker_id, success=True, sources_added=sources_added)
