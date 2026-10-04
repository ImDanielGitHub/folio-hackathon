import asyncio
import json

import pytest

from folio_api.jobs import JobQueue
from folio_api.providers.tool_stream import ModelTurn, TokenUsage
from folio_api.store import Store


@pytest.fixture
def setup(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'worker.db'}", testing=True)
    _, state = store.create_session()
    queue = JobQueue(store.engine)
    queue.migrate()
    run = queue.enqueue(
        workspace_id=state["id"],
        operation_id="worker_op",
        question="Compare the months",
        scope="personal",
        expected_version=1,
    )
    return store, state, queue, run


class Provider:
    def __init__(self, text="No verified income was provided."):
        self.text = text
        self.calls = 0

    async def turn(self, messages, tools, *, max_tokens):
        self.calls += 1
        return ModelTurn(self.text, (), TokenUsage(100, 20), "request_1")


async def test_worker_persists_verified_completion(setup):
    from folio_api.worker import run_once

    store, state, queue, run = setup
    provider = Provider()
    assert await run_once(queue, store, provider, worker_id="test") is True
    saved = queue.get(state["id"], run["runId"])
    assert saved["status"] == "completed"
    assert saved["question"] == "Compare the months"
    assert saved["result"]["actualInference"] is True
    assert saved["result"]["toolResults"] == []
    assert saved["usage"]["totalTokens"] == 120
    assert saved["events"][-1]["type"] == "run.completed"
    assert await run_once(queue, store, provider, worker_id="test") is False


async def test_worker_never_publishes_ungrounded_final_money(setup):
    from folio_api.worker import run_once

    store, state, queue, run = setup
    await run_once(queue, store, Provider("You saved $999.00."), worker_id="test")
    saved = queue.get(state["id"], run["runId"])
    assert saved["status"] == "failed"
    assert "$999" not in json.dumps(saved)
    assert saved["result"]["actualInference"] is True


async def test_worker_rejects_stale_workspace_before_inference(setup):
    from folio_api.worker import run_once

    store, state, queue, run = setup
    from folio_api.store import workspaces

    with store.engine.begin() as con:
        state["version"] += 1
        con.execute(workspaces.update().values(state=json.dumps(state)))
    provider = Provider()
    await run_once(queue, store, provider, worker_id="test")
    assert provider.calls == 0
    assert queue.get(state["id"], run["runId"])["status"] == "failed"


async def test_worker_cancels_inflight_model_and_charges_uncertain_usage(setup):
    from folio_api.worker import run_once

    store, state, queue, run = setup
    started = asyncio.Event()
    stopped = asyncio.Event()

    class SlowProvider:
        async def turn(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

    task = asyncio.create_task(
        run_once(queue, store, SlowProvider(), worker_id="test", heartbeat_seconds=0.01)
    )
    await asyncio.wait_for(started.wait(), 2)
    queue.cancel(state["id"], run["runId"])
    await asyncio.wait_for(task, 2)
    assert stopped.is_set()
    saved = queue.get(state["id"], run["runId"])
    assert saved["status"] == "cancelled"
    assert saved["usageUncertain"] is True
    assert saved["quotaChargedTokens"] == queue.policy.reservation_tokens


async def test_worker_cancel_between_model_and_tool_does_not_stop_worker(setup):
    from folio_api.providers.tool_stream import ToolCall
    from folio_api.worker import run_once

    store, state, queue, run = setup
    renew = queue.renew
    calls = 0

    def cancel_at_tool(lease):
        nonlocal calls
        calls += 1
        if calls == 2:
            queue.cancel(state["id"], run["runId"])
        return renew(lease)

    queue.renew = cancel_at_tool

    class ToolProvider:
        async def turn(self, *args, **kwargs):
            return ModelTurn(
                "",
                (ToolCall("call_1", "calculate_capacity", {}),),
                TokenUsage(100, 20),
                "request_1",
            )

    assert await run_once(queue, store, ToolProvider(), worker_id="test") is True
    assert queue.get(state["id"], run["runId"])["status"] == "cancelled"


async def test_worker_can_ground_direct_answer_in_typed_projection(setup):
    from folio_api.finance_tools import make_projection
    from folio_api.worker import run_once

    store, state, queue, run = setup
    fact = make_projection(state, "Compare the months", "personal").facts[0]
    answer = f"{fact.currency} {fact.amount_minor / 100:.2f} [{fact.calculation_id}]"
    await run_once(queue, store, Provider(answer), worker_id="test")
    saved = queue.get(state["id"], run["runId"])
    assert saved["status"] == "completed"
    assert saved["result"]["text"] == answer
