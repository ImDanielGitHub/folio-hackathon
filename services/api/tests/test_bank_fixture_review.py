"""Original fixture review only changes the ledger on explicit confirmation."""

from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from folio_api.app import create_app
from folio_api.demo_domain import (
    DomainError,
    apply_action,
    compare_months,
    effective_transactions,
    initial_state,
)

FIXTURE = "nz-original-v1"
PREFIX = "bank-fixture-nz-v1-"


def load(state=None):
    return apply_action(state or initial_state(), "load_bank_fixture", {"fixtureId": FIXTURE})


def confirm(state, suffix="coffee", purpose="personal", kind="expense", category="Eating out"):
    return apply_action(
        state,
        "confirm_bank_fixture",
        {
            "id": PREFIX + suffix,
            "purpose": purpose,
            "type": kind,
            "category": category,
        },
    )


def test_stage_original_fixture_without_changing_any_ledger_totals():
    state = initial_state()
    staged = load(state)
    bank = staged["bankImport"]
    assert bank["fixtureId"] == FIXTURE
    assert bank["provenance"] == "original_fictional_fixture"
    assert bank["apiConnected"] is False
    assert bank["loadedAt"]
    assert len(bank["accounts"]) == 2
    assert all(
        a["currency"] == "NZD" and a["availableIncludesCredit"] is False for a in bank["accounts"]
    )
    assert [a["currentBalanceMinor"] for a in bank["accounts"]] == [245678, 870045]
    assert [a["availableBalanceMinor"] for a in bank["accounts"]] == [240123, 870045]
    assert [r["amountMinor"] for r in bank["transactions"]] == [
        -1875,
        -6437,
        1299,
        325000,
        -50000,
        -2990,
        -3210,
    ]
    assert [r["status"] for r in bank["transactions"]] == ["staged"] * 5 + [
        "pending",
        "quarantined",
    ]
    assert bank["transactions"][-1]["sourceId"] is None
    assert staged["transactions"] == state["transactions"]
    assert len(effective_transactions(staged)) == 341
    for scope in ("personal", "business", "everything"):
        assert (
            compare_months(staged, scope)["currentMinor"]
            == compare_months(state, scope)["currentMinor"]
        )


def test_confirm_preserves_exact_source_cents_and_changes_only_explicit_scope():
    staged = load()
    accepted = confirm(staged, purpose="business")
    assert accepted["transactions"] == staged["transactions"]
    row = next(r for r in effective_transactions(accepted) if r["id"] == PREFIX + "coffee")
    source = staged["bankImport"]["transactions"][0]
    assert row["amountMinor"] == -1875
    assert row["sourceId"] == source["sourceId"]
    assert row["accountId"] == source["accountId"]
    assert row["provenance"] == "original_fictional_fixture"
    assert row["fixtureId"] == FIXTURE
    assert row["status"] == "confirmed" and row["postingStatus"] == "posted"
    assert row["purpose"] == "business" and row["businessPercent"] == 100
    assert accepted["bankImport"]["transactions"][0]["status"] == "imported"
    assert compare_months(accepted, "business")["currentMinor"] == 1875
    assert (
        compare_months(accepted, "personal")["currentMinor"]
        == compare_months(staged, "personal")["currentMinor"]
    )
    assert (
        compare_months(accepted, "everything")["currentMinor"]
        == compare_months(staged, "everything")["currentMinor"] + 1875
    )


def test_refund_reduces_spending_income_and_transfer_are_excluded():
    staged = load()
    accepted = confirm(staged, "refund", kind="refund", category="Shopping")
    assert (
        compare_months(accepted, "personal")["currentMinor"]
        == compare_months(staged, "personal")["currentMinor"] - 1299
    )
    accepted = confirm(accepted, "income", kind="income", category="Other")
    accepted = confirm(accepted, "transfer", kind="transfer", category="Other")
    assert (
        compare_months(accepted, "personal")["currentMinor"]
        == compare_months(staged, "personal")["currentMinor"] - 1299
    )
    assert len(effective_transactions(accepted)) == 344


def test_load_is_noop_before_and_after_review_without_reset_or_history_entry():
    staged = load()
    assert load(staged) == staged
    accepted = confirm(staged)
    assert load(accepted) == accepted
    assert len(accepted["history"]) == 2
    with pytest.raises(DomainError, match="already imported"):
        confirm(accepted)


def test_confirmation_and_load_undo_restore_review_and_source_provenance():
    staged = load()
    accepted = confirm(staged)
    undone = apply_action(accepted, "undo", {})
    assert undone["bankImport"] == staged["bankImport"]
    assert len(effective_transactions(undone)) == 341
    assert undone["transactions"] == staged["transactions"]
    removed = apply_action(undone, "undo", {})
    assert removed.get("bankImport") is None
    assert len(effective_transactions(removed)) == 341
    again = confirm(load(removed))
    assert len(effective_transactions(again)) == 342


def test_imported_rows_support_classify_split_and_undo():
    accepted = confirm(load())
    changed = apply_action(
        accepted, "classify", {"ids": [PREFIX + "coffee"], "purpose": "business"}
    )
    assert compare_months(changed, "business")["currentMinor"] == 1875
    split = apply_action(changed, "split", {"id": PREFIX + "coffee", "businessPercent": 60})
    assert compare_months(split, "business")["currentMinor"] == 1125
    assert split["transactions"] == accepted["transactions"]
    assert split["bankImport"] == accepted["bankImport"]
    assert apply_action(split, "undo", {})["annotations"] == changed["annotations"]


@pytest.mark.parametrize("suffix", ["pending", "missing-id", "foreign"])
def test_pending_quarantine_and_foreign_ids_cannot_be_confirmed(suffix):
    staged = load()
    before = deepcopy(staged)
    with pytest.raises(DomainError):
        confirm(staged, suffix)
    assert staged == before


def test_stage_cannot_be_reclassified_or_split_without_confirmation():
    staged = load()
    with pytest.raises(DomainError):
        apply_action(staged, "classify", {"ids": [PREFIX + "coffee"], "purpose": "business"})
    with pytest.raises(DomainError):
        apply_action(staged, "split", {"id": PREFIX + "coffee", "businessPercent": 60})
    with pytest.raises(DomainError):
        confirm(initial_state())


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"fixtureId": "foreign"},
        {"fixtureId": FIXTURE, "transactions": []},
        {"fixtureId": FIXTURE, "apiConnected": True},
        {"fixtureId": [FIXTURE]},
        [],
        None,
    ],
)
def test_load_accepts_only_known_fixture_id(payload):
    with pytest.raises(DomainError):
        apply_action(initial_state(), "load_bank_fixture", payload)


@pytest.mark.parametrize(
    "override",
    [
        {"amountMinor": -1},
        {"currency": "USD"},
        {"sourceId": "forged"},
        {"accountId": "forged"},
        {"provenance": "bank_api"},
        {"status": "posted"},
        {"purpose": "split"},
        {"category": "Client-made category"},
        {"category": None},
        {"type": "income"},
        {"type": "refund"},
        {"type": "credit"},
        {"id": "demo-2026-09-0-00"},
    ],
)
def test_confirmation_rejects_extra_fields_invalid_values_and_sign_mismatch(override):
    payload = {
        "id": PREFIX + "coffee",
        "purpose": "personal",
        "type": "expense",
        "category": "Eating out",
        **override,
    }
    with pytest.raises(DomainError):
        apply_action(load(), "confirm_bank_fixture", payload)


@pytest.mark.parametrize("kind", ["income", "transfer"])
def test_nonspending_types_require_other_category(kind):
    with pytest.raises(DomainError):
        confirm(load(), "income", kind=kind, category="Shopping")


def test_positive_money_cannot_be_confirmed_as_expense():
    with pytest.raises(DomainError):
        confirm(load(), "refund")


def test_api_fixture_persists_replays_and_stays_in_one_tenant(tmp_path):
    app = create_app("sqlite:///" + str(tmp_path / "review.db"), testing=True)
    headers = {"Origin": "http://testserver"}
    first, second = TestClient(app), TestClient(app)
    first_state = first.post("/v1/demo/session", json={}, headers=headers).json()
    second.post("/v1/demo/session", json={}, headers=headers)
    command = {
        "operationId": str(uuid4()),
        "expectedVersion": first_state["version"],
        "type": "load_bank_fixture",
        "payload": {"fixtureId": FIXTURE},
    }
    response = first.post("/v1/demo/actions", json=command, headers=headers)
    assert response.status_code == 200, response.text
    staged = response.json()
    assert first.post("/v1/demo/actions", json=command, headers=headers).json() == staged
    assert second.get("/v1/demo/workspace").json().get("bankImport") is None
    confirm_command = {
        "operationId": str(uuid4()),
        "expectedVersion": staged["version"],
        "type": "confirm_bank_fixture",
        "payload": {
            "id": PREFIX + "coffee",
            "purpose": "business",
            "category": "Eating out",
            "type": "expense",
        },
    }
    accepted = first.post("/v1/demo/actions", json=confirm_command, headers=headers)
    assert accepted.status_code == 200, accepted.text
    assert (
        first.post("/v1/demo/actions", json=confirm_command, headers=headers).json()
        == accepted.json()
    )
    assert len(first.get("/v1/demo/workspace").json()["transactions"]) == 342
    foreign = second.post(
        "/v1/demo/actions",
        json={**confirm_command, "operationId": str(uuid4()), "expectedVersion": 1},
        headers=headers,
    )
    assert foreign.status_code == 422
    assert len(second.get("/v1/demo/workspace").json()["transactions"]) == 341


def test_public_undo_control_uses_remaining_history_not_latest_receipt():
    from folio_api.app import public_state

    original = initial_state()
    assert public_state(original)["undo"] == {"available": False, "label": None}
    staged = load(original)
    accepted = confirm(staged, "coffee")
    undone = apply_action(accepted, "undo", {})
    view = public_state(undone)
    assert view["undo"]["available"] is True
    assert view["undo"]["label"].startswith("Staged original fictional")
    assert "history" not in view
    assert public_state(apply_action(undone, "undo", {}))["undo"] == {
        "available": False,
        "label": None,
    }
