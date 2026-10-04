"""Standalone leased worker. Run only after explicit migration and spend enablement."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import socket

from folio_api.agent import RunLimits, run_agent
from folio_api.finance_tools import (
    build_tools,
    make_projection,
    make_tool_executor,
    validate_financial_answer,
)
from folio_api.jobs import TERMINAL, JobError, LeaseLost
from folio_api.providers.tool_stream import NebiusToolClient


async def run_once(queue, store, provider, *, worker_id="folio-worker", heartbeat_seconds=None):
    """Claim and finish one job; all provider/tool access stays in its tenant scope.

    Provider injection supports offline tests. The CLI enforces explicit live
    inference enablement; callers injecting a provider own the same approval gate.
    """
    lease = await asyncio.to_thread(queue.claim, worker_id)
    if lease is None:
        return False
    cancellation = asyncio.Event()
    heartbeat_seconds = heartbeat_seconds or min(1.0, queue.policy.lease_seconds / 3)
    lease_failure = None

    async def heartbeat():
        nonlocal lease_failure
        while True:
            await asyncio.sleep(heartbeat_seconds)
            try:
                if await asyncio.to_thread(queue.renew, lease):
                    cancellation.set()
            except Exception as error:
                # Stop inference even when the DB cannot verify that this worker owns it.
                lease_failure = error
                cancellation.set()
                return

    async def emit(event):
        if lease_failure is not None:
            raise LeaseLost("Lease could not be verified") from None
        # Buffer terminal output until financial validation. Unverified prose must
        # never escape through polling/SSE before the final result is checked.
        if event["type"] in {f"run.{status}" for status in TERMINAL}:
            return
        await asyncio.to_thread(queue.append_event, lease, event)

    pulse = asyncio.create_task(heartbeat())
    try:
        state = await asyncio.to_thread(store.load_workspace_for_job, lease.workspace_id)
        if state["version"] != lease.expected_version:
            raise JobError("Workspace changed before execution; refresh and retry")
        projection = make_projection(state, lease.question, lease.scope)
        execute = make_tool_executor(state, lease.scope)

        async def guarded_execute(name, arguments, operation_id):
            if await asyncio.to_thread(queue.renew, lease):
                cancellation.set()
                return {"status": "cancelled", "message": "Stopped before the tool ran."}
            return await execute(name, arguments, operation_id)

        if await asyncio.to_thread(queue.renew, lease):
            cancellation.set()
        outcome = await run_agent(
            lease.run_id,
            projection,
            build_tools(state, lease.scope),
            guarded_execute,
            emit,
            provider=provider,
            cancellation=cancellation,
            limits=RunLimits(
                max_total_tokens=min(
                    32_000, queue.policy.reservation_tokens // queue.policy.max_attempts
                )
            ),
        )
        if lease_failure is not None:
            raise LeaseLost("Lease could not be verified")
        result = {
            "status": outcome.status,
            "text": outcome.text,
            "actualInference": outcome.actual_inference,
            "usage": outcome.usage.as_dict(),
            "toolResults": list(outcome.tool_results),
            "requestIds": list(outcome.request_ids),
            "provider": outcome.provider,
            "model": outcome.model,
        }
        evidence = [fact.as_dict() for fact in projection.facts] + list(outcome.tool_results)
        if not validate_financial_answer(outcome.text, evidence):
            result.update(
                status="partial" if outcome.tool_results else "failed",
                text="The answer could not be verified against the calculations. "
                "No unverified financial result is shown.",
            )
        await asyncio.to_thread(queue.finish, lease, result)
    except LeaseLost:
        # Replacement owns the job; even a failure event from this worker is fenced.
        pass
    except asyncio.CancelledError:
        cancellation.set()
        with contextlib.suppress(LeaseLost):
            await asyncio.to_thread(
                queue.finish,
                lease,
                {
                    "status": "cancelled",
                    "text": "Stopped. Any committed work is preserved.",
                    "actualInference": False,
                    "toolResults": [],
                },
            )
        # Preserve process/task shutdown cancellation semantics.
        raise
    except Exception:
        with contextlib.suppress(LeaseLost):
            await asyncio.to_thread(
                queue.finish,
                lease,
                {
                    "status": "failed",
                    "text": "The run could not be verified. Refresh and retry.",
                    "actualInference": False,
                    "toolResults": [],
                },
            )
    finally:
        pulse.cancel()
        await asyncio.gather(pulse, return_exceptions=True)
    return True


async def serve():
    # Reuse API database/TLS validation. Neither process runs migrations implicitly.
    from folio_api.app import create_app

    app = create_app()
    if not app.state.inference_enabled:
        raise RuntimeError(
            "Worker disabled: explicitly approve live inference before enabling "
            "FOLIO_LIVE_INFERENCE_ENABLED=true with NEBIUS_API_KEY"
        )
    provider = NebiusToolClient()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    try:
        while not stop.is_set():
            if not await run_once(app.state.jobs, app.state.store, provider, worker_id=worker_id):
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=1)
    finally:
        await provider.aclose()
        app.state.store.engine.dispose()


if __name__ == "__main__":
    asyncio.run(serve())
