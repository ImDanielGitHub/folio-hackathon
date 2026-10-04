"""Sandbox-only staging ledger. Not exposed by the anonymous public demo API.

Fixtures exercise import contracts; they are never presented as live API results.
Source revisions survive changes/removal. Unreviewed rows do not silently enter
spending, income or tax-purpose calculations.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, select, update

metadata = MetaData()
connections = Table(
    "bank_import_connections",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(80), nullable=False),
    Column("mode", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("state", Text, nullable=False),
)
receipts = Table(
    "bank_import_receipts",
    metadata,
    Column("id", String(200), primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("response", Text, nullable=False),
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


def _identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid bounded provider identifier.")
    return value


def normalize_plaid_transaction(raw, item_ref, account_ids):
    _identifier(item_ref)
    transaction_id = _identifier(raw.get("transaction_id"))
    account_id = _identifier(raw.get("account_id"))
    if account_id not in account_ids:
        raise ValueError("Transaction belongs to an unselected provider account.")
    currency = raw.get("iso_currency_code")
    if currency not in ("USD", "NZD"):
        raise ValueError("Currency is missing or unsupported; no currency is assumed.")
    value = raw.get("amount")
    if type(value) is bool or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("Invalid provider amount.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Invalid provider amount.") from error
    if (
        not amount.is_finite()
        or abs(amount) > Decimal("1000000000")
        or amount * 100 != (amount * 100).to_integral_value()
    ):
        raise ValueError("Provider amount must be exact supported minor units.")
    raw_date = raw.get("date")
    if not isinstance(raw_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
        raise ValueError("Provider date must be unambiguous YYYY-MM-DD.")
    posted_date = date.fromisoformat(raw_date).isoformat()
    pending = raw.get("pending")
    if type(pending) is not bool:
        raise ValueError("Provider must explicitly mark pending status.")
    replacement = raw.get("pending_transaction_id")
    if replacement is not None:
        _identifier(replacement)
    description = raw.get("name", "")
    merchant = raw.get("merchant_name") or description
    if (
        not isinstance(description, str)
        or not isinstance(merchant, str)
        or len(description) > 500
        or len(merchant) > 200
    ):
        raise ValueError("Provider labels exceed their bound.")
    return {
        "id": f"plaid:{item_ref}:{transaction_id}",
        "providerTransactionId": transaction_id,
        "accountId": account_id,
        "sourceId": f"plaid:{item_ref}:{transaction_id}",
        "date": posted_date,
        "merchant": merchant,
        "description": description,
        "amountMinor": -int(amount * 100),
        "sourceAmount": str(amount),
        "currency": currency,
        "status": "pending" if pending else "posted_unreviewed",
        "replacesPendingId": replacement,
        "category": "Not sorted yet",
        "purpose": "unknown",
        "analysisEligible": False,
    }


def _opaque_identifier(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid bounded opaque provider identifier.")
    return value


def _minor(value):
    if type(value) is not int or abs(value) > 100_000_000_000:
        raise ValueError("Money must be bounded integer minor units.")
    return value


def normalize_account(raw):
    currency = raw.get("currency")
    if currency not in ("NZD", "USD", "AUD"):
        raise ValueError("Explicit supported account currency is required.")
    name = raw.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 200:
        raise ValueError("A bounded account label is required.")
    availability = raw.get("transactionAvailability")
    if availability not in ("available", "unavailable", "unknown"):
        raise ValueError("Transaction availability must be explicit.")
    current, available = raw.get("currentBalanceMinor"), raw.get("availableBalanceMinor")
    result = {
        "accountId": _opaque_identifier(raw.get("accountId")),
        "name": name,
        "currency": currency,
        "currentBalanceMinor": None if current is None else _minor(current),
        "availableBalanceMinor": None if available is None else _minor(available),
        "transactionAvailability": availability,
    }
    for prefix, kind in [("current", "InterimBooked"), ("available", "InterimAvailable")]:
        field = f"{prefix}BalanceType"
        if field in raw:
            if raw[field] != kind:
                raise ValueError("Unsupported balance semantics.")
            result[field] = kind
            as_of = raw.get(f"{prefix}BalanceAsOf")
            if not isinstance(as_of, str) or len(as_of) > 40:
                raise ValueError("Missing balance source timestamp.")
            from datetime import datetime

            parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Balance timestamp requires timezone.")
            result[f"{prefix}BalanceAsOf"] = as_of
    included = raw.get("availableIncludesCredit")
    if included is not None and type(included) is not bool:
        raise ValueError("Credit-line inclusion must be explicit or unknown.")
    result["availableIncludesCredit"] = included
    return result


def normalize_transaction(raw, provider, item_ref, accounts, *, ephemeral=False):
    account_id = _opaque_identifier(raw.get("accountId"))
    if account_id not in accounts:
        raise ValueError("Transaction belongs to an unselected provider account.")
    currency = raw.get("currency")
    if currency != accounts[account_id]["currency"]:
        raise ValueError("Transaction currency must match its selected account.")
    amount = _minor(raw.get("amountMinor"))
    source = raw.get("sourceAmount")
    if not isinstance(source, str) or not re.fullmatch(r"-?\d{1,13}(?:\.\d{1,5})?", source):
        raise ValueError("Exact source decimal string is required.")
    try:
        source_amount = Decimal(source)
    except InvalidOperation as error:
        raise ValueError("Invalid source decimal.") from error
    sign = raw.get("sourceSign")
    if sign not in ("credit_positive", "debit_positive"):
        raise ValueError("Source sign convention must be explicit.")
    multiplier = 1 if sign == "credit_positive" else -1
    if not source_amount.is_finite() or source_amount * 100 * multiplier != amount:
        raise ValueError("Normalized amount disagrees with exact source amount/sign.")
    raw_date = raw.get("date")
    if not isinstance(raw_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
        raise ValueError("Provider date must be unambiguous YYYY-MM-DD.")
    local_date = date.fromisoformat(raw_date).isoformat()
    description = raw.get("description")
    if not isinstance(description, str) or len(description) > 500:
        raise ValueError("A bounded source description is required.")
    status = raw.get("status")
    if status not in ("posted", "pending") or (ephemeral and status != "pending"):
        raise ValueError("Source status must be explicit posted or pending.")
    tid = raw.get("providerTransactionId")
    if ephemeral:
        if tid is not None:
            raise ValueError("Ephemeral pending snapshots cannot invent provider identities.")
        identity = None
    else:
        tid = _opaque_identifier(tid)
        identity = f"{provider}:{item_ref}:{tid}"
    result = {
        "id": identity,
        "providerTransactionId": tid,
        "accountId": account_id,
        "sourceId": identity,
        "date": local_date,
        "description": description,
        "merchant": description[:200],
        "amountMinor": amount,
        "sourceAmount": source,
        "sourceSign": sign,
        "currency": currency,
        "status": "pending" if status == "pending" else "posted_unreviewed",
        "replacesPendingId": None,
        "category": "Not sorted yet",
        "purpose": "unknown",
        "analysisEligible": False,
    }
    if "sourceBookingDateTime" in raw:
        from datetime import datetime

        value = raw["sourceBookingDateTime"]
        if not isinstance(value, str) or len(value) > 40:
            raise ValueError("Invalid source booking timestamp.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or raw.get("dateBasis") != "booking":
            raise ValueError("Source booking date/time basis is ambiguous.")
        result.update(sourceBookingDateTime=value, dateBasis="booking")
    return result


class SandboxImportLedger:
    def __init__(self, engine):
        self.engine = engine

    def migrate(self):
        metadata.create_all(self.engine)

    def create_connection(self, workspace_id, *, mode, provider):
        _identifier(provider)
        if mode not in ("fixture", "sandbox"):
            raise ValueError("This staging ledger accepts fixtures and Sandbox only.")
        identifier = str(uuid4())
        state = {
            "provider": provider,
            "cursor": None,
            "records": {},
            "receipts": [],
            "accounts": [],
            "pendingSnapshot": [],
        }
        with self.engine.begin() as con:
            con.execute(
                connections.insert().values(
                    id=identifier,
                    workspace_id=workspace_id,
                    mode=mode,
                    version=1,
                    state=json.dumps(state),
                )
            )
        return identifier

    @staticmethod
    def _row(con, workspace_id, connection_id):
        row = (
            con.execute(
                select(connections)
                .where(
                    connections.c.id == connection_id, connections.c.workspace_id == workspace_id
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ValueError("Import connection not found in this workspace.")
        return row

    def apply(self, workspace_id, connection_id, operation_id, expected_cursor, batch):
        """Compatibility adapter for explicitly Plaid-shaped fixture/sandbox changes."""
        return self._apply(
            workspace_id, connection_id, operation_id, expected_cursor, batch, normalized=False
        )

    def apply_normalized(self, workspace_id, connection_id, operation_id, expected_cursor, batch):
        """Trusted adapter boundary, never an anonymous user-supplied import endpoint.

        A provider page/checkpoint is not proof of complete date-range coverage.
        Unavailable transaction history remains distinct from an empty, complete history.
        """
        return self._apply(
            workspace_id, connection_id, operation_id, expected_cursor, batch, normalized=True
        )

    def _apply(
        self, workspace_id, connection_id, operation_id, expected_cursor, batch, *, normalized
    ):
        _identifier(operation_id)
        if not isinstance(batch, dict):
            raise ValueError("Import batch must be an object.")
        raw_request = json.dumps([normalized, expected_cursor, batch], sort_keys=True, default=str)
        if len(raw_request) > 2_000_000:
            raise ValueError("Import batch exceeds the supported bound.")
        fingerprint = hashlib.sha256(raw_request.encode()).hexdigest()
        receipt_key = f"{workspace_id}:{connection_id}:{operation_id}"
        with self.engine.begin() as con:
            row = self._row(con, workspace_id, connection_id)
            state = json.loads(row["state"])
            provider = state["provider"]
            if not normalized and provider != "plaid":
                raise ValueError("Plaid adapter does not match this provider connection.")
            prior = (
                con.execute(select(receipts).where(receipts.c.id == receipt_key))
                .mappings()
                .one_or_none()
            )
            if prior:
                if prior["request_hash"] != fingerprint:
                    raise ValueError("Import operation ID was reused for different data.")
                return json.loads(prior["response"])
            state = json.loads(row["state"])
            if state["cursor"] != expected_cursor:
                raise ValueError("Import cursor changed; restart from the committed cursor.")
            account_rows = batch.get("accounts")
            if not isinstance(account_rows, list) or not 1 <= len(account_rows) <= 100:
                raise ValueError("Select a bounded list of provider accounts.")
            if normalized:
                account_projection = [normalize_account(account) for account in account_rows]
                accounts = {account["accountId"]: account for account in account_projection}
                account_ids = set(accounts)
                old_selection = {(a["accountId"], a.get("currency")) for a in state["accounts"]}
                new_selection = {(a["accountId"], a.get("currency")) for a in account_projection}
                if old_selection and old_selection != new_selection:
                    raise ValueError(
                        "Selected accounts/currencies changed; explicit reconnection required."
                    )
            else:
                account_ids = {_identifier(account.get("account_id")) for account in account_rows}
                account_projection = [{"accountId": aid} for aid in sorted(account_ids)]
            if len(account_ids) != len(account_rows):
                raise ValueError("Duplicate provider account identities.")
            for kind in ("added", "modified", "removed"):
                if not isinstance(batch.get(kind), list) or len(batch[kind]) > 5000:
                    raise ValueError("Invalid or oversized provider sync changes.")
            next_cursor = batch.get("nextCursor")
            if not isinstance(next_cursor, str) or not 1 <= len(next_cursor) <= 2000:
                raise ValueError("A bounded provider cursor is required.")
            records = deepcopy(state["records"])
            item_ref = connection_id.replace("-", "")
            pending_snapshot = state.get("pendingSnapshot", [])
            if normalized and "pendingSnapshot" in batch:
                if batch.get("pendingSnapshotComplete") is not True:
                    raise ValueError("Partial pending pages cannot replace a complete snapshot.")
                pending = batch["pendingSnapshot"]
                if not isinstance(pending, list) or len(pending) > 5000:
                    raise ValueError("Invalid or oversized pending snapshot.")
                pending_snapshot = [
                    normalize_transaction(raw, provider, item_ref, accounts, ephemeral=True)
                    for raw in pending
                ]
            if normalized:
                changes = [*batch["added"], *batch["modified"]]
                ids = [_opaque_identifier(raw.get("providerTransactionId")) for raw in changes]
                removed_ids = [
                    _opaque_identifier(raw.get("providerTransactionId")) for raw in batch["removed"]
                ]
                if (
                    len(set(ids)) != len(ids)
                    or len(set(removed_ids)) != len(removed_ids)
                    or set(ids) & set(removed_ids)
                ):
                    raise ValueError("Conflicting or duplicate changes within one provider batch.")
                if any(
                    accounts.get(raw.get("accountId"), {}).get("transactionAvailability")
                    == "unavailable"
                    for raw in changes + batch.get("pendingSnapshot", [])
                ):
                    raise ValueError("Transactions contradict account data availability.")
            added = revised = removed = 0
            for raw in [*batch["added"], *batch["modified"]]:
                record = (
                    normalize_transaction(raw, provider, item_ref, accounts)
                    if normalized
                    else normalize_plaid_transaction(raw, item_ref, account_ids)
                )
                tid = record["providerTransactionId"]
                previous = records.get(tid)
                if previous is None:
                    records[tid] = {"current": record, "versions": [], "removed": False}
                    added += 1
                elif previous["current"] != record or previous["removed"]:
                    if previous["current"] is not None:
                        previous["versions"].append(previous["current"])
                    previous.update(current=record, removed=False)
                    revised += 1
                replacement = record["replacesPendingId"]
                if not record["status"].startswith("pending") and replacement in records:
                    old = records[replacement]
                    if old["current"] and old["current"]["status"] == "pending":
                        old["removed"] = True
                        old["removalReason"] = "posted_replacement"
            for raw in batch["removed"]:
                tid = (
                    _opaque_identifier(raw.get("providerTransactionId"))
                    if normalized
                    else _identifier(raw.get("transaction_id"))
                )
                previous = records.setdefault(
                    tid, {"current": None, "versions": [], "removed": False}
                )
                if not previous["removed"]:
                    removed += 1
                previous["removed"] = True
                previous["removalReason"] = "provider_removed"
            receipt = {
                "receiptId": str(uuid4()),
                "operationId": operation_id,
                "connectionId": connection_id,
                "mode": row["mode"],
                "provider": provider,
                "status": "imported_unreviewed",
                "added": added,
                "revised": revised,
                "removed": removed,
                "nextCursor": next_cursor,
            }
            state.update(
                records=records,
                cursor=next_cursor,
                accounts=account_projection,
                pendingSnapshot=pending_snapshot,
            )
            state["receipts"].append(receipt)
            changed = con.execute(
                update(connections)
                .where(connections.c.id == connection_id, connections.c.version == row["version"])
                .values(version=row["version"] + 1, state=json.dumps(state))
            )
            if changed.rowcount != 1:
                raise ValueError("Concurrent import changed this connection; retry safely.")
            con.execute(
                receipts.insert().values(
                    id=receipt_key, request_hash=fingerprint, response=json.dumps(receipt)
                )
            )
            return receipt

    def view(self, workspace_id, connection_id):
        with self.engine.connect() as con:
            row = self._row(con, workspace_id, connection_id)
        state = json.loads(row["state"])
        active = [
            record["current"]
            for record in state["records"].values()
            if record["current"] is not None and not record["removed"]
        ]
        totals = {}
        for record in active:
            if record["status"] != "pending":
                totals[record["currency"]] = (
                    totals.get(record["currency"], 0) + record["amountMinor"]
                )
        availability = [a.get("transactionAvailability") for a in state["accounts"]]
        coverage = (
            "unavailable"
            if availability and all(a == "unavailable" for a in availability)
            else "not_established"
        )
        return {
            "connectionId": connection_id,
            "mode": row["mode"],
            "provider": state["provider"],
            "accounts": state["accounts"],
            "pendingSnapshot": state.get("pendingSnapshot", []),
            "transactionCoverage": coverage,
            "cursor": state["cursor"],
            "transactions": active,
            "netPostedMinorByCurrency": totals,
            "sourceRecordCount": len(state["records"]),
            "revisionCount": sum(len(record["versions"]) for record in state["records"].values()),
            "receipts": state["receipts"],
            "analysisStatus": "unreviewed",
        }
