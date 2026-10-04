"""Exact, side-effect-free finance tools over an explicitly synthetic workspace.

The model may select these tools; no tool infers business purpose from a merchant.
Original transactions are immutable; changes are separate annotations.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class DomainError(ValueError):
    pass


CATEGORIES = ("Eating out", "Power", "Transport", "Groceries", "Everything else", "Not sorted yet")
BASE = {
    "2026-07": (58800, 12500, 36000, 82000, 104500, 15000),
    "2026-08": (46410, 10320, 35260, 87150, 122470, 0),
    "2026-09": (71240, 16420, 40890, 88420, 103900, 20410),
}
COUNTS = {"2026-07": 102, "2026-08": 112, "2026-09": 127}
MERCHANTS = {
    "Eating out": ["Riverside Cafe", "Garden Table", "Dinner Delivery"],
    "Power": ["Demo Energy"],
    "Transport": ["City Transit", "Fuel Stop"],
    "Groceries": ["Market Lane", "Fresh Basket"],
    "Everything else": ["Fictional Mobile", "Design Software", "Home Store"],
    "Not sorted yet": ["Unclear merchant", "Mixed purchase"],
}


def initial_state():
    rows = []
    for month, totals in BASE.items():
        count = COUNTS[month]
        each = count // 6
        spare = count % 6
        for category_index, (category, total) in enumerate(zip(CATEGORIES, totals, strict=True)):
            n = each + (category_index < spare)
            for i in range(n):
                # Zero-value records in a known complete month are explicit fixture rows.
                amount = total // n + (i < total % n)
                tid = f"demo-{month}-{category_index}-{i:02d}"
                rows.append(
                    {
                        "id": tid,
                        "date": f"{month}-{(i * 2 + category_index) % 28 + 1:02d}",
                        "merchant": MERCHANTS[category][i % len(MERCHANTS[category])],
                        "description": f"SYNTHETIC SAMPLE {category} {i + 1}",
                        "amountMinor": -amount,
                        "currency": "NZD",
                        "category": category,
                        "purpose": "personal",
                        "businessPercent": 0,
                        "status": "needs_review"
                        if category == "Not sorted yet" and amount
                        else "example_label",
                        "accountId": "demo-everyday",
                        "sourceId": f"source-{tid}",
                        "recurring": category in ("Power",),
                        "version": 1,
                    }
                )
    return {
        "id": str(uuid4()),
        "kind": "demo",
        "displayName": "Sam Rivera",
        "currency": "NZD",
        "timezone": "Pacific/Auckland",
        "asOf": "2026-10-04T00:00:00Z",
        "coverage": {
            "NZD": {
                month: {"status": "complete", "minimumTransactionCount": COUNTS[month]}
                for month in BASE
            }
        },
        "version": 1,
        "transactions": rows,
        "annotations": {},
        "goals": [],
        "memory": [],
        "activities": [],
        "history": [],
        "messages": [],
        "model": {
            "state": "unconfigured",
            "provider": "nebius",
            "model": "nvidia/nemotron-3-super-120b-a12b",
        },
    }


def split_amount(amount, pct):
    if type(amount) is not int or type(pct) is not int or not 0 <= pct <= 100:
        raise DomainError("Use an integer percentage from 0 to 100.")
    work = abs(amount) * pct // 100
    if amount < 0:
        work = -work
    return work, amount - work


def validate_scope(scope):
    if scope not in ("everything", "personal", "business"):
        raise DomainError("Unknown scope.")


def workspace_timezone(state):
    try:
        return ZoneInfo(state.get("timezone", "Pacific/Auckland"))
    except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
        raise DomainError("Use a valid IANA workspace timezone.") from exc


def local_date(value, zone):
    try:
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        instant = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )
        if not isinstance(instant, datetime) or instant.tzinfo is None:
            raise ValueError("Timestamp must include its timezone.")
        return instant.astimezone(zone).date()
    except (ValueError, TypeError) as exc:
        raise DomainError("Use an ISO calendar date or timezone-aware timestamp.") from exc


def reporting_date(state, now=None):
    return local_date(
        now if now is not None else state.get("asOf", datetime.now(UTC)), workspace_timezone(state)
    )


def validate_month(month):
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise DomainError("Use a calendar month in YYYY-MM format.")
    try:
        date.fromisoformat(month + "-01")
    except ValueError as exc:
        raise DomainError("Use a valid calendar month.") from exc


def effective_transactions(state):
    rows = []
    for transaction in state["transactions"]:
        row = {**transaction, **state["annotations"].get(transaction["id"], {})}
        # Review status is editable; bank posting status is immutable source evidence.
        row["postingStatus"] = transaction.get("postingStatus", transaction.get("status", "posted"))
        rows.append(row)
    return rows


def is_posted(row):
    return (
        not row.get("pending", False)
        and not row.get("removed", False)
        and row.get("postingStatus", row.get("status")) not in ("pending", "removed")
    )


def is_expense(row):
    # Refund/chargeback credits are signed reductions, never absolute-value spending.
    return is_posted(row) and row.get("type") not in (
        "transfer",
        "card_repayment",
        "income",
        "loan_proceeds",
    )


def scoped_amount(t, scope):
    validate_scope(scope)
    if scope == "everything":
        return t["amountMinor"]
    work, personal = split_amount(
        t["amountMinor"], t.get("businessPercent", 100 if t["purpose"] == "business" else 0)
    )
    return work if scope == "business" else personal


def period_rows(state, month, currency):
    validate_month(month)
    zone = workspace_timezone(state)
    return [
        row
        for row in effective_transactions(state)
        if row["currency"] == currency
        and is_posted(row)
        and local_date(row["date"], zone).isoformat()[:7] == month
    ]


def period_coverage_complete(state, month, currency):
    """Coverage is supplied by import evidence, never inferred from a nonempty month.

    Fixture manifests retain their minimum source count so deleting test/import rows
    cannot silently preserve a false complete-history claim. A confirmed empty import
    may explicitly declare complete coverage with no rows.
    """
    coverage = state.get("coverage", {}).get(currency, {}).get(month)
    if coverage == "complete":
        return True
    if not isinstance(coverage, dict) or coverage.get("status") != "complete":
        return False
    minimum = coverage.get("minimumTransactionCount", 0)
    return (
        type(minimum) is int
        and minimum >= 0
        and len(period_rows(state, month, currency)) >= minimum
    )


def compare_months(state, scope, previous="2026-08", current="2026-09", currency="NZD"):
    validate_scope(scope)
    by_month = {month: period_rows(state, month, currency) for month in (previous, current)}
    known = {
        month: bool(values) or period_coverage_complete(state, month, currency)
        for month, values in by_month.items()
    }
    selected = {
        month: [
            row
            for row in rows
            if is_expense(row) and (scoped_amount(row, scope) != 0 or row["amountMinor"] == 0)
        ]
        for month, rows in by_month.items()
    }
    totals = {
        month: -sum(scoped_amount(row, scope) for row in selected[month]) if known[month] else None
        for month, rows in by_month.items()
    }
    rows = []
    all_selected = [row for values in selected.values() for row in values]
    for category in sorted({row["category"] for row in all_selected}):
        amounts = {
            month: -sum(scoped_amount(row, scope) for row in values if row["category"] == category)
            if known[month]
            else None
            for month, values in selected.items()
        }
        before, after = amounts[previous], amounts[current]
        rows.append(
            {
                "category": category,
                "previousMinor": before,
                "currentMinor": after,
                "differenceMinor": None if before is None or after is None else after - before,
                "transactionIds": list(
                    dict.fromkeys(row["id"] for row in all_selected if row["category"] == category)
                ),
            }
        )
    before, after = totals[previous], totals[current]
    return {
        "type": "PeriodComparison",
        "schemaVersion": 1,
        "calculationId": (
            f"compare:{state['id']}:{state['version']}:{scope}:{currency}:{previous}:{current}"
        ),
        "currency": currency,
        "scope": scope,
        "coverageByPeriod": {
            month: period_coverage_complete(state, month, currency) for month in by_month
        },
        "previousPeriod": previous,
        "currentPeriod": current,
        "previousMinor": before,
        "currentMinor": after,
        "differenceMinor": None if before is None or after is None else after - before,
        "rows": sorted(
            rows,
            key=lambda row: row["differenceMinor"] if row["differenceMinor"] is not None else 0,
            reverse=True,
        ),
        "sourceIds": list(dict.fromkeys(row["sourceId"] for row in all_selected)),
        "timezone": state.get("timezone", "Pacific/Auckland"),
        "assumptions": [
            "Posted only; transfers, card repayments, income and loan proceeds excluded.",
            "Refunds and chargebacks reduce spending in their posted period. "
            "Currencies are never combined.",
        ],
    }


def goal_settings(state, payload, existing=None, now=None):
    goal = {
        **(
            {
                "title": "Eating out",
                "category": "Eating out",
                "currency": state["currency"],
                "scope": "personal",
                "period": "month",
                "startsOn": reporting_date(state, now).replace(day=1).isoformat(),
            }
            if existing is None
            else existing
        )
    }
    allowed = ("limitMinor", "category", "currency", "scope", "period", "startsOn")
    goal.update({key: payload[key] for key in allowed if key in payload})
    amount = goal.get("limitMinor")
    if type(amount) is not int or not 0 < amount <= 100000000:
        raise DomainError("Enter a positive amount within the supported range.")
    validate_scope(goal["scope"])
    if not isinstance(goal["currency"], str) or not re.fullmatch(r"[A-Z]{3}", goal["currency"]):
        raise DomainError("Use a three-letter uppercase currency.")
    if goal["period"] != "month":
        raise DomainError("Only monthly spending goals are supported.")
    if not isinstance(goal["category"], str) or not 1 <= len(goal["category"].strip()) <= 80:
        raise DomainError("Choose a category of 1–80 characters.")
    if not isinstance(goal["startsOn"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", goal["startsOn"]
    ):
        raise DomainError("Use a goal start date in YYYY-MM-DD format.")
    local_date(goal["startsOn"], workspace_timezone(state))
    goal["title"] = goal["category"]
    return goal


def goal_baseline(state, goal):
    start = date.fromisoformat(goal["startsOn"])
    index = start.year * 12 + start.month - 1
    periods = [
        f"{(index - offset) // 12:04d}-{(index - offset) % 12 + 1:02d}" for offset in (3, 2, 1)
    ]
    observed = {month: period_rows(state, month, goal["currency"]) for month in periods}
    rows = [
        row
        for values in observed.values()
        for row in values
        if is_expense(row)
        and row["category"] == goal.get("category", goal["title"])
        and scoped_amount(row, goal["scope"]) != 0
    ]
    complete = all(period_coverage_complete(state, month, goal["currency"]) for month in periods)
    total = -sum(scoped_amount(row, goal["scope"]) for row in rows) if complete else None
    return {
        "baselineMinor": None if total is None else total // 3,
        "baselineTotalMinor": total,
        "baselinePeriods": periods,
        "baselineMonths": [
            {
                "month": month,
                "amountMinor": -sum(
                    scoped_amount(row, goal["scope"])
                    for row in observed[month]
                    if is_expense(row) and row["category"] == goal.get("category", goal["title"])
                )
                if period_coverage_complete(state, month, goal["currency"])
                else None,
            }
            for month in periods
        ],
        "baselineCoverageComplete": complete,
        "baselineRounding": {
            "method": "floor_to_minor_unit",
            "divisor": 3,
            "remainderNumerator": None if total is None else total % 3,
        },
        "baselineSourceIds": [row["sourceId"] for row in rows],
    }


def goal_progress(state, goal, now=None):
    today = reporting_date(state, now)
    month = today.isoformat()[:7]
    start = date.fromisoformat(goal["startsOn"])
    zone = workspace_timezone(state)
    observed = [
        row
        for row in period_rows(state, month, goal["currency"])
        if start <= local_date(row["date"], zone) <= today
    ]
    rows = [
        row
        for row in observed
        if is_expense(row)
        and row["category"] == goal.get("category", goal["title"])
        and scoped_amount(row, goal["scope"]) != 0
    ]
    complete = start <= today and period_coverage_complete(state, month, goal["currency"])
    spent = (
        -sum(scoped_amount(row, goal["scope"]) for row in rows) if observed or complete else None
    )
    return {
        "spentMinor": spent,
        "remainingMinor": None if spent is None else goal["limitMinor"] - spent,
        "progressPeriod": month,
        "coverageComplete": complete,
        "progressNote": "No posted transactions imported for this goal period; progress is unknown."
        if spent is None
        else (
            "Complete imported coverage; posted transactions only."
            if complete
            else "Observed posted transactions only; full account coverage is not established."
        ),
        "sourceIds": [row["sourceId"] for row in rows],
        "calculationId": (
            f"goal-progress:{state['id']}:{state['version']}:"
            f"{goal.get('id', 'draft')}:{goal['scope']}:"
            f"{goal['currency']}:{today.isoformat()}"
        ),
        "asOf": today.isoformat(),
        "timezone": state.get("timezone", "Pacific/Auckland"),
    }


def refresh_goal_progress(state, now=None):
    value = deepcopy(state)
    value["goals"] = [
        {**goal, **goal_baseline(state, goal), **goal_progress(state, goal, now)}
        for goal in state["goals"]
    ]
    return value


def apply_action(state, action, payload, *, now=None):
    if not isinstance(payload, dict):
        raise DomainError("Action payload must be an object.")
    value = deepcopy(state)
    snapshot = {key: deepcopy(state[key]) for key in ("annotations", "goals", "memory")}
    ids = {t["id"] for t in state["transactions"]}
    if action == "undo":
        if not value["history"]:
            raise DomainError("There is no reversible action.")
        prior = value["history"].pop()
        value.update(prior["before"])
        label = f"Undid: {prior['label']}"
    elif action == "classify":
        chosen = payload.get("ids")
        purpose = payload.get("purpose")
        if (
            not isinstance(chosen, list)
            or not 1 <= len(chosen) <= 50
            or any(not isinstance(t, str) for t in chosen)
            or len(set(chosen)) != len(chosen)
            or any(t not in ids for t in chosen)
        ):
            raise DomainError("Choose 1–50 transactions in this workspace.")
        if purpose not in ("personal", "business"):
            raise DomainError("Choose personal or business.")
        for tid in chosen:
            value["annotations"][tid] = {
                **value["annotations"].get(tid, {}),
                "purpose": purpose,
                "businessPercent": 100 if purpose == "business" else 0,
                "status": "confirmed",
            }
        label = f"Confirmed {len(chosen)} transactions as {purpose}"
        if payload.get("remember") is True:
            value["memory"].append(
                {
                    "id": str(uuid4()),
                    "text": f"These {len(chosen)} selected purchases were {purpose}.",
                    "scope": chosen,
                    "status": "confirmed",
                    "source": "Your correction",
                    "createdAt": datetime.now(UTC).isoformat(),
                }
            )
    elif action == "split":
        tid = payload.get("id")
        pct = payload.get("businessPercent")
        if not isinstance(tid, str) or tid not in ids:
            raise DomainError("Transaction not found in this workspace.")
        t = next(t for t in state["transactions"] if t["id"] == tid)
        split_amount(t["amountMinor"], pct)
        value["annotations"][tid] = {
            **value["annotations"].get(tid, {}),
            "purpose": "split",
            "businessPercent": pct,
            "status": "confirmed",
        }
        label = f"Split one transaction {pct}/{100 - pct}"
    elif action == "save_goal":
        goal = goal_settings(state, payload, now=now)
        goal.update(id=str(uuid4()), status="active", version=1)
        goal.update(goal_baseline(state, goal))
        value["goals"].append(goal)
        label = "Saved a spending goal"
    elif action in ("edit_goal", "update_goal", "pause_goal", "archive_goal"):
        goal = next((g for g in value["goals"] if g["id"] == payload.get("id")), None)
        if goal is None:
            raise DomainError("Goal not found in this workspace.")
        if goal["status"] == "archived":
            raise DomainError("Archived goals cannot be changed; undo the archive first.")
        if action in ("edit_goal", "update_goal"):
            goal.update(goal_settings(state, payload, existing=goal, now=now))
            goal.update(goal_baseline(state, goal))
            label = "Updated a spending goal"
        elif action == "archive_goal":
            goal["status"] = "archived"
            label = "Archived a spending goal"
        else:
            goal["status"] = "active" if goal["status"] == "paused" else "paused"
            label = f"{goal['status'].capitalize()} goal"
        goal["version"] += 1
    elif action == "forget_memory":
        mid = payload.get("id")
        if not any(m["id"] == mid for m in value["memory"]):
            raise DomainError("Memory not found.")
        value["memory"] = [m for m in value["memory"] if m["id"] != mid]
        label = "Forgot a scoped example"
    else:
        raise DomainError("This action is not supported. No changes were made.")
    if action != "undo":
        value["history"].append({"before": snapshot, "label": label})
    value["version"] += 1
    value["activities"].insert(
        0,
        {
            "id": str(uuid4()),
            "label": label,
            "status": "completed",
            "createdAt": datetime.now(UTC).isoformat(),
            "source": "You confirmed",
            "undoable": action != "undo",
            "affectedIds": payload.get("ids", [payload["id"]] if payload.get("id") else []),
        },
    )
    return refresh_goal_progress(value, now)
