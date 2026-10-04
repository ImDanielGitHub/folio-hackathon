from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from folio_api.agent import RunLimits, run_agent
from folio_api.providers.nebius import CloudProjection, EvidenceFact, NebiusSettings
from folio_api.providers.tool_stream import (
    ModelTurn,
    NebiusToolClient,
    TokenUsage,
    ToolCall,
    ToolSpec,
)


def projected() -> CloudProjection:
    return CloudProjection(
        "Compare these months",
        (EvidenceFact("calc_comparison", "Spending change", 39670, "NZD", ("txn_one",)),),
        synthetic=True,
    )


def tool(effect: str = "read") -> ToolSpec:
    return ToolSpec(
        "compare_periods",
        "Compare two periods with exact arithmetic.",
        {
            "type": "object",
            "properties": {"period": {"type": "string"}},
            "required": ["period"],
            "additionalProperties": False,
        },
        effect=effect,
    )


class StubProvider:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = turns
        self.messages: list[list[dict]] = []

    async def turn(
        self, messages: list[dict], tools: list[ToolSpec], *, max_tokens: int
    ) -> ModelTurn:
        self.messages.append(list(messages))
        return self.turns.pop(0)


def turn(*, calls: tuple[ToolCall, ...] = (), text: str = "") -> ModelTurn:
    return ModelTurn(text, calls, TokenUsage(100, 30), "chatcmpl_fixture")


@pytest.mark.asyncio
async def test_live_loop_executes_validated_call_and_feeds_result_to_next_model_step() -> None:
    provider = StubProvider(
        [
            turn(calls=(ToolCall("call_one", "compare_periods", {"period": "September"}),)),
            turn(text="See calculation calc_comparison for the spending change."),
        ]
    )
    events: list[dict] = []
    calls: list[tuple] = []

    async def execute(name: str, args: dict, operation_id: str) -> dict:
        calls.append((name, args, operation_id))
        return {"status": "completed", "calculationId": "calc_comparison", "amountMinor": 39670}

    async def emit(event: dict) -> None:
        events.append(event)

    result = await run_agent(
        "run_fixture",
        projected(),
        [tool()],
        execute,
        emit,
        provider=provider,
    )
    assert result.status == "completed"
    assert result.actual_inference is True
    assert result.usage.total_tokens == 260
    assert len(calls) == 1
    assert calls[0][2] == "run_fixture:call_one"
    assert provider.messages[1][-1]["role"] == "tool"
    assert json.loads(provider.messages[1][-1]["content"])["amountMinor"] == 39670
    assert events[0]["type"] == "run.started"
    assert any(event["type"] == "tool.completed" for event in events)
    assert events[-1]["type"] == "run.completed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        ToolCall("call_bad", "arbitrary_sql", {"query": "SELECT *"}),
        ToolCall("call_bad", "compare_periods", {"period": "September", "workspaceId": "other"}),
        ToolCall("call_bad", "compare_periods", {"period": 123}),
    ],
)
async def test_invalid_tool_never_executes(call: ToolCall) -> None:
    provider = StubProvider([turn(calls=(call,))])

    async def execute(*_: object) -> dict:
        pytest.fail("Invalid or cross-workspace call executed")

    async def emit(_: dict) -> None:
        pass

    result = await run_agent("run_bad", projected(), [tool()], execute, emit, provider=provider)
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_write_without_approval_ends_needs_input_without_execution() -> None:
    provider = StubProvider(
        [
            turn(
                calls=(
                    ToolCall(
                        "call_write",
                        "compare_periods",
                        {"period": "September"},
                    ),
                )
            )
        ]
    )

    async def execute(*_: object) -> dict:
        pytest.fail("Unapproved write executed")

    async def emit(_: dict) -> None:
        pass

    result = await run_agent(
        "run_write",
        projected(),
        [tool("write")],
        execute,
        emit,
        provider=provider,
    )
    assert result.status == "needs_input"
    assert result.pending_tool is not None


@pytest.mark.asyncio
async def test_budget_reached_returns_partial_and_preserves_work() -> None:
    provider = StubProvider(
        [
            turn(
                calls=(
                    ToolCall(
                        "call_budget",
                        "compare_periods",
                        {"period": "September"},
                    ),
                )
            )
        ]
    )

    async def execute(*_: object) -> dict:
        return {"status": "completed", "calculationId": "calc_comparison"}

    async def emit(_: dict) -> None:
        pass

    result = await run_agent(
        "run_budget",
        projected(),
        [tool()],
        execute,
        emit,
        provider=provider,
        limits=RunLimits(max_model_steps=1),
    )
    assert result.status == "partial"
    assert len(result.tool_results) == 1


@pytest.mark.asyncio
async def test_cancelled_run_never_calls_provider() -> None:
    cancellation = asyncio.Event()
    cancellation.set()
    provider = StubProvider([])

    async def execute(*_: object) -> dict:
        pytest.fail("Cancelled run executed a tool")

    async def emit(_: dict) -> None:
        pass

    result = await run_agent(
        "run_cancel",
        projected(),
        [tool()],
        execute,
        emit,
        provider=provider,
        cancellation=cancellation,
    )
    assert result.status == "cancelled"
    assert provider.messages == []


@pytest.mark.asyncio
async def test_sse_assembles_fragmented_tool_arguments_and_records_usage() -> None:
    frames = [
        {
            "id": "chatcmpl_stream",
            "model": "nvidia/nemotron-3-super-120b-a12b",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_stream",
                                "type": "function",
                                "function": {"name": "compare_periods", "arguments": '{"per'},
                            }
                        ]
                    },
                }
            ],
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "reasoning_content": "hidden",
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": 'iod":"September"}'}}
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {"choices": [], "usage": {"prompt_tokens": 200, "completion_tokens": 50}},
    ]
    wire = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames) + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["stream_options"]["include_usage"] is True
        assert body["tools"][0]["function"]["name"] == "compare_periods"
        return httpx.Response(200, text=wire, headers={"Content-Type": "text/event-stream"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider = NebiusToolClient(NebiusSettings(api_key="fixture"), transport=transport)
        result = await provider.turn(
            [{"role": "user", "content": "synthetic"}], [tool()], max_tokens=500
        )
    assert result.tool_calls[0].arguments == {"period": "September"}
    assert result.usage.total_tokens == 250
    assert "hidden" not in result.text


@pytest.mark.asyncio
async def test_incomplete_sse_is_not_a_success() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, text='data: {"choices":[]}\n\n')
        )
    ) as transport:
        provider = NebiusToolClient(NebiusSettings(api_key="fixture"), transport=transport)
        with pytest.raises(RuntimeError):
            await provider.turn(
                [{"role": "user", "content": "synthetic"}], [tool()], max_tokens=500
            )


@pytest.mark.asyncio
async def test_inflight_cancellation_closes_provider_work_promptly() -> None:
    cancellation = asyncio.Event()
    entered = asyncio.Event()
    closed = asyncio.Event()

    class WaitingProvider:
        async def turn(self, *_: object, **__: object) -> ModelTurn:
            entered.set()
            try:
                await asyncio.sleep(20)
            finally:
                closed.set()
            raise AssertionError("Should have been cancelled")

    async def execute(*_: object) -> dict:
        pytest.fail("Cancelled run executed a tool")

    async def emit(_: dict) -> None:
        pass

    task = asyncio.create_task(
        run_agent(
            "run_cancel_inflight",
            projected(),
            [tool()],
            execute,
            emit,
            provider=WaitingProvider(),
            cancellation=cancellation,
        )
    )
    await entered.wait()
    cancellation.set()
    result = await asyncio.wait_for(task, timeout=0.5)
    assert result.status == "cancelled"
    assert closed.is_set()


@pytest.mark.asyncio
async def test_repeat_call_identity_does_not_repeat_side_effect() -> None:
    repeated = ToolCall("call_repeat", "compare_periods", {"period": "September"})
    provider = StubProvider([turn(calls=(repeated,)), turn(calls=(repeated,)), turn(text="Done.")])
    count = 0

    async def execute(*_: object) -> dict:
        nonlocal count
        count += 1
        return {"status": "completed", "calculationId": "calc_comparison"}

    async def emit(_: dict) -> None:
        pass

    result = await run_agent("run_repeat", projected(), [tool()], execute, emit, provider=provider)
    assert result.status == "completed"
    assert count == 1


@pytest.mark.asyncio
async def test_secret_tool_fields_never_reach_the_model() -> None:
    provider = StubProvider(
        [
            turn(
                calls=(
                    ToolCall(
                        "call_secret",
                        "compare_periods",
                        {"period": "September"},
                    ),
                )
            )
        ]
    )

    async def execute(*_: object) -> dict:
        return {"status": "completed", "api_key": "private-canary"}

    async def emit(_: dict) -> None:
        pass

    result = await run_agent("run_secret", projected(), [tool()], execute, emit, provider=provider)
    assert result.status == "failed"
    assert len(provider.messages) == 1
    assert "private-canary" not in json.dumps(provider.messages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"choices": [None]},
        {"choices": [{"delta": []}]},
        {"choices": [], "usage": []},
        {"choices": [{"delta": {"tool_calls": [None]}}]},
    ],
)
async def test_malformed_stream_is_redacted(payload: dict) -> None:
    wire = f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=wire))
    ) as transport:
        provider = NebiusToolClient(NebiusSettings(api_key="fixture"), transport=transport)
        with pytest.raises(RuntimeError, match="unavailable or invalid"):
            await provider.turn(
                [{"role": "user", "content": "synthetic"}], [tool()], max_tokens=500
            )
