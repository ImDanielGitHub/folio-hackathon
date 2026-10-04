"""Exact cash schedules. Inputs are terms, not proof that an offer is suitable."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Use a calendar date in YYYY-MM-DD format.")
    return date.fromisoformat(value)


def _money(value):
    if type(value) is not int or not 0 <= value <= 100_000_000:
        raise ValueError("Money must be nonnegative bounded integer minor units.")
    return value


def _cycle(anchor, unit, count, index):
    if unit == "day":
        return anchor + timedelta(days=count * index)
    month = anchor.year * 12 + anchor.month - 1 + count * index
    year, month = divmod(month, 12)
    month += 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def calculate_offer_cost(offer, start, end):
    start, end, anchor = _date(start), _date(end), _date(offer["anchorDate"])
    if not 0 < (end - start).days <= 730 or abs((start - anchor).days) > 730:
        raise ValueError("Use a bounded positive horizon and nearby billing anchor.")
    unit, count = offer["billingUnit"], offer["billingCount"]
    if (
        unit not in ("day", "month")
        or type(count) is not int
        or not 1 <= count <= (366 if unit == "day" else 12)
    ):
        raise ValueError("Unsupported billing interval.")
    if not isinstance(offer["currency"], str) or not re.fullmatch("[A-Z]{3}", offer["currency"]):
        raise ValueError("Use one explicit currency.")
    price = _money(offer["priceMinor"])
    promo_count = offer.get("promotionPayments", 0)
    if type(promo_count) is not int or not 0 <= promo_count <= 730:
        raise ValueError("Invalid promotion length.")
    promo = _money(offer.get("promotionMinor")) if promo_count else price
    fees = (
        "setupMinor",
        "exitMinor",
        "devicePerPaymentMinor",
        "mandatoryPerPaymentMinor",
        "taxPerPaymentMinor",
    )
    missing = [key for key in fees if offer.get(key) is None]
    values = {key: 0 if offer.get(key) is None else _money(offer[key]) for key in fees}
    if type(offer.get("taxIncluded")) is not bool:
        raise ValueError("State whether the quoted service price includes tax.")
    if offer["taxIncluded"] and values["taxPerPaymentMinor"] != 0:
        raise ValueError("Tax-inclusive service prices must not be taxed twice.")
    extras = sum(values[key] for key in fees[2:])
    payments = []
    for index in range(1500):
        charge_date = _cycle(anchor, unit, count, index)
        if charge_date >= end:
            break
        if charge_date < start:
            continue
        service = promo if index < promo_count else price
        payments.append(
            {
                "date": charge_date.isoformat(),
                "serviceMinor": service,
                "knownPaymentMinor": service + extras,
            }
        )
    else:
        raise ValueError("Billing schedule exceeds its bound.")
    subtotal = (
        sum(row["knownPaymentMinor"] for row in payments)
        + values["setupMinor"]
        + values["exitMinor"]
    )
    numerator, denominator = (price * 365, count) if unit == "day" else (price * 12, count)
    annualised = (2 * numerator + denominator) // (2 * denominator)
    return {
        "type": "OfferCost",
        "schemaVersion": 1,
        "offerId": offer["id"],
        "currency": offer["currency"],
        "horizonStart": start.isoformat(),
        "horizonEndExclusive": end.isoformat(),
        "billingUnit": unit,
        "billingCount": count,
        "paymentCount": len(payments),
        "serviceTotalMinor": sum(row["serviceMinor"] for row in payments),
        "payments": payments,
        "knownSubtotalMinor": subtotal,
        "exactTotalMinor": None if missing else subtotal,
        "ongoingPriceMinor": price,
        "annualisedServiceMinor": annualised,
        "annualisedBasis": "Ongoing service rate, rounded half-up to one minor unit; not cash paid.",
        "calculationBasis": "Cash payments due in the half-open horizon; excludes optional usage.",
        "missingFacts": missing,
        "synthetic": offer.get("synthetic", False),
    }
