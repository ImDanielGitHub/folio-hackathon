"""Authenticated tools: identity is captured by the server, never a model argument."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from folio_api.demo_domain import (
    DomainError,
    compare_months,
    calculate_capacity,
    effective_transactions,
    goal_baseline,
    goal_progress,
    goal_settings,
    is_expense,
    local_date,
    scoped_amount,
    validate_scope,
    workspace_timezone,
)
from folio_api.phone_offers import phone_comparison
from folio_api.providers.nebius import CloudProjection, EvidenceFact
from folio_api.providers.tool_stream import ToolSpec


def schema(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def build_tools(state, scope):
    validate_scope(scope)
    return [
        ToolSpec(
            "compare_periods",
            "Compare calendar months in exact minor units. Scope is fixed by the user.",
            schema(
                {
                    "previous": {"type": "string", "pattern": r"^2026-(07|08|09)$"},
                    "current": {"type": "string", "pattern": r"^2026-(07|08|09)$"},
                },
                ("previous", "current"),
            ),
        ),
        ToolSpec(
            "search_transactions",
            "Read up to25 minimised source records; no raw bank descriptions.",
            schema(
                {
                    "category": {"type": "string", "maxLength": 80},
                    "month": {"type": "string", "pattern": r"^2026-(07|08|09)$"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                }
            ),
        ),
        ToolSpec(
            "get_transaction",
            "Inspect one authorised source record and allocation.",
            schema({"id": {"type": "string", "maxLength": 160}}, ("id",)),
        ),
        ToolSpec(
            "preview_goal",
            "Draft an eating-out spending goal. This does NOT save it.",
            schema(
                {"limitMinor": {"type": "integer", "minimum": 1, "maximum": 100000000}},
                ("limitMinor",),
            ),
            effect="propose",
        ),
        ToolSpec(
            "calculate_capacity",
            "Check whether current evidence can support an income/capacity estimate.",
            schema({}),
        ),
        ToolSpec(
            "phone_plan_comparison",
            "Read dated official NZ personal-plan terms and exact cash schedules. Unknown fees and suitability prevent savings claims.",
            schema({}),
        ),
        ToolSpec(
            "retrieve_examples",
            "Retrieve confirmed examples in this workspace. An example is not a universal rule.",
            schema({}),
        ),
    ]


def make_tool_executor(state, scope):
    validate_scope(scope)
    rows = effective_transactions(state)

    async def execute(name, args, operation_id):
        if name == "compare_periods":
            return compare_months(state, scope, args["previous"], args["current"])
        if name == "search_transactions":
            limit = args.get("limit", 20)
            if type(limit) is not int or not 1 <= limit <= 25:
                raise DomainError("Row limit is1–25.")
            matches = [
                t
                for t in rows
                if (not args.get("category") or t["category"] == args["category"])
                and (
                    not args.get("month")
                    or local_date(t["date"], workspace_timezone(state))
                    .isoformat()
                    .startswith(args["month"])
                )
                and scoped_amount(t, scope) != 0
            ]
            return {
                "status": "completed",
                "scope": scope,
                "count": len(matches),
                "truncated": len(matches) > limit,
                "transactions": [
                    {
                        "id": t["id"],
                        "date": t["date"],
                        "merchant": t["merchant"],
                        "amountMinor": scoped_amount(t, scope),
                        "currency": t["currency"],
                        "category": t["category"],
                        "purpose": t["purpose"],
                        "sourceId": t["sourceId"],
                    }
                    for t in matches[:limit]
                ],
            }
        if name == "get_transaction":
            t = next((t for t in rows if t["id"] == args["id"]), None)
            if t is None:
                raise DomainError("Transaction not found in this workspace.")
            return {
                "status": "completed",
                "transaction": {
                    "id": t["id"],
                    "date": t["date"],
                    "merchant": t["merchant"],
                    "amountMinor": scoped_amount(t, scope),
                    "currency": t["currency"],
                    "purpose": t["purpose"],
                    "sourceId": t["sourceId"],
                },
                "scope": scope,
                "calculationId": f"transaction:{t['id']}:{scope}",
            }
        if name == "preview_goal":
            amount = args["limitMinor"]
            if type(amount) is not int or not 0 < amount <= 100000000:
                raise DomainError("Invalid target amount.")
            goal = goal_settings(state, {"limitMinor": amount, "scope": scope})
            baseline = goal_baseline(state, goal)
            progress = goal_progress(state, goal)
            return {
                "type": "GoalPreview",
                "schemaVersion": 1,
                "status": "draft",
                "saved": False,
                **goal,
                **baseline,
                "sourceIds": baseline["baselineSourceIds"],
                "spentMinor": progress["spentMinor"],
                "progressNote": progress["progressNote"],
                "calculationId": (
                    f"goal-preview:{state['id']}:{state['version']}:{scope}:"
                    f"{goal['currency']}:{goal['startsOn']}:{amount}"
                ),
                "assumptions": [
                    f"Only posted {scope} allocations count; transfers and income are excluded.",
                    "Refunds reduce spending in their posted period; currencies are not combined.",
                    progress["progressNote"],
                ],
                "action": "Save goal only after the person confirms the preview.",
            }
        if name == "calculate_capacity":
            return calculate_capacity(state, scope)
        if name == "phone_plan_comparison":
            return phone_comparison(state, scope)
        if name == "retrieve_examples":
            return {
                "status": "completed",
                "examples": [
                    {"text": m["text"], "scope": m["scope"], "status": m["status"]}
                    for m in state["memory"][-12:]
                ],
            }
        raise DomainError("Unsupported tool.")

    return execute


def make_projection(state, question, scope):
    """Build bounded synthetic evidence on the server; never accept client egress flags."""
    validate_scope(scope)
    if state.get("kind") != "demo":
        raise DomainError("Only the synthetic demo may enter this provider projection.")
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise DomainError("Question must contain 1–2000 characters.")
    zone = workspace_timezone(state)
    groups = {}
    for row in effective_transactions(state):
        if not is_expense(row):
            continue
        key = (local_date(row["date"], zone).isoformat()[:7], row["currency"], row["category"])
        groups.setdefault(key, []).append(row)
    facts = []
    try:
        for index, ((month, currency, category), rows) in enumerate(sorted(groups.items())):
            facts.append(
                EvidenceFact(
                    calculation_id=f"category:{state['id']}:{state['version']}:{scope}:{index}",
                    label=f"{month} · {category} · {scope} · net posted spending",
                    amount_minor=-sum(scoped_amount(row, scope) for row in rows),
                    currency=currency,
                    source_ids=tuple(row["sourceId"] for row in rows),
                )
            )
        if not facts:
            facts.append(
                EvidenceFact(
                    calculation_id=f"empty:{state['id']}:{state['version']}:{scope}",
                    label="No posted spending evidence available; spending is unknown.",
                    amount_minor=None,
                    currency=state["currency"],
                    source_ids=(),
                )
            )
        return CloudProjection(
            question=question, facts=tuple(facts), synthetic=True, owner_approved=False
        )
    except (ValueError, TypeError) as exc:
        raise DomainError(
            "Evidence exceeds the bounded provider projection; narrow the scope."
        ) from exc


_MONEY = re.compile(
    r"(?<![\w.])(?:(?P<currency>[A-Z]{3})\s*\$?|(?P<symbol>\$))\s*(?P<amount>[−+-]?\d[\d,]*(?:\.\d+)?)"
)


def validate_financial_answer(text, results):
    """Fail closed for unsupported monetary strings; not a semantic-proof claim.

    Currency, sign, integer precision and a cited owning calculation must match.
    A bare dollar symbol is accepted only when the evidence has one currency.
    """
    evidence = set()

    def visit(value, currency=None, calculation_id=None):
        if isinstance(value, dict):
            currency = value.get("currency", currency)
            calculation_id = value.get("calculationId", calculation_id)
            for key, item in value.items():
                if key.endswith("Minor") and type(item) is int:
                    evidence.add((item, currency, calculation_id))
                elif isinstance(item, (dict, list, tuple)):
                    visit(item, currency, calculation_id)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item, currency, calculation_id)

    visit(results)
    # Remove only recognised bounded evidence IDs from money-token scanning.
    # UUID segments ending b/k/m are identifiers, not billion/thousand/million claims.
    # Unrecognised bracket contents remain visible to the fail-closed parser.
    monetary_text = text
    for _, _, calculation_id in evidence:
        if isinstance(calculation_id, str) and re.fullmatch(
            r"[A-Za-z0-9_.:-]{1,160}", calculation_id
        ):
            token = r"(?<![A-Za-z0-9_.:-])" + re.escape(calculation_id) + r"(?![A-Za-z0-9_.:-])"
            monetary_text = re.sub(token, "", monetary_text)
    # Unsupported money grammars must not evade the bounded ISO-prefix parser.
    unsupported = (
        r"[A-Za-z]+\$|[€£¥]\s*[−+-]?\d|"
        r"\d[\d,.]*\s+(?-i:[A-Z]{3})\b|"
        r"\d[\d,.]*\s*(?:million|billion|thousand|hundred|dollars?|cents?|[kmb])\b"
    )
    if re.search(unsupported, monetary_text, re.IGNORECASE):
        return False
    claims = list(_MONEY.finditer(monetary_text))
    if not claims:
        return True
    currencies = {currency for _, currency, _ in evidence if currency}
    try:
        for claim in claims:
            raw = claim.group("amount").replace("−", "-")
            if "." in raw and len(raw.rsplit(".", 1)[1]) > 2:
                return False
            # Do not normalise malformed comma placement into a different claim.
            if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", raw):
                return False
            amount = int(Decimal(raw.replace(",", "")) * 100)
            currency = claim.group("currency")
            if currency is None:
                if len(currencies) != 1:
                    return False
                currency = next(iter(currencies))
            if not any(
                amount == value
                and currency == unit
                and isinstance(cid, str)
                and re.search(
                    r"(?<![A-Za-z0-9_.:-])" + re.escape(cid) + r"(?![A-Za-z0-9_.:-])", text
                )
                for value, unit, cid in evidence
            ):
                return False
        return True
    except (InvalidOperation, ValueError):
        return False
