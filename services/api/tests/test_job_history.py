import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from folio_api.app import create_app
from folio_api.jobs import JobError, JobQueue


def enqueue(queue, workspace, operation):
    return queue.enqueue(
        workspace_id=workspace,
        operation_id=operation,
        question="Why?",
        scope="personal",
        expected_version=1,
    )


def test_recent_history_is_tenant_scoped_and_bounded(tmp_path):
    clock = [100.0]
    queue = JobQueue(create_engine(f"sqlite:///{tmp_path / 'history.db'}"), clock=lambda: clock[0])
    queue.migrate()
    first = enqueue(queue, "one", "first")
    queue.cancel("one", first["runId"])
    clock[0] += 1
    last = enqueue(queue, "one", "last")
    enqueue(queue, "two", "foreign")
    history = queue.list("one")
    assert [run["runId"] for run in history] == [last["runId"], first["runId"]]
    assert len(queue.list("one", limit=1)) == 1
    assert queue.list("unknown") == []
    for limit in (0, 101, True, "2"):
        with pytest.raises(JobError):
            queue.list("one", limit=limit)


def test_history_api_recovers_only_the_authenticated_workspace(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'api.db'}", testing=True)
    one, two = TestClient(app), TestClient(app)
    headers = {"origin": "http://testserver"}
    state = one.post("/v1/demo/session", json={}, headers=headers).json()
    two.post("/v1/demo/session", json={}, headers=headers)
    run = enqueue(app.state.jobs, state["id"], "saved")
    response = one.get("/v1/demo/runs")
    assert response.status_code == 200
    assert response.json()["runs"][0]["runId"] == run["runId"]
    assert two.get("/v1/demo/runs").json() == {"runs": []}
    assert TestClient(app).get("/v1/demo/runs").status_code == 401
    assert one.get("/v1/demo/runs?limit=101").status_code == 422
