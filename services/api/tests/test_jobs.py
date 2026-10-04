from pathlib import Path

import pytest
from sqlalchemy import create_engine

from folio_api.jobs import JobError, JobPolicy, JobQueue, LeaseLost


class Clock:
    value = 1_800_000_000.0

    def __call__(self):
        return self.value


@pytest.fixture
def queue(tmp_path: Path):
    q = JobQueue(create_engine(f"sqlite:///{tmp_path / 'jobs.db'}"), clock=Clock(),
                 policy=JobPolicy(workspace_daily_tokens=64_000))
    q.migrate()
    return q


def enqueue(q, operation="operation_one", workspace="workspace_one"):
    return q.enqueue(workspace_id=workspace, operation_id=operation,
                     question="Compare the months", scope="personal", expected_version=1)


def test_idempotency_and_conflicts(queue):
    first = enqueue(queue)
    assert enqueue(queue)["runId"] == first["runId"]
    with pytest.raises(JobError, match="different"):
        queue.enqueue(workspace_id="workspace_one", operation_id="operation_one",
                      question="Different", scope="personal", expected_version=1)


def test_wrong_workspace_cannot_read_or_cancel(queue):
    run = enqueue(queue)
    with pytest.raises(JobError) as error:
        queue.get("workspace_other", run["runId"])
    assert error.value.status == 404
    with pytest.raises(JobError):
        queue.cancel("workspace_other", run["runId"])


def test_reclaim_fences_previous_worker(queue):
    enqueue(queue)
    first = queue.claim("worker_one")
    queue.clock.value += 61
    second = queue.claim("worker_two")
    assert second.run_id == first.run_id and second.lease_token != first.lease_token
    with pytest.raises(LeaseLost):
        queue.append_event(first, {"type": "run.completed", "sequence": 1})
    assert queue.renew(second) is False


def test_durable_ordered_idempotent_events(queue):
    run = enqueue(queue)
    lease = queue.claim("worker_one")
    event = {"type": "model.started", "sequence": 1, "runId": "spoofed"}
    queue.append_event(lease, event)
    queue.append_event(lease, event)
    queue.append_event(lease, {"type": "model.completed", "sequence": 2,
                              "usage": {"promptTokens": 100, "completionTokens": 20}})
    stored = queue.get("workspace_one", run["runId"])
    assert [e["sequence"] for e in stored["events"]] == [1, 2, 3]
    assert all(e["runId"] == run["runId"] for e in stored["events"])
    queue.finish(lease, {"status": "completed", "text": "Verified", "actualInference": True})
    restored = JobQueue(queue.engine, clock=queue.clock).get("workspace_one", run["runId"])
    assert restored["status"] == "completed" and restored["usage"]["totalTokens"] == 120
    assert restored["result"]["text"] == "Verified"


def test_quota_reservation_and_release(queue):
    run = enqueue(queue)
    with pytest.raises(JobError) as error:
        enqueue(queue, "operation_two")
    assert error.value.status == 429
    lease = queue.claim("worker_one")
    queue.append_event(lease, {"type": "model.started", "sequence": 1})
    queue.append_event(lease, {"type": "model.completed", "sequence": 2,
                              "usage": {"promptTokens": 100, "completionTokens": 20}})
    queue.finish(lease, {"status": "completed", "text": "done"})
    assert queue.get("workspace_one", run["runId"])["quotaChargedTokens"] == 120
    other = enqueue(queue, "other_operation", "other_workspace")
    queue.cancel("other_workspace", other["runId"])
    assert queue.get("other_workspace", other["runId"])["quotaChargedTokens"] == 0


def test_uncertain_usage_is_conservatively_charged(queue):
    run = enqueue(queue)
    lease = queue.claim("worker_one")
    queue.append_event(lease, {"type": "model.started", "sequence": 1})
    queue.finish(lease, {"status": "cancelled", "text": "stopped"})
    result = queue.get("workspace_one", run["runId"])
    assert result["usageUncertain"] is True
    assert result["quotaChargedTokens"] == queue.policy.reservation_tokens


def test_running_cancellation_reaches_worker(queue):
    run = enqueue(queue)
    lease = queue.claim("worker_one")
    queue.cancel("workspace_one", run["runId"])
    assert queue.renew(lease) is True


def test_global_concurrency_across_instances(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'global.db'}")
    q = JobQueue(engine, policy=JobPolicy(max_active_runs=1))
    q.migrate()
    enqueue(q)
    enqueue(q, "other_op", "other_workspace")
    assert q.claim("worker_one") is not None
    assert JobQueue(engine, policy=q.policy).claim("worker_two") is None


def test_exhausted_crashed_job_is_terminal(queue):
    run = enqueue(queue)
    assert queue.claim("worker_one") is not None
    queue.clock.value += 61
    assert queue.claim("worker_two") is not None
    queue.clock.value += 61
    assert queue.claim("worker_three") is None
    result = queue.get("workspace_one", run["runId"])
    assert result["status"] == "failed" and result["usageUncertain"] is True
