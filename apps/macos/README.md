# Folio native Mac source

Native implementation work is paused while the desktop platform direction is being decided. This folder is a fresh SwiftUI source scaffold, **not a compiled, signed or tested release**. No earlier Folio project source was reused.

## Requirements and local run

- macOS 26, Xcode 26 or newer, and selected Xcode command-line tools.
- Start the repository's synthetic API separately, then run `./script/build_and_run.sh` from this folder.
- The app defaults to `http://127.0.0.1:8000`. Settings → Connections accepts an HTTPS backend address (localhost HTTP is allowed). Do not enter provider secrets.
- The backend must explicitly allow the native origin `folio://macos`.
- Use `./script/build_and_run.sh --test` for Swift tests, `--build-only` to stage `dist/Folio.app`, or `--verify` to launch and check the process. `--debug`, `--logs`, and `--telemetry` are optional diagnostics.
- The bundle uses a development ad hoc signature. Distribution signing, hardened runtime, notarisation, and fresh-Mac installation testing remain required. Do not disable Gatekeeper.

## Source layout

- `FolioCore`: integer money, local CSV preview, injectable async service, wire DTOs and typed HTTP actor.
- `FolioApp`: native window/settings/menu-bar scenes, Paper light/dark tokens, 212-point sidebar and 340-point evidence inspector, command palette and feature views.
- `Tests/FolioCoreTests`: exact amounts, 60/40 split rounding, date interpretation, invalid rows, duplicate visibility, null coverage, URL validation and API decoding.

The existing source covers Today/evidence, transaction inspection, purpose correction for one item or an explicit group, a transaction-only split, scoped memory, server-confirmed goal creation and activity undo. The native API boundary sends an operation UUID and the current server workspace version. All mutations await a returned server state. No local fixture silently substitutes for a failed server or model.

CSV preview is local-only, capped at 5 MB, and accepts Date, Description/Merchant and Amount columns. It preserves rejected and possible-duplicate rows. It cannot upload or commit private financial data to the synthetic API. Bank linking, private account authentication and Keychain-backed real session handling are deliberately not represented as finished.

## Verification record

On 4 October 2026, in the Linux cloud workspace:

- `swift test`: **not run**, command unavailable (`swift: command not found`).
- `bash -n script/build_and_run.sh`: passed shell syntax validation.
- `./script/build_and_run.sh --build-only`: correctly stopped with the macOS/Xcode requirement before building.
- No Swift compiler, native UI run, screenshot comparison, VoiceOver pass, distribution signing or notarisation was possible.

Tests are source only; no red/green execution is claimed. The app's full DTO decode and native UI must be exercised against the final API response contract before it is described as working. In particular, the live ask result's provider receipt schema is pending final server alignment.

## Remaining gates

1. Decide whether to retain SwiftUI or replace the desktop client after the cross-platform decision.
2. Compile and fix diagnostics on macOS 26; execute all Swift tests and the narrow-window/light/dark/keyboard/VoiceOver checks.
3. Verify bundled Newsreader and Inter PostScript names, resource registration, and exact Paper frame comparison. Newsreader must actually be present before claiming typographic fidelity.
4. Align and test live ask receipt decoding with the final backend. Unconfigured inference remains an honest server error.
5. Verify session restore, cookie storage, expiry, rejected versions, lost-response recovery and offline cache behaviour. The current view is kept in memory on a failed refresh; durable offline financial caching is not implemented.
6. Add validated private-workspace authentication and uploads, permission/capability flags, bank authorisation, durable cancellation, and production distribution only after their own acceptance work.

Bills and Opportunities show truthful evidence/capability states. There are no invented bill dates, verified offer prices, savings claims, bank status, or successful inference indicators.
