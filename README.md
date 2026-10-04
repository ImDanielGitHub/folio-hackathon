# Folio

Fresh hackathon rebuild: a source-grounded finance workspace for web, Mac and Linux. The web judge experience uses fictional records only. Exact money arithmetic, authorisation, durable state and explicit confirmation remain conventional code; NVIDIA Nemotron through Nebius Token Factory selects and explains bounded finance tools.

## Current state

This is an implementation in progress, not a completed financial service. The React interface, exact synthetic comparisons, review, reversible splits, goals, explicitly hypothetical income/capacity scenarios, scoped correction memory and activity work through the API. Live model use stays disabled until its server-side key and usage approval are configured. There are no fabricated model responses or live bank badges.

See [release acceptance](docs/acceptance-status.md) for the full unfinished requirements. CSV import, recurring/digest workflows, verified phone-plan research, production banking, full held-out evaluation and signed native releases are not complete.

## Architecture

- `apps/web-demo`: shared React/Vite working surface, Paper-derived Newsreader/Inter design
- `apps/desktop`: Tauri 2 shell for the same web application, Mac/Linux build gates
- `apps/edge`: Sites-compatible Worker and D1 synthetic-demo adapter
- `services/api`: portable FastAPI/PostgreSQL API and independently running leased worker
- `deploy/nebius`: optional approved-infrastructure deployment source; nothing provisioned by this repository

The Sites fallback persists each model step, evidence, quota and receipt in D1. It advances while a client is connected and can resume saved work. **It does not claim independent background execution while the client is closed.** The portable Python worker implements that capability separately and still needs hosting.

## Development

Requires Node 24 and Python 3.12.

```sh
npm ci
npm --prefix apps/web-demo ci
npm run test:edge
npm run build
cd services/api
uv sync --frozen
uv run pytest -q
```

For the portable development API, explicitly migrate a disposable local database:

```sh
cd services/api
DATABASE_URL=sqlite:////tmp/folio-dev.sqlite3 uv run python -c "from folio_api.app import app; app.state.store.migrate(); app.state.jobs.migrate()"
DATABASE_URL=sqlite:////tmp/folio-dev.sqlite3 uv run uvicorn folio_api.app:app --host 127.0.0.1 --port 8876
```

Run `npm run web` in another terminal. Vite proxies `/v1` to the development API. A model key is not needed for deterministic comparisons and manual review.

D1 schema lives in `apps/edge/db/schema.ts`; `npm run db:generate` generates append-only migrations. Production schema changes are never made inside a request. Edge tests use an in-memory SQLite adapter for the D1 prepared-statement/batch contract; deployed D1 verification is a separate gate.

## Inference and safety

The pinned model is `nvidia/nemotron-3-super-120b-a12b`, using `https://api.tokenfactory.nebius.com/v1/chat/completions`. No fallback provider is substituted. Configure `NEBIUS_API_KEY` only in protected server secret storage, never a browser bundle, repository, URL or chat. Both this secret and `FOLIO_LIVE_INFERENCE_ENABLED=true` are required. Enabling paid/credit-backed usage requires the account owner's explicit approval.

Runs reserve at most 32,000 tokens and allow at most four model steps/eight tools. The anonymous Sites demo caps reservations at 64,000 tokens per workspace/day and 320,000 globally/day, with at most four active model steps. These are token controls, not a verified monetary spending cap. Unknown provider usage is charged conservatively. The service never pays, transfers, switches plans or submits applications.

The application validates financial figure strings against signed, currency-specific typed evidence. This is an additional fail-closed safeguard, not proof of semantic correctness. Real model evaluations, user testing and privacy/financial review remain release gates.

## Tests and provenance

Deterministic model-transport mocks are explicitly separated from live inference. No passing mocked test is described as a real provider success. Original synthetic transaction amounts are immutable; annotations and operation receipts provide scoped changes and undo. Tenant identity is cookie-derived, never a model argument.

The illustrated handover and third-party reference screenshots are private design inputs and are not included. Bundled Inter and Newsreader fonts retain their own licence files under `apps/web-demo/public/fonts`. No code is imported from the user's old Folio repository.

## Licence

Original project source is MIT-licensed. Fonts and third-party dependencies retain their respective licences. See `LICENSE` and bundled font notices.
