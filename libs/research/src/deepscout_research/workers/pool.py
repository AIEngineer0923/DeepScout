"""Parallel research worker pool with fan-out/fan-in."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from deepscout_core.domain.budget import BudgetExhaustedError
from deepscout_core.domain.contracts import SourceKind
from deepscout_core.domain.enums import (
    AgentRole,
    ResearchPhase,
    ResearchQuestionStatus,
    ResearchTaskStatus,
    ToolExecutionStatus,
)
from deepscout_core.domain.events import ResearchEventType
from deepscout_core.domain.research_profiles import research_profile
from deepscout_core.domain.schemas import (
    ResearchTaskRead,
    SearchCandidateWrite,
    SearchResult,
    SourceSnapshotWrite,
    SourceWrite,
    ToolExecutionWrite,
)
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_research.budget_gate import BudgetGate
from deepscout_research.fetch.secure import public_http_url_or_none
from deepscout_research.preferences.search_context import RunScopedSearchProvider
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
        # Queue every ready task in this orchestration iteration. A run's workers
        # deliberately write sequentially: their task, source, event, usage, and
        # budget rows share a PostgreSQL parent and parallel lock upgrades can
        # deadlock. Independent runs remain concurrent at the durable-job layer.
        # max_workers remains the allocation admission bound; it no longer drops
        # ready work or changes iteration accounting.
        return [
            self._execute_one(
                run_id,
                task,
                iteration=iteration,
                store=self._inline_store,
            )
            for task in tasks
        ]

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
            search_batches: list[tuple[str, list[SearchResult]]] = []
            try:
                from deepscout_research.contracts.evidence_relevance import (
                    is_search_result_relevant,
                )
                from deepscout_research.contracts.extract import contract_from_snapshot
                from deepscout_research.contracts.query_planning import (
                    office_holder_queries,
                    search_discovery_requests,
                )
                from deepscout_research.contracts.source_authority import (
                    is_source_admissible,
                )
                from deepscout_research.contracts.source_portfolio import (
                    SourcePortfolioTracker,
                    source_family,
                )
                from deepscout_research.source_fabric.strategy import (
                    DiscoveryRequest,
                    QueryStrategy,
                    infer_source_kind,
                    plan_source_strategy,
                )
                from deepscout_research.source_policy import is_excluded

                row = store.get_run_row(run_id)
                contract = contract_from_snapshot(row.config_snapshot if row else None)
                goal = row.goal if row is not None else ""
                prefs = store.list_source_preferences(run_id)
                query_params = {
                    "search_variant_count_delta": 0,
                    "zero_yield_reformulation_bonus": 0,
                }
                if row is not None:
                    from deepscout_evaluation.learning.policy_runtime import (
                        effective_query_strategy_params,
                        policy_from_run_snapshot,
                    )

                    effective = policy_from_run_snapshot(row.config_snapshot)
                    query_params = effective_query_strategy_params(effective)
                mode = run.research_mode if run else None
                source_strategy = plan_source_strategy(
                    task.objective,
                    contract,
                    research_mode=mode,
                )
                portfolio = SourcePortfolioTracker(source_strategy)
                if task.task_key == "entity-office-holder" and contract is not None:
                    planned_requests = [
                        DiscoveryRequest(
                            query=item,
                            strategy=QueryStrategy.PRIMARY,
                            source_kinds=frozenset(
                                {SourceKind.OFFICIAL_SOURCE, SourceKind.WEB_PAGE}
                            ),
                        )
                        for item in office_holder_queries(contract)
                    ]
                else:
                    base_attempts = {"quick": 2, "standard": 5, "deep": 7}.get(mode, 5)
                    delta = int(query_params.get("search_variant_count_delta", 0))
                    bonus = int(query_params.get("zero_yield_reformulation_bonus", 0))
                    minimum_attempts = max(
                        2,
                        source_strategy.minimum_query_families + 1,
                        source_strategy.target_independent_publishers + 1,
                    )
                    planned_attempt_limit = min(
                        7,
                        max(minimum_attempts, base_attempts + delta + bonus),
                    )
                    planned_requests = [
                        item.request
                        for item in search_discovery_requests(
                            task.objective,
                            contract,
                            research_mode=mode,
                            max_variants=planned_attempt_limit,
                        )
                    ]
                scoped_search = RunScopedSearchProvider(self._search, store, run_id)
                max_results = research_profile(
                    run.research_mode if run else None
                ).search_results_per_query
                for attempt, planned_request in enumerate(planned_requests):
                    request = DiscoveryRequest(
                        query=planned_request.query,
                        max_results=max_results,
                        strategy=planned_request.strategy,
                        source_kinds=planned_request.source_kinds,
                        freshness_days=planned_request.freshness_days,
                        topic=planned_request.topic,
                    )
                    query = request.query
                    budget.reserve_tool_call(
                        run_id,
                        note=f"search:{task.task_key}:attempt:{attempt + 1}",
                    )
                    # Persist the reservation before making a remote call.
                    self._persist(session, owns_session)
                    if attempt == 0:
                        graph_state = run_worker_graph(
                            run_id=run_id,
                            task_id=task.id,
                            worker_id=worker_id,
                            objective=query,
                            search_provider=scoped_search,
                            resume=True,
                            database_url=self._settings.database_url,
                            durable_checkpoint=self._settings.research_durable_langgraph_checkpoint,
                            cancelled=run is not None and run.status.value == "cancelled",
                            max_results=max_results,
                            discovery_request=request,
                        )
                        if graph_state.get("status") == "failed":
                            raise RuntimeError(graph_state.get("error") or "worker_graph_failed")
                        query = graph_state.get("query", query)
                        results = [
                            SearchResult.model_validate(item)
                            for item in graph_state.get("search_results", [])
                        ]
                    else:
                        store.increment_task_retry(task.id)
                        results = scoped_search.discover(request)
                    run = store.get_run(run_id)
                    if run is not None and run.status.value == "cancelled":
                        store.update_task_status(
                            task.id,
                            ResearchTaskStatus.CANCELLED,
                            worker_id=worker_id,
                            error_message="run_cancelled",
                        )
                        self._persist(session, owns_session)
                        return WorkerResult(
                            task.id, worker_id, success=False, error="run_cancelled"
                        )
                    provider_attempts = getattr(scoped_search, "last_attempts", ())
                    attempt_summary = ", ".join(
                        f"{item.provider}:{item.result_count if item.success else item.error}"
                        for item in provider_attempts
                    )
                    store.save_tool_execution(
                        run_id,
                        ToolExecutionWrite(
                            tool_name="web_search",
                            input_summary=query,
                            output_summary=(
                                f"{len(results)} results"
                                + (f" ({attempt_summary})" if attempt_summary else "")
                            ),
                            status=ToolExecutionStatus.SUCCESS,
                        ),
                    )
                    memory.remember_tool_summary(f"web_search:{len(results)}")
                    results_by_provider: dict[str, list[SearchResult]] = {}
                    for result in results:
                        provider_name = (result.discovery_provider or self._search.provider_name)[
                            :32
                        ]
                        results_by_provider.setdefault(provider_name, []).append(result)
                    for provider_name, provider_results in results_by_provider.items():
                        store.add_search_candidates(
                            run_id,
                            SearchCandidateWrite(
                                query=query,
                                provider=provider_name,
                                results=provider_results,
                                question_id=task.question_id,
                            ),
                        )
                    search_batches.append((query, results))
                    admitted_this_query = 0
                    for result in results:
                        safe_url = public_http_url_or_none(result.url)
                        if safe_url is None or is_excluded(safe_url, prefs):
                            continue
                        if not is_search_result_relevant(
                            title=result.title,
                            snippet=result.snippet,
                            query=query,
                            goal=goal,
                            contract=contract,
                        ):
                            continue
                        admissible, _ = is_source_admissible(
                            safe_url,
                            contract=contract,
                            preferences=prefs,
                            title=result.title,
                        )
                        if admissible:
                            enriched = result
                            if result.source_kind == SourceKind.UNKNOWN.value:
                                enriched = result.model_copy(
                                    update={
                                        "source_kind": infer_source_kind(
                                            safe_url,
                                            title=result.title,
                                        ).value
                                    }
                                )
                            if portfolio.admit(enriched):
                                admitted_this_query += 1
                    portfolio.finish_query(admitted_this_query)
                    if portfolio.adequate():
                        break
                    if attempt >= 2 and portfolio.saturated():
                        break
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
                # A database concurrency exception leaves the transaction
                # unusable. Roll back before persisting the failed execution and
                # terminal task state, while preserving the already committed
                # tool-budget reservation.
                if owns_session:
                    session.rollback()
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

            sources_added = 0
            persisted_portfolio = SourcePortfolioTracker(source_strategy)
            persisted_query_admissions: dict[str, int] = {
                batch_query: 0 for batch_query, _ in search_batches
            }

            def _office_holder_rank(item) -> int:
                lowered = f"{item.url} {item.title}".casefold()
                score = 0
                if "president" in lowered or "presidente" in lowered:
                    score += 3
                if any(
                    host in lowered
                    for host in ("commission.europa.eu", "ec.europa.eu", "europa.eu")
                ):
                    score += 2
                if any(
                    token in lowered for token in ("biography", "about", "leadership", "college")
                ):
                    score += 1
                if "eur-lex" in lowered and "president" not in lowered:
                    score -= 3
                if any(token in lowered for token in ("index", "directory", "eli/register")):
                    score -= 2
                return score

            mode_profile = research_profile(run.research_mode if run else None)
            corrective_source_reserve = (
                mode_profile.max_coverage_rounds * mode_profile.gap_queries_per_round
            )
            initial_source_cap = max(
                1,
                (run.budget.max_sources if run else 0) - corrective_source_reserve,
            )

            result_pairs = [
                (batch_query, result)
                for batch_query, batch_results in search_batches
                for result in batch_results
            ]
            office_holder_task = task.task_key == "entity-office-holder" or any(
                token in task.objective.casefold()
                for token in ("president", "presidente", "office-holder")
            )
            if office_holder_task:
                result_pairs = sorted(
                    result_pairs, key=lambda item: _office_holder_rank(item[1]), reverse=True
                )

            admitted_family_counts: dict[str, int] = {}
            for result_query, result in result_pairs:
                if (
                    not task.task_key.startswith("gap_")
                    and store.get_consumption(run_id).sources >= initial_source_cap
                ):
                    break
                safe_url = public_http_url_or_none(result.url)
                if safe_url is None:
                    continue
                if not is_search_result_relevant(
                    title=result.title,
                    snippet=result.snippet,
                    query=result_query,
                    goal=goal,
                    contract=contract,
                ):
                    continue
                if is_excluded(safe_url, prefs):
                    continue
                admissible, _reason = is_source_admissible(
                    safe_url,
                    contract=contract,
                    preferences=prefs,
                    title=result.title,
                )
                if not admissible:
                    continue
                family = source_family(safe_url, publisher=result.publisher)
                if (
                    admitted_family_counts.get(family, 0) >= 2
                    and len(portfolio.publisher_families) > 1
                ):
                    continue
                domain = urlparse(safe_url).netloc
                try:
                    # Source admission and its budget reservation are one unit. If
                    # the cap is reached, the savepoint removes the just-added row
                    # so persisted source counts cannot exceed budget consumption.
                    with store._session.begin_nested():  # noqa: SLF001
                        source_row, created = store.add_source(
                            run_id,
                            SourceWrite(
                                canonical_url=safe_url,
                                title=result.title,
                                domain=domain,
                            ),
                        )
                        if created:
                            budget.reserve_source(run_id, note=f"task:{task.task_key}")
                except BudgetExhaustedError:
                    break
                if not created:
                    continue
                sources_added += 1
                persisted_portfolio.admit(result)
                persisted_query_admissions[result_query] = (
                    persisted_query_admissions.get(result_query, 0) + 1
                )
                admitted_family_counts[family] = admitted_family_counts.get(family, 0) + 1
                if len(result.structured_content.strip()) >= 80:
                    metadata = {
                        str(key): str(value)[:4000] for key, value in result.provenance.items()
                    }
                    metadata.update(
                        {
                            "connector": result.discovery_provider or "structured_discovery",
                            "query_strategy": result.query_strategy,
                            "evidence_role": result.evidence_role,
                            "source_kind": (
                                result.source_kind
                                if result.source_kind != SourceKind.UNKNOWN.value
                                else infer_source_kind(safe_url, title=result.title).value
                            ),
                            "publisher": result.publisher,
                            "publication_date": result.published_at,
                            "fetch_url": result.fetch_url,
                            "extraction_method": "structured_provider_record",
                        }
                    )
                    store.add_snapshot(
                        source_row.id,
                        SourceSnapshotWrite(
                            content=result.structured_content,
                            mime_type=result.structured_mime_type,
                            retrieval_metadata=metadata,
                        ),
                    )
                    store.append_run_event(
                        run_id,
                        ResearchEventType.SOURCE_FETCHED.value,
                        {
                            "source_id": str(source_row.id),
                            "connector": result.discovery_provider,
                            "source_kind": metadata["source_kind"],
                            "layer": "tool",
                        },
                    )
                store.append_run_event(
                    run_id,
                    ResearchEventType.SOURCE_DISCOVERED.value,
                    {
                        "task_id": str(task.id),
                        "worker_id": str(worker_id),
                        "url": safe_url,
                        "connector": result.discovery_provider or self._search.provider_name,
                        "source_kind": (
                            result.source_kind
                            if result.source_kind != SourceKind.UNKNOWN.value
                            else infer_source_kind(safe_url, title=result.title).value
                        ),
                        "query_strategy": result.query_strategy,
                        "evidence_role": result.evidence_role,
                        "layer": "tool",
                    },
                )

            for batch_query, _ in search_batches:
                persisted_portfolio.finish_query(persisted_query_admissions.get(batch_query, 0))
            portfolio_success = sources_added > 0 and (
                persisted_portfolio.adequate() or (run is not None and run.research_mode == "quick")
            )
            if task.question_id is not None:
                status = (
                    ResearchQuestionStatus.ANSWERED
                    if portfolio_success
                    else ResearchQuestionStatus.INSUFFICIENT_EVIDENCE
                )
                store.update_question_status(task.question_id, status)

            task_status = (
                ResearchTaskStatus.COMPLETED if portfolio_success else ResearchTaskStatus.BLOCKED
            )
            blocked_reason = None
            if not portfolio_success:
                blocked_reason = (
                    "no_admissible_sources_after_retries"
                    if sources_added == 0
                    else "source_portfolio_inadequate_after_bounded_search"
                )
            store.update_task_status(
                task.id,
                task_status,
                worker_id=worker_id,
                error_message=blocked_reason,
            )
            store.append_run_event(
                run_id,
                (
                    ResearchEventType.WORKER_COMPLETED.value
                    if portfolio_success
                    else ResearchEventType.WORKER_FAILED.value
                ),
                {
                    "task_id": str(task.id),
                    "worker_id": str(worker_id),
                    "task_key": task.task_key,
                    "sources_added": sources_added,
                    "outcome": "completed" if portfolio_success else "blocked",
                    "reason": blocked_reason,
                    "search_attempts": len(search_batches),
                    "independent_publishers": len(persisted_portfolio.publisher_families),
                    "source_kinds": sorted(item.value for item in persisted_portfolio.source_kinds),
                    "portfolio_adequate": persisted_portfolio.adequate(),
                    "search_saturated": portfolio.saturated(),
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
                    "outcome": "completed" if portfolio_success else "blocked",
                    "reason": blocked_reason,
                    "source_portfolio": {
                        "independent_publishers": len(persisted_portfolio.publisher_families),
                        "source_kinds": sorted(
                            item.value for item in persisted_portfolio.source_kinds
                        ),
                        "adequate": persisted_portfolio.adequate(),
                        "saturated": portfolio.saturated(),
                        "query_yields": persisted_portfolio.query_yields,
                    },
                    "memory": memory.snapshot(),
                },
            )
            self._persist(session, owns_session)
            return WorkerResult(
                task.id,
                worker_id,
                success=portfolio_success,
                sources_added=sources_added,
                error=blocked_reason,
            )
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
