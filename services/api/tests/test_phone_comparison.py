import importlib
import pytest
from folio_api.demo_domain import initial_state


def compare():
    try:
        return importlib.import_module("folio_api.phone_offers").phone_comparison
    except ModuleNotFoundError:
        pytest.fail("The source-backed closed comparison surface is not implemented.")


def test_fresh_official_snapshot_exposes_exact_service_cash_not_false_savings():
    result = compare()(initial_state(), now="2026-10-04T10:00:00Z")
    assert result["type"] == "OfferComparison"
    assert [row["cost"]["knownSubtotalMinor"] for row in result["offers"]] == [56000, 54000]
    assert all(
        row["cost"]["exactTotalMinor"] is None and row["savingsMinor"] is None
        for row in result["offers"]
    )
    assert all(row["suitability"] == "unknown" for row in result["offers"])
    assert all(row["sources"] for row in result["offers"])


def test_stale_source_suppresses_current_prices():
    result = compare()(initial_state(), now="2026-10-06T00:00:00Z")
    assert result["status"] == "needs_research"
    assert all("cost" not in row and "priceMinor" not in row for row in result["offers"])


def test_insufficient_data_is_unsuitable_even_when_cheap():
    state = initial_state()
    state["phoneScenario"] = {
        "currentMonthlyMinor": 5000,
        "exitMinor": None,
        "minimumDataGb": 20,
        "hotspotRequired": True,
    }
    result = compare()(state, now="2026-10-04T10:00:00Z")
    assert all(row["suitability"] == "unsuitable" for row in result["offers"])
    assert result["currentPlan"]["annualServiceMinor"] == 60000
    assert all(row["savingsMinor"] is None for row in result["offers"])


def test_unknown_offer_id_and_client_price_override_rejected():
    from folio_api.demo_domain import apply_action, DomainError

    with pytest.raises(DomainError):
        apply_action(initial_state(), "save_phone_scenario", {"priceMinor": 1})
