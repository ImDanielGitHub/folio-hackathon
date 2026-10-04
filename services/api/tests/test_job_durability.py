from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine

from folio_api.jobs import JobError, JobPolicy, JobQueue, LeaseLost


@pytest.fixture
def queue(tmp_path):
    q = JobQueue(
        create_engine(f"sqlite:///{tmp_path / 'durable.db'}"), policy=JobPolicy(max_active_runs=1)
    )
    q.migrate()
    return q


def enqueue(q, operation="first", workspace="tenant", scope="personal"):
    return q.enqueue(
        workspace_id=workspace,
        operation_id=operation,
        question="Why?",
        scope=scope,
        expected_version=1,
    )


def test_everything_scope_and_question_roundtrip(queue):
    run = enqueue(queue, scope="everything")
    assert run["scope"] == "everything" and run["question"] == "Why?"


def test_competing_workers_have_one_global_slot(queue):
    enqueue(queue)
    enqueue(queue, operation="second", workspace="other")
    with ThreadPoolExecutor(max_workers=6) as executor:
        claimed = list(
            executor.map(
                lambda i: JobQueue(queue.engine, policy=queue.policy).claim(f"worker_{i}"), range(6)
            )
        )
    assert sum(lease is not None for lease in claimed) == 1


def test_competing_submissions_reserve_once(queue):
    with ThreadPoolExecutor(max_workers=6) as executor:
        runs = list(executor.map(lambda _: enqueue(JobQueue(queue.engine)), range(6)))
    assert len({run["runId"] for run in runs}) == 1


def test_event_conflict_rollback_and_reconnect(queue):
    run = enqueue(queue)
    lease = queue.claim("worker")
    queue.append_event(lease, {"type": "model.started", "sequence": 1})
    with pytest.raises(JobError, match="different"):
        queue.append_event(lease, {"type": "model.completed", "sequence": 1})
    recovered = JobQueue(queue.engine).get("tenant", run["runId"], after_sequence=1)
    assert [event["sequence"] for event in recovered["events"]] == [2]
    assert queue.get("tenant", run["runId"], after_sequence=2)["events"] == []


def test_expired_lease_cannot_renew_or_finish(queue):
    now = [1000.0]
    queue.clock = lambda: now[0]
    enqueue(queue)
    lease = queue.claim("worker")
    now[0] += 60
    with pytest.raises(LeaseLost):
        queue.renew(lease)
    with pytest.raises(LeaseLost):
        queue.finish(lease, {"status": "completed", "text": "late"})


def test_running_cancellation_wins_completion_race(queue):
    run = enqueue(queue)
    lease = queue.claim("worker")
    queue.cancel("tenant", run["runId"])
    queue.finish(lease, {"status": "completed", "text": "done"})
    assert queue.get("tenant", run["runId"])["status"] == "cancelled"


def test_finished_receipt_retry_is_idempotent(queue):
    run = enqueue(queue)
    lease = queue.claim("worker")
    result = {"status": "completed", "text": "done"}
    first = queue.finish(lease, result)
    second = queue.finish(lease, result)
    assert second == first
    with pytest.raises(JobError):
        queue.finish(lease, {"status": "completed", "text": "different"})
    assert len(queue.get("tenant", run["runId"])["events"]) == 2


def test_active_reservation_stays_charged_across_utc_midnight(queue):
    now = [1_800_000_000.0]
    queue.clock = lambda: now[0]
    queue.policy = JobPolicy(workspace_daily_tokens=64_000)
    enqueue(queue)
    now[0] += 86400
    with pytest.raises(JobError) as error:
        enqueue(queue, operation="tomorrow")
    assert error.value.status == 429


def test_final_usage_and_inference_receipt_survive_worker_error(queue):
    run = enqueue(queue)
    lease = queue.claim("worker")
    queue.append_event(lease, {"type": "model.started", "sequence": 1})
    queue.append_event(
        lease,
        {
            "type": "model.completed",
            "sequence": 2,
            "usage": {"promptTokens": 100, "completionTokens": 20},
        },
    )
    queue.finish(
        lease, {"status": "failed", "text": "An error occurred.", "actualInference": False}
    )
    result = queue.get("tenant", run["runId"])["result"]
    assert result["actualInference"] is True
    assert result["usage"]["totalTokens"] == 120
