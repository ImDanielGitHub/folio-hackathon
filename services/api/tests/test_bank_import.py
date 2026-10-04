import importlib

import pytest
from sqlalchemy import create_engine


def module():
    try:
        return importlib.import_module("folio_api.bank_import")
    except ModuleNotFoundError:
        pytest.fail("Sandbox import/reconciliation contract is not implemented.")


def transaction(id="posted-1", **changes):
    value = {
        "transaction_id": id,
        "account_id": "account-one",
        "amount": 12.34,
        "iso_currency_code": "USD",
        "date": "2026-09-10",
        "name": "Fictional market",
        "pending": False,
        "pending_transaction_id": None,
    }
    value.update(changes)
    return value


def batch(**changes):
    value = {
        "accounts": [{"account_id": "account-one", "name": "Synthetic checking"}],
        "added": [transaction()],
        "modified": [],
        "removed": [],
        "nextCursor": "cursor-one",
    }
    value.update(changes)
    return value


def ledger(tmp_path):
    instance = module().SandboxImportLedger(create_engine(f"sqlite:///{tmp_path / 'imports.db'}"))
    instance.migrate()
    connection = instance.create_connection("workspace-one", mode="fixture", provider="plaid")
    return instance, connection


def test_exact_source_normalization_and_currency_preservation():
    fn = module().normalize_plaid_transaction
    result = fn(transaction(), "fixture-item", {"account-one"})
    assert result["amountMinor"] == -1234 and result["currency"] == "USD"
    assert result["sourceAmount"] == "12.34" and result["analysisEligible"] is False
    refund = fn(transaction(amount=-2.01), "fixture-item", {"account-one"})
    assert refund["amountMinor"] == 201
    for raw in (
        transaction(amount=1.001),
        transaction(amount=True),
        transaction(iso_currency_code=None),
        transaction(account_id="foreign"),
    ):
        with pytest.raises(ValueError):
            fn(raw, "fixture-item", {"account-one"})


def test_import_replay_has_one_effect_and_survives_reopen(tmp_path):
    db, connection = ledger(tmp_path)
    first = db.apply("workspace-one", connection, "operation-one", None, batch())
    assert db.apply("workspace-one", connection, "operation-one", None, batch()) == first
    assert db.view("workspace-one", connection)["netPostedMinorByCurrency"] == {"USD": -1234}
    reloaded = module().SandboxImportLedger(db.engine)
    assert len(reloaded.view("workspace-one", connection)["transactions"]) == 1


def test_pending_replacement_preserves_source_without_double_counting(tmp_path):
    db, connection = ledger(tmp_path)
    db.apply(
        "workspace-one",
        connection,
        "one",
        None,
        batch(added=[transaction("pending-1", pending=True)]),
    )
    assert db.view("workspace-one", connection)["netPostedMinorByCurrency"] == {}
    posted = transaction("posted-2", pending_transaction_id="pending-1", amount=12.50)
    db.apply(
        "workspace-one",
        connection,
        "two",
        "cursor-one",
        batch(added=[posted], nextCursor="cursor-two"),
    )
    state = db.view("workspace-one", connection)
    assert state["netPostedMinorByCurrency"] == {"USD": -1250}
    assert len(state["transactions"]) == 1 and state["sourceRecordCount"] == 2


def test_modified_source_is_versioned_and_removal_retains_audit(tmp_path):
    db, connection = ledger(tmp_path)
    db.apply("workspace-one", connection, "one", None, batch())
    db.apply(
        "workspace-one",
        connection,
        "two",
        "cursor-one",
        batch(added=[], modified=[transaction(amount=13)], nextCursor="two"),
    )
    assert db.view("workspace-one", connection)["revisionCount"] == 1
    db.apply(
        "workspace-one",
        connection,
        "three",
        "two",
        batch(added=[], removed=[{"transaction_id": "posted-1"}], nextCursor="three"),
    )
    result = db.view("workspace-one", connection)
    assert result["transactions"] == [] and result["sourceRecordCount"] == 1


def test_stale_cursor_foreign_tenant_and_conflicting_replay_rejected(tmp_path):
    db, connection = ledger(tmp_path)
    db.apply("workspace-one", connection, "one", None, batch())
    for args in [
        ("workspace-two", connection, "two", "cursor-one", batch()),
        ("workspace-one", connection, "two", None, batch()),
        ("workspace-one", connection, "one", None, batch(added=[])),
    ]:
        with pytest.raises(ValueError):
            db.apply(*args)
    with pytest.raises(ValueError):
        db.view("workspace-two", connection)


def test_bad_batch_rolls_back_every_record_and_cursor(tmp_path):
    db, connection = ledger(tmp_path)
    with pytest.raises(ValueError):
        db.apply(
            "workspace-one",
            connection,
            "one",
            None,
            batch(added=[transaction(), transaction("bad", amount=1.001)]),
        )
    state = db.view("workspace-one", connection)
    assert state["transactions"] == [] and state["cursor"] is None


def test_currencies_are_never_silently_summed(tmp_path):
    db, connection = ledger(tmp_path)
    db.apply(
        "workspace-one",
        connection,
        "one",
        None,
        batch(added=[transaction(), transaction("nzd", iso_currency_code="NZD", amount=8)]),
    )
    assert db.view("workspace-one", connection)["netPostedMinorByCurrency"] == {
        "USD": -1234,
        "NZD": -800,
    }


def test_production_bank_mode_is_not_accepted(tmp_path):
    db, _ = ledger(tmp_path)
    with pytest.raises(ValueError):
        db.create_connection("workspace-one", mode="production", provider="plaid")


def normalized_account(**changes):
    result = {
        "accountId": "test-account",
        "name": "Fictional NZ checking",
        "currency": "NZD",
        "currentBalanceMinor": 100050,
        "availableBalanceMinor": None,
        "transactionAvailability": "unavailable",
    }
    result.update(changes)
    return result


def normalized_transaction(**changes):
    result = {
        "providerTransactionId": "test-transaction",
        "accountId": "test-account",
        "date": "2026-09-10",
        "description": "Fictional NZ purchase",
        "amountMinor": -1234,
        "sourceAmount": "-12.34",
        "sourceSign": "credit_positive",
        "currency": "NZD",
        "status": "posted",
    }
    result.update(changes)
    return result


def normalized_batch(**changes):
    result = {
        "accounts": [normalized_account(transactionAvailability="available")],
        "added": [normalized_transaction()],
        "modified": [],
        "removed": [],
        "nextCursor": "page-one",
    }
    result.update(changes)
    return result


def neutral_ledger(tmp_path):
    db = module().SandboxImportLedger(create_engine(f"sqlite:///{tmp_path / 'neutral.db'}"))
    db.migrate()
    connection = db.create_connection("workspace-one", mode="fixture", provider="nz-bank-fixture")
    return db, connection


def test_provider_neutral_accounts_only_does_not_claim_zero_transaction_history(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    receipt = db.apply_normalized(
        "workspace-one",
        connection,
        "one",
        None,
        normalized_batch(accounts=[normalized_account()], added=[]),
    )
    view = db.view("workspace-one", connection)
    assert receipt["provider"] == "nz-bank-fixture"
    assert view["accounts"][0]["currentBalanceMinor"] == 100050
    assert view["accounts"][0]["availableBalanceMinor"] is None
    assert view["accounts"][0]["transactionAvailability"] == "unavailable"
    assert view["netPostedMinorByCurrency"] == {}
    assert view["transactionCoverage"] == "unavailable"
    assert view["mode"] == "fixture"


def test_neutral_source_units_sign_currency_and_no_unreviewed_analysis(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    db.apply_normalized("workspace-one", connection, "one", None, normalized_batch())
    row = db.view("workspace-one", connection)["transactions"][0]
    assert row["id"].startswith("nz-bank-fixture:")
    assert row["amountMinor"] == -1234 and row["sourceAmount"] == "-12.34"
    assert row["analysisEligible"] is False and row["purpose"] == "unknown"
    assert row["status"] == "posted_unreviewed"
    assert db.view("workspace-one", connection)["transactionCoverage"] == "not_established"


@pytest.mark.parametrize(
    "changes",
    [
        {"amountMinor": -1233},
        {"amountMinor": True},
        {"amountMinor": -1234.0},
        {"sourceAmount": "-12.341"},
        {"sourceAmount": "NaN"},
        {"sourceSign": "unknown"},
        {"currency": "USD"},
        {"accountId": "unselected"},
        {"status": "cleared"},
        {"date": "09/10/2026"},
        {"providerTransactionId": None},
    ],
)
def test_neutral_malformed_or_inconsistent_source_rolls_back(tmp_path, changes):
    db, connection = neutral_ledger(tmp_path)
    with pytest.raises(ValueError):
        db.apply_normalized(
            "workspace-one",
            connection,
            "one",
            None,
            normalized_batch(added=[normalized_transaction(**changes)]),
        )
    assert db.view("workspace-one", connection)["cursor"] is None


def test_neutral_pending_snapshot_replaced_without_fake_provider_identity_or_matching(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    pending = normalized_transaction(providerTransactionId=None, status="pending")
    first = normalized_batch(
        added=[], pendingSnapshot=[pending, pending], pendingSnapshotComplete=True
    )
    db.apply_normalized("workspace-one", connection, "one", None, first)
    view = db.view("workspace-one", connection)
    assert len(view["pendingSnapshot"]) == 2
    assert all(row["providerTransactionId"] is None for row in view["pendingSnapshot"])
    assert view["netPostedMinorByCurrency"] == {} and view["sourceRecordCount"] == 0
    db.apply_normalized(
        "workspace-one",
        connection,
        "two",
        "page-one",
        normalized_batch(pendingSnapshot=[], pendingSnapshotComplete=True, nextCursor="page-two"),
    )
    view = db.view("workspace-one", connection)
    assert view["pendingSnapshot"] == [] and view["sourceRecordCount"] == 1
    assert view["netPostedMinorByCurrency"] == {"NZD": -1234}


def test_neutral_replay_revisions_tenant_and_adapter_boundaries(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    first = db.apply_normalized("workspace-one", connection, "one", None, normalized_batch())
    assert (
        db.apply_normalized("workspace-one", connection, "one", None, normalized_batch()) == first
    )
    with pytest.raises(ValueError):
        db.apply("workspace-one", connection, "two", "page-one", batch())
    with pytest.raises(ValueError):
        db.apply_normalized("other", connection, "two", "page-one", normalized_batch())
    second = normalized_batch(
        added=[],
        modified=[normalized_transaction(amountMinor=-1250, sourceAmount="-12.50")],
        nextCursor="two",
    )
    db.apply_normalized("workspace-one", connection, "two", "page-one", second)
    assert db.view("workspace-one", connection)["revisionCount"] == 1
    db.apply_normalized(
        "workspace-one",
        connection,
        "three",
        "two",
        normalized_batch(
            added=[], removed=[{"providerTransactionId": "test-transaction"}], nextCursor="three"
        ),
    )
    assert db.view("workspace-one", connection)["transactions"] == []


def test_neutral_account_currency_and_selection_cannot_silently_change(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    db.apply_normalized("workspace-one", connection, "one", None, normalized_batch())
    for accounts in (
        [normalized_account(currency="USD")],
        [normalized_account(accountId="different")],
    ):
        with pytest.raises(ValueError):
            db.apply_normalized(
                "workspace-one",
                connection,
                "two",
                "page-one",
                normalized_batch(accounts=accounts, added=[]),
            )


def test_neutral_account_projection_discards_unneeded_personal_fields(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    db.apply_normalized(
        "workspace-one",
        connection,
        "one",
        None,
        normalized_batch(
            accounts=[
                normalized_account(
                    holder="Do not retain", address="Do not retain", accountNumber="Do not retain"
                )
            ],
            added=[],
        ),
    )
    account = db.view("workspace-one", connection)["accounts"][0]
    assert not {"holder", "address", "accountNumber"} & account.keys()


def test_neutral_accepts_opaque_provider_ids_without_rewriting(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    account_id, transaction_id = "bank/account:1.2", "txn/2026:09.10"
    db.apply_normalized(
        "workspace-one",
        connection,
        "one",
        None,
        normalized_batch(
            accounts=[
                normalized_account(accountId=account_id, transactionAvailability="available")
            ],
            added=[
                normalized_transaction(accountId=account_id, providerTransactionId=transaction_id)
            ],
        ),
    )
    row = db.view("workspace-one", connection)["transactions"][0]
    assert row["accountId"] == account_id and row["providerTransactionId"] == transaction_id


def test_neutral_debit_positive_source_is_explicit_not_assumed(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    db.apply_normalized(
        "workspace-one",
        connection,
        "one",
        None,
        normalized_batch(
            added=[normalized_transaction(sourceAmount="12.34", sourceSign="debit_positive")]
        ),
    )
    assert db.view("workspace-one", connection)["netPostedMinorByCurrency"] == {"NZD": -1234}


def test_neutral_rejects_conflicting_duplicate_changes_and_unavailable_data(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    for changes in (
        {
            "added": [
                normalized_transaction(),
                normalized_transaction(amountMinor=-1250, sourceAmount="-12.50"),
            ]
        },
        {"removed": [{"providerTransactionId": "test-transaction"}]},
        {"accounts": [normalized_account()]},
    ):
        with pytest.raises(ValueError):
            db.apply_normalized(
                "workspace-one", connection, "one", None, normalized_batch(**changes)
            )
    assert db.view("workspace-one", connection)["cursor"] is None


def test_partial_pending_page_cannot_replace_authoritative_snapshot(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    with pytest.raises(ValueError):
        db.apply_normalized(
            "workspace-one", connection, "one", None, normalized_batch(added=[], pendingSnapshot=[])
        )
    assert db.view("workspace-one", connection)["cursor"] is None


def test_stale_balance_cannot_override_committed_import(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    account = normalized_account(
        transactionAvailability="available",
        currentBalanceType="InterimBooked",
        currentBalanceAsOf="2026-09-30T23:30:00Z",
    )
    db.apply_normalized(
        "workspace-one", connection, "one", None, normalized_batch(accounts=[account])
    )
    stale = {**account, "currentBalanceAsOf": "2026-09-29T23:30:00Z", "currentBalanceMinor": 500}
    with pytest.raises(ValueError):
        db.apply_normalized(
            "workspace-one",
            connection,
            "two",
            "page-one",
            normalized_batch(accounts=[stale], added=[], nextCursor="two"),
        )
    assert db.view("workspace-one", connection)["accounts"][0]["currentBalanceMinor"] == 100050


def test_balance_omission_cannot_erase_timestamped_committed_position(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    account = normalized_account(
        transactionAvailability="available",
        currentBalanceType="InterimBooked",
        currentBalanceAsOf="2026-09-30T23:30:00Z",
    )
    db.apply_normalized(
        "workspace-one", connection, "one", None, normalized_batch(accounts=[account])
    )
    db.apply_normalized(
        "workspace-one",
        connection,
        "two",
        "page-one",
        normalized_batch(
            accounts=[normalized_account(currentBalanceMinor=None)], added=[], nextCursor="two"
        ),
    )
    saved = db.view("workspace-one", connection)["accounts"][0]
    assert (
        saved["currentBalanceMinor"] == 100050
        and saved["currentBalanceAsOf"] == account["currentBalanceAsOf"]
    )


def test_stable_transaction_identity_cannot_move_accounts_or_currencies(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    selection = [
        normalized_account(transactionAvailability="available"),
        normalized_account(
            accountId="second-account", currency="USD", transactionAvailability="available"
        ),
    ]
    db.apply_normalized(
        "workspace-one", connection, "one", None, normalized_batch(accounts=selection)
    )
    with pytest.raises(ValueError):
        db.apply_normalized(
            "workspace-one",
            connection,
            "two",
            "page-one",
            normalized_batch(
                accounts=selection,
                added=[],
                modified=[normalized_transaction(accountId="second-account", currency="USD")],
                nextCursor="two",
            ),
        )
    assert db.view("workspace-one", connection)["netPostedMinorByCurrency"] == {"NZD": -1234}


def test_receipt_storage_key_is_bounded_for_maximum_public_identifiers(tmp_path):
    from sqlalchemy import select

    db, _ = neutral_ledger(tmp_path)
    workspace = "w" * 80
    connection = db.create_connection(workspace, mode="fixture", provider="test")
    db.apply_normalized(workspace, connection, "o" * 120, None, normalized_batch())
    with db.engine.connect() as con:
        key = con.execute(select(module().receipts.c.id)).scalar_one()
    assert len(key) <= 200


def test_committed_booked_transaction_cannot_regress_to_pending(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    db.apply_normalized("workspace-one", connection, "one", None, normalized_batch())
    with pytest.raises(ValueError):
        db.apply_normalized(
            "workspace-one",
            connection,
            "two",
            "page-one",
            normalized_batch(
                added=[], modified=[normalized_transaction(status="pending")], nextCursor="two"
            ),
        )
    assert db.view("workspace-one", connection)["netPostedMinorByCurrency"] == {"NZD": -1234}


def test_same_timestamp_missing_credit_disclosure_keeps_known_warning(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    account = normalized_account(
        transactionAvailability="available",
        availableBalanceMinor=150000,
        availableBalanceType="InterimAvailable",
        availableBalanceAsOf="2026-09-30T23:30:00Z",
        availableIncludesCredit=True,
    )
    db.apply_normalized(
        "workspace-one", connection, "one", None, normalized_batch(accounts=[account])
    )
    without = {**account, "availableIncludesCredit": None}
    db.apply_normalized(
        "workspace-one",
        connection,
        "two",
        "page-one",
        normalized_batch(accounts=[without], added=[], nextCursor="two"),
    )
    assert db.view("workspace-one", connection)["accounts"][0]["availableIncludesCredit"] is True


def test_same_timestamp_conflicting_credit_disclosure_rolls_back(tmp_path):
    db, connection = neutral_ledger(tmp_path)
    account = normalized_account(
        transactionAvailability="available",
        availableBalanceMinor=150000,
        availableBalanceType="InterimAvailable",
        availableBalanceAsOf="2026-09-30T23:30:00Z",
        availableIncludesCredit=True,
    )
    db.apply_normalized(
        "workspace-one", connection, "one", None, normalized_batch(accounts=[account])
    )
    with pytest.raises(ValueError):
        db.apply_normalized(
            "workspace-one",
            connection,
            "two",
            "page-one",
            normalized_batch(
                accounts=[{**account, "availableIncludesCredit": False}], added=[], nextCursor="two"
            ),
        )
