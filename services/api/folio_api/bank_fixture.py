"""Closed, original fictional data. No bank API, consent, credentials or uploads."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

FIXTURE = json.loads((Path(__file__).parent / "data" / "nz_bank_fixture.json").read_text())
IMPORT_CATEGORIES = (
    "Eating out",
    "Groceries",
    "Transport",
    "Shopping",
    "Utilities",
    "Software",
    "Other",
)


def _exact_payload(payload, keys):
    from folio_api.demo_domain import DomainError

    if not isinstance(payload, dict) or set(payload) != set(keys):
        raise DomainError(
            "Only the required review fields are accepted; fixture data is server-owned."
        )


def load_bank_fixture(current, payload):
    from folio_api.demo_domain import DomainError

    _exact_payload(payload, ("fixtureId",))
    if payload["fixtureId"] != FIXTURE["fixtureId"]:
        raise DomainError("Choose the original fictional NZ fixture.")
    if current is not None:
        if current.get("fixtureId") != FIXTURE["fixtureId"]:
            raise DomainError("Another import is already staged; no fixture was replaced.")
        return deepcopy(current)
    return {**deepcopy(FIXTURE), "loadedAt": datetime.now(UTC).isoformat()}


def confirm_bank_fixture(current, payload):
    from folio_api.demo_domain import DomainError

    _exact_payload(payload, ("id", "purpose", "category", "type"))
    if (
        not isinstance(current, dict)
        or current.get("fixtureId") != FIXTURE["fixtureId"]
        or current.get("provenance") != "original_fictional_fixture"
        or current.get("apiConnected") is not False
    ):
        raise DomainError("Load the original fictional fixture before reviewing a transaction.")
    if not isinstance(payload["id"], str):
        raise DomainError("Choose a staged transaction in this workspace's fixture.")
    source = next((r for r in FIXTURE["transactions"] if r["id"] == payload["id"]), None)
    row = next((r for r in current["transactions"] if r["id"] == payload["id"]), None)
    if source is None or row is None:
        raise DomainError("Choose a staged transaction in this workspace's fixture.")
    if row["status"] == "imported":
        raise DomainError("This fixture transaction is already imported.")
    if row["status"] != "staged" or source["status"] != "staged" or not row["sourceId"]:
        raise DomainError("Only posted staged transactions with a source ID can be imported.")
    if any(row.get(key) != value for key, value in source.items()):
        raise DomainError("Fixture source evidence must remain unchanged.")
    purpose, category, kind = payload["purpose"], payload["category"], payload["type"]
    if purpose not in ("personal", "business"):
        raise DomainError("Choose personal or business before importing.")
    if category not in IMPORT_CATEGORIES:
        raise DomainError("Choose a supported import category.")
    if kind not in ("expense", "refund", "income", "transfer"):
        raise DomainError("Choose expense, refund, income or transfer.")
    amount = source["amountMinor"]
    if (
        amount == 0
        or (kind == "expense" and amount >= 0)
        or (kind in ("refund", "income") and amount <= 0)
    ):
        raise DomainError("The transaction type must match the original signed amount.")
    if kind in ("income", "transfer") and category != "Other":
        raise DomainError("Use Other for income and transfers; these do not count as spending.")
    result = deepcopy(current)
    reviewed = next(r for r in result["transactions"] if r["id"] == payload["id"])
    reviewed.update(
        status="imported",
        confirmation={"purpose": purpose, "category": category, "type": kind},
        confirmedAt=datetime.now(UTC).isoformat(),
    )
    return result


def confirmed_fixture_transactions(bank_import):
    """Only explicitly reviewed rows are part of the ledger; base fixtures stay immutable."""
    if not bank_import:
        return []
    rows = []
    for source in bank_import["transactions"]:
        if source["status"] != "imported" or not source.get("confirmation"):
            continue
        confirmation = source["confirmation"]
        row = deepcopy(source)
        row.pop("confirmation")
        row.update(
            **confirmation,
            status="confirmed",
            businessPercent=100 if confirmation["purpose"] == "business" else 0,
            provenance=bank_import["provenance"],
            fixtureId=bank_import["fixtureId"],
            recurring=False,
            version=1,
        )
        rows.append(row)
    return rows
