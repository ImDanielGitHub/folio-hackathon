# Folio release acceptance

Updated 4 October 2026. This is an implementation status record, not a completion claim.

## Authority and scope

- Fresh project. Do not publish or modify the old Folio repository.
- The 50-page Folio v1.0 handover supplies functional, safety and release requirements.
- Paper Folio Components, Mac and Web judge pages supply actual visual design. No reference screenshots are distributed with source.
- User-approved change: React web first, shared React + Tauri desktop for Mac/Linux instead of SwiftUI. Native Mac validation requires a Mac runner.
- Portable architecture: Nebius API, durable worker, PostgreSQL and object storage. User subsequently approved Sites fallback after no usable hosting grant was found. Sites uses the same client contracts with a Worker/D1 synthetic adapter; it does not provide the independent background-worker guarantee.
- Demo is synthetic and isolated. Real data, bank access, new credentials and paid resources require their separate approvals.

## Evidence so far

- TypeScript check and Vite production build passed on 4 October.
- Latest aggregate Python run: 154 tests pass after fixing a random citation-UUID parsing regression. Sites adapter: 28 deterministic tests pass with an in-memory SQLite/D1 adapter. Shared React typecheck/production build passes.
- Nine Tauri deployment/security configuration tests passed. Native compilation and cookie persistence across desktop restart have not run.
- Source has 341 fictional transactions, exact minor-unit comparison, reversible manual annotation/splits, goals, scoped correction records, isolated cookie sessions and versioned idempotent writes.
- Nemotron provider and bounded real tool-stream loop source exists. Tests use controlled transports. No live inference has been verified.
- Public synthetic Sites preview deployed on 4 October: https://folio-finance-coach.imdaniel.chatgpt.site. Browser verified anonymous first-run, exact comparison, goal save/reload/edit/undo, scoped phone split/recalculation/undo, dark appearance and truthful model-unavailable state. A separate public GitHub repository, mobile viewport and native QA remain pending.

## Screen/flow gates

| Handover screen | Current status | Remaining proof |
|---|---|---|
| S01 welcome/demo | Implemented source, API tests | Fresh browser/native journey, sign-out invalidation |
| S02 profile/consent | Missing | Separate permissions and provenance |
| S03 connections | Disabled honestly | Akahu/Plaid adapters, callbacks, fixtures, authorised testing |
| S04 CSV | Missing in current shared frontend | Preview, ambiguity, batch commit and duplicate protection |
| S05 first useful work | Deterministic sample comparison | Unscripted model-led bounded organisation |
| S06 Today/conversation | Persisted run/history/reconnect source | Browser proof; Sites request-bound execution only; dismiss/snooze |
| S07 money/evidence | Exact comparison tools | Live query, follow-up context, dates and evidence UI |
| S08 transactions | Filtering/inspector source | Keyboard, stable selection and browser tests |
| S09 detail/split | Exact split/undo tested; deployed browser 60/40 phone split and undo passed | Refund UI and native journeys |
| S10 grouped review | Manual bounded confirmation | Actual model uncertainty, learned example and counterexample |
| S11 breakdowns | Exact scoped totals | Currency/transfer/refund/coverage golden corpus |
| S12 capacity | Editable explicitly hypothetical scenario source; saved inputs, exact monthly and separate cash arithmetic, scoped tools, undo and timezone tests | Deployed UI QA; real evidence-backed projections and commitment ingestion |
| S13 goals | Edit/archive, timezone, baseline and unknown progress tested in Python; shared UI updated | Browser/native proof; edge timezone/coverage parity |
| S14 recurring | Missing | Confirmed series, variable/annual charges |
| S15 opportunities | Honest unavailable state | Permissioned research, freshness, dismiss |
| S16 phone comparison | Missing | Official-source terms, billing arithmetic, unknown fees |
| S17 outcome tracking | Missing | Projected/reported/observed distinctions |
| S18 grants | Missing, P1 | Official conditions and Unknown eligibility |
| Remaining settings/activity/memory/remote/release screens | Partial activity/memory/settings source | Full handover interactions, deletion, quiet controls, secure Telegram and packaging |

## Named acceptance tests

Passing a related unit test does not mean the whole release scenario has passed.

| ID | Required outcome | Status |
|---|---|---|
| T01 | Repeated CSV adds no duplicates | Pending |
| T02 | Ambiguous date asks for confirmation | Pending |
| T03 | Pending replacement avoids duplication | Pending |
| T04 | Transfers excluded | Additional fixture verification pending |
| T05 | Refunds net correctly with evidence | Pending |
| T06 | 60/40 exact split and undo | Domain/API and deployed browser proof pass on synthetic phone charge |
| T07 | Correction scope stays bounded | Manual scope tests; learned reuse pending |
| T08 | Stale multi-client write rejected | API version conflict passes; remote client pending |
| T09 | Retry after commit returns original result | API idempotency and retained client operation-ID tests pass; browser fault injection pending |
| T10 | Cloud outage preserves cached views | Pending |
| T11 | Irregular income not guaranteed | Hypothetical variable income excluded by default; opt-in uncertainty tested; real income corpus pending |
| T12 | NZD/USD never silently summed | Full corpus pending |
| T13 | Goal month boundary uses timezone | Pending |
| T14 | Personal goal excludes business | Pending |
| T15 | Missing data distinct from zero | Comparison unit proof; broader coverage pending |
| T16 | Promotion expiry included | Pending |
| T17 | Unknown exit fee blocks exact savings | Pending |
| T18 | 28-day billing arithmetic | Pending |
| T19 | Coverage mismatch rejected | Pending |
| T20 | Expired source rechecked/unavailable | Pending |
| T21 | Eligibility Unknown preserved | Pending |
| T22 | No sensitive eligibility inference | Pending |
| T23 | Prompt injection cannot disclose private data | Provider projection tests; research ingestion pending |
| T24 | Foreign tenant IDs rejected | API/tool tests pass; full adversarial corpus pending |
| T25 | Telegram replay one effect | Pending |
| T26 | DST quiet hours do not duplicate digest | Pending |
| T27 | Malformed model output recoverable | Provider tests; end-to-end pending |
| T28 | Token cap yields bounded partial result | Agent tests; durable accounting pending |
| T29 | Deletion/revocation effective | Pending |
| T30 | Fresh judge completes real model flow | Pending |

## Submission gates

No release is ready until the thin vertical slice works without developer assistance: fresh session, real Nemotron query, exact typed evidence, reversible correction, goal, one useful verified opportunity and persisted receipts. Four diverse synthetic accounts and held-out evaluations remain required. No measured precision, task-success, first-value or model-tier claim is made.

Deployment also requires a verified Nebius project/region, scoped secure credentials, approved usage budget, TLS and PostgreSQL verification, durable worker restart tests, backups/restore, browser QA, public-repository authorisation/licence review, and a working judge path maintained through the judging period.
