# Folio hackathon design contract

Observed directly in Paper, 4 October 2026. New project; do not import the earlier Folio repository.

Source: https://app.paper.design/file/01M418RQDCFF3X99BWT5TTCG4Y/p-1-0
Components: https://app.paper.design/file/01M418RQDCFF3X99BWT5TTCG4Y/p-2-0
Mac light: https://app.paper.design/file/01M418RQDCFF3X99BWT5TTCG4Y/p-3-0
Web judge companion: https://app.paper.design/file/01M418RQDCFF3X99BWT5TTCG4Y/p-4-0

## Product
Folio notices a money problem, checks the evidence, and does the agreed work. Native Mac finance coach/operator; limited synthetic-data web judge companion; Telegram safe-summary surface. Nemotron on Nebius Token Factory. Observe → understand → investigate → organise → explain → agree → follow through. A run ends only with a saved outcome, honest partial result, or needed question. Model plans and chooses typed tools; deterministic code owns maths, permissions, storage, and side effects.

## Behaviour
- One digest by default. Merge similar findings. Dismissed insights do not return unchanged.
- Reversible annotations: categories, splits, goals. Never autonomously pay, transfer, switch providers, or submit grants.
- Ask about groups, with item/group scope explicit. Large ambiguity needs review regardless of reported confidence.
- Every number links to a calculation ID and source records. Never model-calculated chart data.
- Display work stages and receipts, not hidden reasoning.
- Scoped inspectable memory: item correction is not a global merchant rule. Suggested rules never appear user-confirmed.
- Distinguish projected, user-reported and observed savings. Always allow keeping the existing plan.
- New Zealand English. No shame, no diagnosis. “Business” rather than tax-deductible. Unknown/empty is not zero.

## Tokens and primitives
Light: canvas #F6F6F4; surface #FFFFFF; sunken #F0F0EE; border #E6E6E2; ink #1C1F1E; secondary #5C625F; accent #1F4D3F; selection #F2F3F1; success #2E6B4F; warning #9A5B12; danger #C2413A.
Dark: canvas #121413; surface #1A1D1C; border #2A2E2C; ink #ECEDEA; accent #8CC3AC.
Newsreader headlines and hero amounts; Inter tabular numerals elsewhere. Display 40; title 28; section 18/24 semibold; body 14/22; label 12/16 medium. Money integer minor units; no floating point storage.
Evergreen only for primary action/links. Neutral selections. No tinted panels/accent stripes; no pill status backgrounds or uppercase eyebrow copy. Hairlines before boxes. Bars/tables before doughnuts; every chart has matching data table. Motion 120–200ms, reduced-motion support, no fake typing.
Mac widths: 212px sidebar, fluid main, 340px inspector. Collapse gracefully at 1024×720. Buttons 32px Mac, 36px web, 44px touch. Irreversible/external action never default Return.

## Screens observed
Welcome and instant demo; CSV preview with explicit date interpretation, deduplication and skipped-row reasons; first useful work receipt; Today attention brief; command palette/menu bar; Money questions plus evidence canvas; transactions plus inspector; grouped review and scoped learning; goal preview with explicit save; income/capacity forecast with assumptions; recurring bills; opportunity shortlist; plan comparison; grants eligibility; memory; coaching/privacy settings; activity receipts and undo; connections with truthful live/testing/sandbox labels and stale data.

Mac navigation: Today, Money, Goals, Opportunities, separator Workspace, Review, Transactions, Bills & subscriptions, Activity, Memory, Connections. Header scope Everything / Personal / Aneke Studio plus search. Inspector stays beside list.

## Web reference W01
1440×900 entry: Folio logo, How it works, Privacy, Download for Mac. “For Nebius × NVIDIA judges”; Newsreader “Try the real agent with pretend money.” Primary opens private demo workspace, secondary 3-minute video only when real video exists. Five suggested journeys: September comparison; grouped review; phone split; eating-out goal; cheaper phone. No bank login, synthetic-only, usage limit and reset. Never claim live Nemotron without successful provider configuration and actual inference proof.

## Web reference W02
1440×900 canvas. Thin dark synthetic-data banner. Top horizontal Folio / Today / Money / Goals / Opportunities / Review nav, Sam Rivera demo at right. Wide white conversation, narrow neutral evidence panel on right. Greeting Newsreader 38/44 at letter-spacing -0.02em. Body Inter 15/23. Conversation width 640, 22px gaps. User question right-aligned with #F0F0EE rounded 12px bubble. Bottom composer border 1px, radius12, 14px vertical padding, 16px left padding; send button28px radius8. Evidence panel category comparison with strong top rule and right-aligned amounts. Dark equivalent uses explicit dark tokens.

Reference amounts must be deterministic outputs of a consistent synthetic fixture, not asserted independently: September $3,412.80, August $3,016.10, delta $396.70. Category changes: eating out +248.30; unsorted +204.10; power +61; transport +56.30; groceries +12.70; other -185.70. All reconcile.

## Provider architecture
Updated implementation decision: React web first with Tauri Mac/Linux wrappers, using the same API; public companion is synthetic only. Nebius API and durable worker (Serverless Endpoint and Jobs), Managed PostgreSQL and object storage. Nemotron Nano routing, Super/Ultra reasoning via Token Factory. CSV and synthetic demo available from first run. Akahu NZ and Plaid US adapter with honest environment statuses. Telegram only safe summaries/opaque IDs; high-impact actions and exports in app. Real financial data must not enter public demo.

## Verified external constraints
Devpost rules: https://nebiusglobalaihackathon.devpost.com/rules
Deadline Oct30 2026 10:00 PDT (Oct31 06:00 NZDT). Runtime must call Token Factory or run on Nebius AI Cloud and use an NVIDIA open-source model. Serverless Endpoint/Jobs encouraged for Best Apps & Agents, not mandatory under event rules, but required by this user's selected architecture. Public open-source repository with license, README, working demo/test build and video under3min. Existing project only eligible with significant updates during submission window; this project is explicitly fresh.

## Open proof gates
Full 50-page handover reviewed as private input. Nebius login/project/region, resource price and spend authorisation, provisioned PostgreSQL/object storage, secure inference key installation, sender/authentication path, live runtime verification, Tauri Mac/Linux compilation and Mac signing/notarisation, browser screenshot QA and all acceptance tests. None may be reported complete from this contract alone.
