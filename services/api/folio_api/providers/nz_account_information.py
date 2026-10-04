"""Read-only Payments NZ Account Information v2.3.3 normalization boundary.

No HTTP, OAuth, credential storage, account consent, or payment capability lives here.
All tests use original fictional examples, not bank-owned sandbox responses.
Only allowlisted account IDs are projected. Booked rows without stable provider IDs
and sub-cent amounts need review rather than invented identities or silent rounding.
"""

from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal
from zoneinfo import ZoneInfo

from folio_api.bank_values import parse_timestamp

STANDARD = "Payments NZ Account Information v2.3.3"
SOURCE = "https://paymentsnz.atlassian.net/wiki/spaces/PaymentsNZAPIStandards/pages/1909098410"
BALANCE_TYPES = {
    "ClosingAvailable",
    "ClosingBooked",
    "Expected",
    "ForwardAvailable",
    "Information",
    "InterimAvailable",
    "InterimBooked",
    "OpeningAvailable",
    "OpeningBooked",
    "PreviouslyClosedBooked",
}


def _rows(payload, key, *, single=False):
    if not isinstance(payload, dict) or not isinstance(payload.get("Data"), dict):
        raise ValueError("Missing standard Data envelope.")
    rows = payload["Data"].get(key)
    if single and isinstance(rows, dict):
        rows = [rows]
    if (
        not isinstance(rows, list)
        or len(rows) > 5000
        or any(not isinstance(row, dict) for row in rows)
    ):
        raise ValueError("Invalid or oversized account-information page.")
    return rows


def _id(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 40 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid Max40Text provider identity.")
    return value


def _time(value):
    return parse_timestamp(value)


def _amount(row, currency):
    amount = row.get("Amount")
    if not isinstance(amount, dict) or amount.get("Currency") != currency:
        raise ValueError("Source amount currency disagrees with selected account.")
    source = amount.get("Amount")
    if not isinstance(source, str) or not re.fullmatch(r"\d{1,13}\.\d{1,5}", source):
        raise ValueError("Expected standard nonnegative decimal amount string.")
    direction = row.get("CreditDebitIndicator")
    if direction not in ("Credit", "Debit"):
        raise ValueError("CreditDebitIndicator must be explicit.")
    decimal = Decimal(source)
    minor = decimal * 100
    if minor != minor.to_integral_value():
        return None, source, direction, "unsupported_minor_unit_precision"
    if minor > 100_000_000_000:
        return None, source, direction, "amount_exceeds_supported_bound"
    return int(minor) * (-1 if direction == "Debit" else 1), source, direction, None


def normalize_accounts(payload, *, selected_account_ids):
    selected = {_id(value) for value in selected_account_ids}
    results = []
    seen = set()
    for row in _rows(payload, "Account", single=True):
        aid = _id(row.get("AccountId"))
        if aid not in selected:
            continue
        if aid in seen:
            raise ValueError("Duplicate provider account identity.")
        seen.add(aid)
        currency = row.get("Currency")
        if currency not in ("NZD", "AUD", "USD"):
            raise ValueError("Explicit supported account currency required.")
        name = row.get("Nickname") or "Selected bank account"
        if not isinstance(name, str) or len(name) > 200:
            raise ValueError("Invalid account nickname.")
        results.append(
            {
                "accountId": aid,
                "name": name,
                "currency": currency,
                "currentBalanceMinor": None,
                "availableBalanceMinor": None,
                "transactionAvailability": "unknown",
            }
        )
    return results


def apply_balances(accounts, payload):
    results = deepcopy(accounts)
    by_id = {row["accountId"]: row for row in results}
    latest = {}
    for row in _rows(payload, "Balance"):
        aid = _id(row.get("AccountId"))
        if aid not in by_id:
            raise ValueError("Balance is outside selected accounts.")
        kind = row.get("Type")
        if kind not in BALANCE_TYPES:
            raise ValueError("Unknown bank balance type.")
        when = _time(row.get("DateTime"))
        minor, _, _, problem = _amount(row, by_id[aid]["currency"])
        if problem:
            raise ValueError(problem)
        key = (aid, kind)
        if key in latest and latest[key][0] > when:
            continue
        if key in latest and latest[key][0] == when and latest[key][1] != row:
            raise ValueError("Conflicting balances at the same source timestamp.")
        latest[key] = (when, row)
        if kind not in ("InterimBooked", "InterimAvailable"):
            continue
        prefix = "current" if kind == "InterimBooked" else "available"
        target = by_id[aid]
        prior_as_of = target.get(f"{prefix}BalanceAsOf")
        if prior_as_of:
            prior_time = _time(prior_as_of)
            if when < prior_time:
                continue
            if when == prior_time and minor != target.get(f"{prefix}BalanceMinor"):
                raise ValueError("Conflicting balance at prior snapshot timestamp.")
        target[f"{prefix}BalanceMinor"] = minor
        target[f"{prefix}BalanceType"] = kind
        target[f"{prefix}BalanceAsOf"] = row["DateTime"]
        if kind == "InterimAvailable":
            credit = row.get("CreditLine")
            if credit is not None and (
                not isinstance(credit, list)
                or len(credit) > 100
                or any(
                    not isinstance(c, dict) or type(c.get("Included")) is not bool for c in credit
                )
            ):
                raise ValueError("Invalid credit-line disclosure.")
            included = None if credit is None else any(c["Included"] for c in credit)
            old_credit = target.get("availableIncludesCredit")
            if prior_as_of and when == _time(prior_as_of):
                if included is None:
                    included = old_credit
                elif old_credit is not None and included != old_credit:
                    raise ValueError("Conflicting credit inclusion at prior snapshot timestamp.")
            target["availableIncludesCredit"] = included
    return results


def normalize_transactions(payload, accounts, *, timezone):
    local_timezone = ZoneInfo(timezone)
    by_id = {row["accountId"]: row for row in accounts}
    keyed, pending, quarantined = [], [], []
    for row in _rows(payload, "Transaction"):
        aid = _id(row.get("AccountId"))
        if aid not in by_id:
            raise ValueError("Transaction is outside selected accounts.")
        status = row.get("Status")
        if status not in ("Booked", "Pending"):
            raise ValueError("Unknown transaction status.")
        booking = _time(row.get("BookingDateTime"))
        description = row.get("TransactionInformation", "")
        if not isinstance(description, str) or len(description) > 500:
            raise ValueError("Invalid transaction information.")
        tid = row.get("TransactionId")
        if tid is not None:
            _id(tid)
        minor, source, direction, problem = _amount(row, by_id[aid]["currency"])
        result = {
            "providerTransactionId": tid,
            "accountId": aid,
            "date": booking.astimezone(local_timezone).date().isoformat(),
            "sourceBookingDateTime": row["BookingDateTime"],
            "dateBasis": "booking",
            "description": description,
            "amountMinor": minor,
            "sourceAmount": source,
            "sourceSign": "debit_positive" if direction == "Debit" else "credit_positive",
            "currency": by_id[aid]["currency"],
            "status": "posted" if status == "Booked" else "pending",
        }
        if problem or (tid is None and status == "Booked"):
            quarantined.append({**result, "reason": problem or "missing_stable_transaction_id"})
        elif tid is None:
            pending.append(result)
        else:
            keyed.append(result)
    links = payload.get("Links", {})
    if not isinstance(links, dict):
        raise ValueError("Invalid pagination links.")
    next_page = links.get("Next")
    if next_page is not None and (
        not isinstance(next_page, str) or not 1 <= len(next_page) <= 2000
    ):
        raise ValueError("Invalid next-page link.")
    # This is an untrusted continuation hint, never a URL to fetch with credentials
    # until the bank-specific caller verifies exact origin/path and pagination bounds.
    return {
        "keyed": keyed,
        "pendingSnapshot": pending,
        "quarantined": quarantined,
        "nextPage": next_page,
        "hasMorePages": next_page is not None,
        "pendingSnapshotComplete": False,
        "coverage": "not_established",
        "standard": STANDARD,
    }
