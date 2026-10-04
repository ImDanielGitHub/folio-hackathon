"""Deterministic accounting and monthly goal lifecycle regressions."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from folio_api import demo_domain as domain


def one_month(*overrides):
    state = domain.initial_state()
    template = state["transactions"][0]
    state["transactions"] = [
        {
            **template,
            "id": f"row-{i}",
            "sourceId": f"source-{i}",
            "date": "2026-10-02",
            "amountMinor": -1000,
            **values,
        }
        for i, values in enumerate(overrides)
    ]
    return state


def test_pending_removed_income_and_transfers_do_not_reduce_expenses():
    state = one_month(
        {},
        {"amountMinor": 200, "type": "refund"},
        {"amountMinor": 50000, "type": "income"},
        {"amountMinor": -5000, "status": "pending"},
        {"amountMinor": -4000, "pending": True},
        {"amountMinor": -3000, "status": "removed"},
        {"amountMinor": -2000, "type": "transfer"},
        {"amountMinor": -9000, "currency": "USD"},
    )
    result = domain.compare_months(state, "personal", "2026-09", "2026-10")
    assert result["currentMinor"] == 800
    assert result["sourceIds"] == ["source-0", "source-1"]
    assert sum(row["currentMinor"] for row in result["rows"]) == 800
    assert all(row["previousMinor"] is None for row in result["rows"])
    assert all(row["differenceMinor"] is None for row in result["rows"])


def test_classifying_pending_record_cannot_turn_it_into_posted_expense():
    state = one_month({"status": "pending"})
    changed = domain.apply_action(state, "classify", {"ids": ["row-0"], "purpose": "business"})
    result = domain.compare_months(changed, "business", "2026-09", "2026-10")
    assert result["currentMinor"] is None
    assert result["sourceIds"] == []


def test_month_selection_uses_workspace_timezone_for_timestamps():
    state = one_month({"date": "2026-09-30T12:30:00Z"})
    result = domain.compare_months(state, "personal", "2026-09", "2026-10")
    assert result["currentMinor"] == 1000
    assert result["previousMinor"] is None
    state["timezone"] = "America/Los_Angeles"
    result = domain.compare_months(state, "personal", "2026-09", "2026-10")
    assert result["previousMinor"] == 1000
    assert result["currentMinor"] is None


def test_invalid_period_and_timezone_fail_closed():
    for period in ["2026-13", "2026-1", "garbage"]:
        with pytest.raises(domain.DomainError):
            domain.compare_months(domain.initial_state(), "personal", period, "2026-10")
    state = domain.initial_state()
    state["timezone"] = "Not/A_Timezone"
    with pytest.raises(domain.DomainError):
        domain.compare_months(state, "personal")


def test_edit_archive_and_undo_preserve_source_and_goal_history():
    state = domain.apply_action(domain.initial_state(), "save_goal", {"limitMinor": 30000})
    goal = deepcopy(state["goals"][0])
    changed = domain.apply_action(
        state, "edit_goal", {"id": goal["id"], "limitMinor": 25000, "scope": "business"}
    )
    assert changed["goals"][0]["limitMinor"] == 25000
    assert changed["goals"][0]["scope"] == "business"
    assert changed["goals"][0]["version"] == 2
    assert changed["history"][-1]["before"]["goals"][0] == goal
    archived = domain.apply_action(changed, "archive_goal", {"id": goal["id"]})
    assert archived["goals"][0]["status"] == "archived"
    restored = domain.apply_action(archived, "undo", {})
    assert {k: v for k, v in restored["goals"][0].items() if k != "calculationId"} == {
        k: v for k, v in changed["goals"][0].items() if k != "calculationId"
    }
    assert restored["goals"][0]["calculationId"] != changed["goals"][0]["calculationId"]
    assert archived["transactions"] == state["transactions"]
    assert state["goals"][0] == goal
    with pytest.raises(domain.DomainError):
        domain.apply_action(archived, "pause_goal", {"id": goal["id"]})


def test_goal_progress_distinguishes_no_coverage_from_zero_category_activity():
    state = one_month({"category": "Power"})
    goal = domain.apply_action(state, "save_goal", {"limitMinor": 30000})["goals"][0]
    assert goal["spentMinor"] == 0
    assert goal["remainingMinor"] == 30000
    state["transactions"] = []
    unknown = domain.goal_progress(state, goal)
    assert unknown["spentMinor"] is None
    assert unknown["remainingMinor"] is None
    assert unknown["coverageComplete"] is False


def test_goal_progress_recalculates_after_correction_and_month_reset():
    state = one_month({"date": "2026-09-30T12:30:00Z"})
    state = domain.apply_action(state, "save_goal", {"limitMinor": 30000})
    goal = state["goals"][0]
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    assert domain.goal_progress(state, goal, now=now)["spentMinor"] == 1000
    changed = domain.apply_action(state, "classify", {"ids": ["row-0"], "purpose": "business"})
    assert changed["goals"][0]["spentMinor"] == 0
    next_month = datetime(2026, 10, 31, 11, 1, tzinfo=UTC)
    result = domain.goal_progress(changed, goal, now=next_month)
    assert result["progressPeriod"] == "2026-11"
    assert result["spentMinor"] is None


def test_goal_honours_start_date_currency_and_refund_allocation():
    state = one_month(
        {"date": "2026-10-01"},
        {"amountMinor": -1234, "businessPercent": 60},
        {"amountMinor": 234, "businessPercent": 60, "type": "refund"},
        {"amountMinor": -9000, "currency": "USD"},
        {"status": "pending"},
    )
    goal = domain.apply_action(state, "save_goal", {"limitMinor": 30000, "startsOn": "2026-10-02"})[
        "goals"
    ][0]
    assert goal["spentMinor"] == 400
    assert goal["sourceIds"] == ["source-1", "source-2"]


@pytest.mark.parametrize(
    "patch",
    [
        {"limitMinor": True},
        {"scope": "unknown"},
        {"currency": "nzd"},
        {"startsOn": "2026-02-30"},
        {"period": "year"},
        {"category": ""},
    ],
)
def test_invalid_goal_edits_do_not_mutate(patch):
    state = domain.apply_action(domain.initial_state(), "save_goal", {"limitMinor": 30000})
    before = deepcopy(state)
    with pytest.raises(domain.DomainError):
        domain.apply_action(state, "edit_goal", {"id": state["goals"][0]["id"], **patch})
    assert state == before


def test_baseline_cannot_claim_complete_without_full_month_import_coverage():
    state = domain.initial_state()
    # Imported-row presence is evidence of activity, not a complete bank history.
    state["coverage"] = {}
    goal = domain.apply_action(state, "save_goal", {"limitMinor": 30000})["goals"][0]
    assert goal["baselineCoverageComplete"] is False
    assert goal["baselineMinor"] is None


def test_saved_goal_baseline_recalculates_after_source_correction():
    state = domain.apply_action(domain.initial_state(), "save_goal", {"limitMinor": 30000})
    transaction = state["transactions"][0]
    changed = domain.apply_action(
        state, "classify", {"ids": [transaction["id"]], "purpose": "business"}
    )
    assert changed["goals"][0]["baselineMinor"] == (176450 + transaction["amountMinor"]) // 3
    assert transaction["sourceId"] not in changed["goals"][0]["baselineSourceIds"]


def test_explicit_complete_empty_import_is_zero_not_missing():
    state = domain.initial_state()
    state["transactions"] = []
    state["coverage"] = {
        "NZD": {month: "complete" for month in ["2026-07", "2026-08", "2026-09", "2026-10"]}
    }
    result = domain.compare_months(state, "personal")
    assert result["currentMinor"] == 0
    assert result["previousMinor"] == 0
    goal = domain.apply_action(state, "save_goal", {"limitMinor": 30000})["goals"][0]
    assert goal["baselineMinor"] == 0
    assert goal["baselineCoverageComplete"] is True
    assert goal["spentMinor"] == 0
    assert goal["coverageComplete"] is True


def test_baseline_chart_uses_same_scoped_source_calculations():
    state = domain.initial_state()
    goal = domain.goal_settings(state, {"limitMinor": 30000})
    baseline = domain.goal_baseline(state, goal)
    assert baseline["baselineMonths"] == [
        {"month": "2026-07", "amountMinor": 58800},
        {"month": "2026-08", "amountMinor": 46410},
        {"month": "2026-09", "amountMinor": 71240},
    ]
    state["coverage"]["NZD"].pop("2026-08")
    assert domain.goal_baseline(state, goal)["baselineMonths"][1]["amountMinor"] is None
