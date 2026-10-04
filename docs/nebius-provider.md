# Nebius inference boundary

This is a fresh implementation for the hackathon project. It has no dependency on the earlier Folio repository. Model access remains disabled until a backend credential is supplied. A credential's presence does not establish a working model, paid quota, regional availability or task quality.

## Pinned integration

- Provider: Nebius Token Factory
- Endpoint: `https://api.tokenfactory.nebius.com/v1/chat/completions`
- Model: `nvidia/nemotron-3-super-120b-a12b`
- Backend settings: `NEBIUS_API_KEY`, `NEBIUS_TIMEOUT_SECONDS` (1–120 seconds)
- No endpoint override, implicit model routing, provider substitution, redirect following or automatic SDK retries
- Requests use `store: false`. This request option is **not** a claim about the provider's complete logging, training, retention or regional-processing policy.

The official [quickstart](https://docs.tokenfactory.nebius.com/quickstart) establishes the API endpoint and authentication shape. The exact Super identifier appears in the [Nebius Nemotron example](https://nebius.com/services/token-factory/nemotron). The [API reference](https://docs.tokenfactory.nebius.com/api-reference/inference/create-chat-completion), [function-calling guide](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling) and [JSON guide](https://docs.tokenfactory.nebius.com/ai-models-inference/json) document the protocol. Actual model behaviour still needs live capability and held-out task checks; no credential or live call was used during implementation.

## Two internal entry points

`NebiusClient.generate(CloudProjection, output_schema=...)` produces a bounded answer over explicit calculation facts. It validates structured responses when a schema is supplied. This is useful for a narrow explanation, not the autonomous tool loop.

`NebiusToolClient.turn(messages, tools, max_tokens=...)` is the internal streaming transport used by `run_agent`. It assembles fragmented SSE function arguments, requires a complete finish and usage record, rejects model substitution and discards reasoning fields. It returns visible text, typed tool calls, provider request ID and measured prompt/completion tokens. Do not expose this method directly to an HTTP request or pass client-authored conversation roles.

## Agent execution contract

`run_agent` accepts a pre-persisted run ID, a server-built `CloudProjection`, a closed `ToolSpec` catalogue, an async tool executor, an awaited event writer and the provider. It sequentially:

1. Emits `run.started` before inference.
2. Calls the pinned model and records measured usage.
3. Validates every selected tool's schema and refuses identity/credential fields.
4. Requires additional server approval for write-effect tools.
5. Calls the workspace-bound executor with `run_id:tool_call_id` as an idempotency key.
6. Emits the result receipt and gives minimised structured results back to the model.
7. Ends as completed, needs_input, partial, cancelled or failed.

The event writer must persist before returning. The executor must enforce authenticated workspace membership, exact item/group scope, expected versions and approval; commit the action and idempotent receipt together. A tool name in `authorised_writes` alone is not sufficient scoped consent. The model must never choose the workspace. Client reconnect/replay and crash recovery belong to the durable run store, not the provider class.

Default ceilings are four model steps, eight tool results, 1,500 output tokens per call, 32,000 measured total tokens and 90 seconds. Each call reserves a conservative input budget using encoded message bytes plus protocol overhead. The runner preserves completed results on limit/error. An in-flight cancellation closes the streaming request; it cannot promise that a provider has not already billed generated tokens. Per-user daily and global concurrency limits must also be enforced at the API/worker boundary.

## Privacy and financial correctness

The application constructs `CloudProjection` from approved evidence. It contains a bounded question and calculation facts with integer minor units, currency, calculation IDs and source IDs. Null amounts remain null. Owner mode requires an explicit approval flag established by authenticated application policy; never trust a client-supplied flag. Anonymous workspaces must use synthetic data only.

Whole ledgers, arbitrary SQL, shell execution, bank credentials and raw account numbers have no place in this interface. Forbidden structured identity/credential fields are rejected from tool data. This allowlist does not prove that arbitrary free-text questions or fact labels contain no identifiers. A tested selective-disclosure policy and canary corpus are required before enabling real-owner inference. Do not describe this implementation as guaranteed anonymisation.

Tool schemas constrain syntax and execution, not factual correctness. Before presenting model financial prose, the application must validate figures and claims against its calculation IDs and committed receipts. Charts and surfaced money come directly from deterministic tools, never parsed from model prose. Unapproved changes remain proposals; no payments, transfers, purchases, filing or grant submissions are available tools.

## Verification status

Mock-transport tests cover protocol payloads, missing credentials, secret-safe diagnostics, pinned model, malformed/refused/truncated responses, strict JSON output, SSE tool assembly, usage, cancellation, bounded execution, cross-workspace argument rejection, unapproved writes and repeated tool IDs. These tests verify source behaviour, not live Nebius access, quality, deployment or cost.

Configuration reports `unconfigured` or `configured_unverified`. A successfully validated response records `inference_verified` and its verification time in that process. Persist actual model receipts with the run for durable provenance; do not label deterministic/manual functionality as live Nemotron work.
