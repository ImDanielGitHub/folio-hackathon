# Direct New Zealand open banking

Status checked 4 October 2026. This is an implementation and test record, not a claim that Folio is connected to a bank.

## Implemented locally

- Provider-neutral, tenant-scoped staging ledger with explicit `fixture` or `sandbox` provenance and explicit provider identity.
- Payments NZ Account Information v2.3.3 normalizers for selected accounts, typed balances and booked/pending transactions.
- Original fictional fixtures, created for this repository. No bank sandbox response or customer data is included.
- Exact decimal-to-minor-unit conversion, explicit credit/debit signs and currency checks. Extra decimal zeroes are retained; genuine fractions of a cent are quarantined without rounding.
- Stable provider identities remain opaque. Booked entries without a stable transaction ID are quarantined, not assigned a guessed fingerprint.
- Strict timezone offsets and stale-balance fences prevent a malformed or older snapshot from moving the ledger backwards. Conflicting credit-line disclosure at the same source timestamp is rejected. Source timestamps beyond microsecond precision fail explicitly as unsupported unless the extra digits are all zero; no sub-microsecond ordering is silently rounded.
- Source booking timestamp retained; display date is converted into the supplied workspace timezone. Booking time is not labelled as purchase time.
- Booked and available balances remain separate. Available funds may include a credit facility. Neither is summed with expected/end-of-day balances.
- Committed cursors/checkpoints, idempotent operation receipts, atomic batches, source revisions and removal tombstones. Account selection and currency cannot silently change during a connection.
- ID-less pending entries are a separate snapshot. Partial pagination cannot replace the authoritative snapshot. No amount/merchant-based pending-to-posted matching is invented.
- Imported rows remain unreviewed and excluded from finance analysis. No imported record can silently become personal income, spending or tax evidence.

## What is not yet implemented or verified

No actual bank API request, bank login, consent grant, token, certificate or client registration has been used. The staging module is not exposed by the public anonymous demo API, and is not yet connected to its UI or D1 deployment. The bank-specific HTTP client, consent lifecycle, full pagination/retry orchestration, authorised sandbox run and reviewed import into the working finance ledger remain open.

A transaction page with no `Links.Next` is not by itself proof of complete date-range coverage. The adapter exposes continuation hints but does not fetch them. A future client must validate the selected bank's exact HTTPS origin/path before sending credentials, preserve consent/filter bounds, enforce page/byte limits and reject pagination cycles. It must never construct page URLs from illustrative documentation.

Akahu is an aggregator rather than a synonym for direct open banking. Its free Personal App Demo Bank enduring connection supplies accounts/balances but no transactions. This is a separate optional path; the current direct-bank normalizer does not depend on Akahu. An accounts-only success must not be reported as zero spending or successful transaction ingestion.

Bank-specific sandbox access and terms must be checked before registration and testing. In particular, a sandbox's data-use terms may prohibit showing or copying its responses into a public judge demo. Public demo fixtures remain original fictional data unless redistribution is explicitly permitted. Private real banking requires separate authenticated storage, explicit selected-account consent, revocation/deletion controls and release review.

## Verified public schema references

- [Payments NZ Account Information v2.3.3](https://paymentsnz.atlassian.net/wiki/spaces/PaymentsNZAPIStandards/pages/1909098410)
- [Accounts](https://paymentsnz.atlassian.net/wiki/spaces/PaymentsNZAPIStandards/pages/1909098565)
- [Balances](https://paymentsnz.atlassian.net/wiki/spaces/PaymentsNZAPIStandards/pages/1909098609)
- [Transactions](https://paymentsnz.atlassian.net/wiki/spaces/PaymentsNZAPIStandards/pages/1909098886)
- [Pagination links clarification](https://paymentsnz.atlassian.net/wiki/spaces/PaymentsNZAPIStandards/pages/1926332417/Pagination+Links+clarification)
- [Akahu Demo Bank limitations](https://developers.akahu.nz/me/docs/demo-bank)

The legacy API Centre's operating status and each bank's current portal must be checked independently; do not assume an old central registration guide remains an available onboarding route.

## Reproduce offline contract tests

From `services/api`, run `uv run pytest tests/test_bank_import.py tests/test_nz_account_information.py -q`. These tests make no network requests and are not live sandbox evidence.
