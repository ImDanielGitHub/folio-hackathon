import importlib
from copy import deepcopy

import pytest


def calculator():
    try:
        return importlib.import_module("folio_api.offer_costs").calculate_offer_cost
    except ModuleNotFoundError:
        pytest.fail("The required deterministic offer-cost calculator is not implemented.")


def offer(**changes):
    value = {
        "id": "synthetic-plan",
        "currency": "NZD",
        "priceMinor": 4000,
        "billingUnit": "month",
        "billingCount": 1,
        "anchorDate": "2026-01-01",
        "setupMinor": 0,
        "exitMinor": 0,
        "devicePerPaymentMinor": 0,
        "mandatoryPerPaymentMinor": 0,
        "taxPerPaymentMinor": 0,
        "taxIncluded": True,
        "synthetic": True,
    }
    value.update(changes)
    return value


def test_promotion_expiry_includes_setup():
    result = calculator()(
        offer(promotionPayments=3, promotionMinor=2000, setupMinor=1000), "2026-01-01", "2027-01-01"
    )
    assert result["exactTotalMinor"] == 43000
    assert result["ongoingPriceMinor"] == 4000
    assert [row["serviceMinor"] for row in result["payments"][:4]] == [2000, 2000, 2000, 4000]


def test_unknown_exit_fee_withholds_total_but_keeps_subtotal():
    result = calculator()(
        offer(promotionPayments=3, promotionMinor=2000, setupMinor=1000, exitMinor=None),
        "2026-01-01",
        "2027-01-01",
    )
    assert result["knownSubtotalMinor"] == 43000 and result["exactTotalMinor"] is None
    assert result["missingFacts"] == ["exitMinor"]


def test_28_day_cash_and_annual_rate_are_different():
    result = calculator()(
        offer(priceMinor=2800, billingUnit="day", billingCount=28), "2026-01-01", "2027-01-01"
    )
    assert result["paymentCount"] == 14 and result["exactTotalMinor"] == 39200
    assert result["annualisedServiceMinor"] == 36500
    shorter = calculator()(
        offer(priceMinor=2800, billingUnit="day", billingCount=28), "2026-01-01", "2026-12-31"
    )
    assert shorter["paymentCount"] == 13 and shorter["exactTotalMinor"] == 36400


def test_monthly_anchor_clips_without_drifting():
    result = calculator()(offer(anchorDate="2026-01-31"), "2026-01-31", "2026-05-01")
    assert [row["date"] for row in result["payments"]] == [
        "2026-01-31",
        "2026-02-28",
        "2026-03-31",
        "2026-04-30",
    ]


def test_all_explicit_costs_are_counted():
    result = calculator()(
        offer(
            priceMinor=3000,
            setupMinor=1500,
            exitMinor=5000,
            devicePerPaymentMinor=1000,
            mandatoryPerPaymentMinor=500,
            taxIncluded=False,
            taxPerPaymentMinor=200,
        ),
        "2026-01-01",
        "2027-01-01",
    )
    assert result["exactTotalMinor"] == 62900


def test_invalid_money_dates_and_tax_double_counting_are_rejected():
    fn = calculator()
    for changed in (
        {"priceMinor": True},
        {"priceMinor": 1.2},
        {"priceMinor": -1},
        {"anchorDate": "2026-02-30"},
        {"billingCount": 0},
        {"taxPerPaymentMinor": 100},
    ):
        with pytest.raises(ValueError):
            fn(offer(**changed), "2026-01-01", "2027-01-01")


def test_calculation_does_not_mutate_source_offer():
    value = offer()
    before = deepcopy(value)
    calculator()(value, "2026-01-01", "2027-01-01")
    assert value == before
