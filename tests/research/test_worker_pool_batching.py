from unittest.mock import MagicMock, patch
from uuid import uuid4

from deepscout_research.workers.pool import ResearchWorkerPool, WorkerResult


def test_worker_limit_bounds_concurrency_not_ready_tasks(settings) -> None:
    tasks = [MagicMock(id=uuid4()) for _ in range(4)]
    pool = ResearchWorkerPool(
        MagicMock(),
        settings,
        MagicMock(),
        max_workers=1,
        inline_store=MagicMock(),
    )

    with patch.object(
        pool,
        "_execute_one",
        side_effect=lambda _run_id, task, **_kwargs: WorkerResult(
            task_id=task.id,
            worker_id=uuid4(),
            success=True,
        ),
    ) as execute_one:
        results = pool.execute_batch(uuid4(), tasks, iteration=1)

    assert execute_one.call_count == len(tasks)
    assert [result.task_id for result in results] == [task.id for task in tasks]
