"""Dated official-source snapshots; unknown fees and suitability remain unknown."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from folio_api.offer_costs import calculate_offer_cost

CATALOG = json.loads((Path(__file__).parent / "data" / "phone_offers.json").read_text())


def phone_settings(payload):
    from folio_api.demo_domain import DomainError

    allowed = {"currentMonthlyMinor", "exitMinor", "minimumDataGb", "hotspotRequired"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise DomainError(
            "Only your fictional requirements are accepted; offer prices are server-owned."
        )
    result = {key: payload.get(key) for key in allowed}
    for key in ("currentMonthlyMinor", "exitMinor"):
        value = result[key]
        if value is not None and (type(value) is not int or not 0 <= value <= 100_000_000):
            raise DomainError("Use nonnegative bounded minor units or leave the amount unknown.")
    data = result["minimumDataGb"]
    if data is not None and (type(data) is not int or not 0 <= data <= 1000):
        raise DomainError("Use a whole-number full-speed data requirement from 0 to 1000GB.")
    if result["hotspotRequired"] is not None and type(result["hotspotRequired"]) is not bool:
        raise DomainError("Choose yes, no or unknown for hotspotting.")
    return result


def phone_comparison(state, scope="personal", now=None):
    if scope != "personal":
        return {
            "type": "OfferComparison",
            "schemaVersion": 1,
            "status": "needs_input",
            "offers": [],
            "question": "These researched plans are for personal NZ use. "
            "Business requirements need separate research.",
        }
    instant = (
        datetime.now(UTC) if now is None else datetime.fromisoformat(now.replace("Z", "+00:00"))
    )
    if instant.tzinfo is None:
        raise ValueError("Use an explicit timezone for freshness checks.")
    checked = datetime.fromisoformat(CATALOG["checkedAt"].replace("Z", "+00:00"))
    stale = datetime.fromisoformat(CATALOG["staleAfter"].replace("Z", "+00:00"))
    common = {
        "type": "OfferComparison",
        "schemaVersion": 1,
        "currency": "NZD",
        "checkedAt": CATALOG["checkedAt"],
        "staleAfter": CATALOG["staleAfter"],
        "freshnessPolicy": CATALOG["freshnessPolicy"],
        "calculationId": f"phone:{state['id']}:{state['version']}:personal",
    }
    if not checked <= instant < stale:
        return {
            **common,
            "status": "needs_research",
            "offers": [
                {
                    "id": offer["id"],
                    "provider": offer["provider"],
                    "status": "stale",
                    "sources": offer["sources"],
                }
                for offer in CATALOG["offers"]
            ],
            "question": "The source check has expired. Recheck official terms before using prices.",
        }
    profile = phone_settings(state.get("phoneScenario") or {})
    start = instant.astimezone(ZoneInfo(state.get("timezone", "Pacific/Auckland"))).date()
    end = start + timedelta(days=365)
    rows = []
    for source in CATALOG["offers"]:
        offer = {**source, "anchorDate": start.isoformat(), "exitMinor": profile["exitMinor"]}
        cost = calculate_offer_cost(offer, start.isoformat(), end.isoformat())
        reasons = []
        if (
            profile["minimumDataGb"] is not None
            and source["fullSpeedDataGb"] < profile["minimumDataGb"]
        ):
            reasons.append("Full-speed data allowance is below the stated requirement.")
        if profile["hotspotRequired"] is True and source["hotspot"] is not True:
            reasons.append("Required hotspotting is not established.")
        rows.append(
            {
                **source,
                "status": "checked_snapshot",
                "cost": cost,
                "suitability": "unsuitable" if reasons else "unknown",
                "suitabilityReasons": reasons
                or ["Coverage, device compatibility and eligibility need confirmation."],
                "savingsMinor": None,
            }
        )
    current = profile["currentMonthlyMinor"]
    return {
        **common,
        "status": "needs_input",
        "scope": "personal",
        "horizonStart": start.isoformat(),
        "horizonEndExclusive": end.isoformat(),
        "requirements": profile,
        "offers": rows,
        "currentPlan": {
            "basis": "Fictional user-entered monthly baseline; not bank-verified.",
            "monthlyMinor": current,
            "annualServiceMinor": None if current is None else current * 12,
        },
        "question": "Check coverage, device fit, eligibility and all switching fees before choosing.",
        "assumptions": [
            "Both plan prices include GST; no promotion is applied.",
            "Cash paid over 365 days differs from an annualised service rate.",
            "No exact switching total or savings is claimed while fees are unknown.",
            "Keeping the existing plan is always an option. Nothing is switched.",
        ],
    }
