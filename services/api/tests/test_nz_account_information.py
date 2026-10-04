"""Original fictional payloads based on the public Payments NZ v2.3.3 schema.

These are NOT responses fetched from any bank sandbox or production API.
"""

import importlib

import pytest


def adapter():
    return importlib.import_module("folio_api.providers.nz_account_information")


def account():
    return {
        "AccountId": "fictional/account:1",
        "Currency": "NZD",
        "Nickname": "Fictional checking",
        "AccountType": "Personal",
        "AccountSubType": "CurrentAccount",
        "Account": [{"Identification": "PRIVATE-OMIT", "Name": "PRIVATE-OMIT"}],
    }


def balance(kind="InterimBooked", amount="1000.00", **changes):
    row = {
        "AccountId": account()["AccountId"],
        "Type": kind,
        "Amount": {"Amount": amount, "Currency": "NZD"},
        "CreditDebitIndicator": "Credit",
        "DateTime": "2026-09-30T23:30:00Z",
    }
    row.update(changes)
    return row


def transaction(**changes):
    row = {
        "AccountId": account()["AccountId"],
        "TransactionId": "fictional/transaction:1",
        "Amount": {"Amount": "12.34000", "Currency": "NZD"},
        "CreditDebitIndicator": "Debit",
        "Status": "Booked",
        "BookingDateTime": "2026-09-30T23:30:00Z",
        "TransactionInformation": "Fictional lunch",
    }
    row.update(changes)
    return row


def accounts():
    return adapter().normalize_accounts(
        {"Data": {"Account": [account()]}}, selected_account_ids={account()["AccountId"]}
    )


def test_account_envelopes_and_explicit_selection_omit_identifying_details():
    many = accounts()
    single = adapter().normalize_accounts(
        {"Data": {"Account": account()}}, selected_account_ids={account()["AccountId"]}
    )
    assert many == single and len(many) == 1
    assert many[0]["accountId"] == account()["AccountId"]
    assert many[0]["currency"] == "NZD" and many[0]["currentBalanceMinor"] is None
    assert "PRIVATE" not in str(many)
    assert (
        adapter().normalize_accounts({"Data": {"Account": [account()]}}, selected_account_ids=set())
        == []
    )


def test_balance_types_are_not_summed_and_credit_facilities_are_disclosed():
    rows = [
        balance(),
        balance("InterimAvailable", "1500.00", CreditLine=[{"Included": True}]),
        balance("Expected", "980.00"),
    ]
    result = adapter().apply_balances(accounts(), {"Data": {"Balance": rows}})[0]
    assert result["currentBalanceMinor"] == 100000
    assert result["availableBalanceMinor"] == 150000
    assert result["availableIncludesCredit"] is True
    assert result["currentBalanceType"] == "InterimBooked"
    assert result["availableBalanceType"] == "InterimAvailable"


def test_balances_pick_latest_matching_type_and_preserve_negative_position():
    rows = [
        balance(amount="5.00", DateTime="2026-09-29T23:30:00Z"),
        balance(amount="10.00", CreditDebitIndicator="Debit"),
    ]
    result = adapter().apply_balances(accounts(), {"Data": {"Balance": rows}})[0]
    assert result["currentBalanceMinor"] == -1000 and result["availableBalanceMinor"] is None


def test_booked_amount_direction_booking_timezone_and_source_preserved():
    result = adapter().normalize_transactions(
        {"Data": {"Transaction": [transaction()]}}, accounts(), timezone="Pacific/Auckland"
    )
    row = result["keyed"][0]
    assert row["amountMinor"] == -1234 and row["sourceAmount"] == "12.34000"
    assert row["sourceSign"] == "debit_positive" and row["date"] == "2026-10-01"
    assert row["sourceBookingDateTime"] == "2026-09-30T23:30:00Z"
    assert row["status"] == "posted" and result["quarantined"] == []


def test_missing_booked_identity_is_quarantined_not_invented_or_silently_deduped():
    raw = transaction()
    raw.pop("TransactionId")
    result = adapter().normalize_transactions(
        {"Data": {"Transaction": [raw, raw]}}, accounts(), timezone="Pacific/Auckland"
    )
    assert result["keyed"] == [] and len(result["quarantined"]) == 2
    assert all(row["reason"] == "missing_stable_transaction_id" for row in result["quarantined"])


def test_unkeyed_pending_uses_ephemeral_snapshot_and_never_becomes_booked():
    raw = transaction(Status="Pending")
    raw.pop("TransactionId")
    result = adapter().normalize_transactions(
        {"Data": {"Transaction": [raw]}}, accounts(), timezone="Pacific/Auckland"
    )
    assert result["keyed"] == [] and len(result["pendingSnapshot"]) == 1
    assert result["pendingSnapshot"][0]["providerTransactionId"] is None
    assert result["pendingSnapshotComplete"] is False


def test_fractional_cent_source_is_quarantined_without_rounding():
    raw = transaction(Amount={"Amount": "12.345", "Currency": "NZD"})
    result = adapter().normalize_transactions(
        {"Data": {"Transaction": [raw]}}, accounts(), timezone="Pacific/Auckland"
    )
    assert (
        result["keyed"] == []
        and result["quarantined"][0]["reason"] == "unsupported_minor_unit_precision"
    )
    assert result["quarantined"][0]["sourceAmount"] == "12.345"


@pytest.mark.parametrize(
    "changes",
    [
        {"CreditDebitIndicator": "Unknown"},
        {"Status": "Unknown"},
        {"AccountId": "unselected"},
        {"BookingDateTime": "2026-09-30T23:30:00"},
        {"BookingDateTime": "yesterday"},
        {"Amount": {"Amount": "12.34", "Currency": "USD"}},
        {"Amount": {"Amount": 12.34, "Currency": "NZD"}},
    ],
)
def test_ambiguous_transaction_data_rejected(changes):
    with pytest.raises(ValueError):
        adapter().normalize_transactions(
            {"Data": {"Transaction": [transaction(**changes)]}},
            accounts(),
            timezone="Pacific/Auckland",
        )


def test_empty_page_never_claims_complete_history():
    result = adapter().normalize_transactions(
        {"Data": {"Transaction": []}}, accounts(), timezone="Pacific/Auckland"
    )
    assert result["keyed"] == [] and result["coverage"] == "not_established"


def test_staging_integration_is_idempotent_and_fixture_labeled(tmp_path):
    from sqlalchemy import create_engine

    from folio_api.bank_import import SandboxImportLedger

    normalized_accounts = adapter().apply_balances(accounts(), {"Data": {"Balance": [balance()]}})
    result = adapter().normalize_transactions(
        {"Data": {"Transaction": [transaction()]}}, normalized_accounts, timezone="Pacific/Auckland"
    )
    db = SandboxImportLedger(create_engine(f"sqlite:///{tmp_path / 'nz.db'}"))
    db.migrate()
    connection = db.create_connection(
        "fictional-workspace", mode="fixture", provider="payments-nz-fixture"
    )
    batch = {
        "accounts": normalized_accounts,
        "added": result["keyed"],
        "modified": [],
        "removed": [],
        "nextCursor": "fixture-page-1",
    }
    first = db.apply_normalized("fictional-workspace", connection, "one", None, batch)
    assert db.apply_normalized("fictional-workspace", connection, "one", None, batch) == first
    view = db.view("fictional-workspace", connection)
    assert view["netPostedMinorByCurrency"] == {"NZD": -1234}
    assert (
        view["mode"] == "fixture" and view["accounts"][0]["currentBalanceType"] == "InterimBooked"
    )


def test_pagination_hint_does_not_claim_completion_or_follow_untrusted_url():
    result = adapter().normalize_transactions(
        {
            "Data": {"Transaction": []},
            "Links": {"Next": "https://fictional-bank.invalid/accounts/x/transactions?cursor=next"},
        },
        accounts(),
        timezone="Pacific/Auckland",
    )
    assert result["hasMorePages"] is True and result["coverage"] == "not_established"
    assert result["pendingSnapshotComplete"] is False


def test_older_balance_page_cannot_overwrite_newer_prior_snapshot():
    current = adapter().apply_balances(
        accounts(), {"Data": {"Balance": [balance(amount="1000.00")]}}
    )
    result = adapter().apply_balances(
        current, {"Data": {"Balance": [balance(amount="9.00", DateTime="2026-09-29T23:30:00Z")]}}
    )
    assert result[0]["currentBalanceMinor"] == 100000
    assert result[0]["currentBalanceAsOf"] == "2026-09-30T23:30:00Z"


def test_conflicting_balance_at_prior_snapshot_timestamp_is_rejected():
    current = adapter().apply_balances(accounts(), {"Data": {"Balance": [balance()]}})
    with pytest.raises(ValueError):
        adapter().apply_balances(current, {"Data": {"Balance": [balance(amount="999.00")]}})


@pytest.mark.parametrize(
    "value", ["2026-10-01T00:30:00+00:60", "2026-10-01T00:30:00+24:00", "2026-10-01T003000Z"]
)
def test_malformed_timezone_or_timestamp_is_not_silently_normalized(value):
    with pytest.raises(ValueError):
        adapter().normalize_transactions(
            {"Data": {"Transaction": [transaction(BookingDateTime=value)]}},
            accounts(),
            timezone="UTC",
        )


def test_same_timestamp_credit_line_warning_cannot_be_erased_by_partial_page():
    current = adapter().apply_balances(
        accounts(),
        {
            "Data": {
                "Balance": [balance("InterimAvailable", "1500.00", CreditLine=[{"Included": True}])]
            }
        },
    )
    merged = adapter().apply_balances(
        current, {"Data": {"Balance": [balance("InterimAvailable", "1500.00")]}}
    )
    assert merged[0]["availableIncludesCredit"] is True


def test_same_timestamp_conflicting_credit_disclosure_is_rejected():
    current = adapter().apply_balances(
        accounts(),
        {
            "Data": {
                "Balance": [balance("InterimAvailable", "1500.00", CreditLine=[{"Included": True}])]
            }
        },
    )
    with pytest.raises(ValueError):
        adapter().apply_balances(
            current,
            {
                "Data": {
                    "Balance": [
                        balance("InterimAvailable", "1500.00", CreditLine=[{"Included": False}])
                    ]
                }
            },
        )


def test_sub_microsecond_precision_is_explicitly_unsupported_not_rounded():
    with pytest.raises(ValueError, match="precision is not supported"):
        adapter().normalize_transactions(
            {
                "Data": {
                    "Transaction": [transaction(BookingDateTime="2026-10-01T00:30:00.1234567Z")]
                }
            },
            accounts(),
            timezone="UTC",
        )
    result = adapter().normalize_transactions(
        {"Data": {"Transaction": [transaction(BookingDateTime="2026-10-01T00:30:00.123456000Z")]}},
        accounts(),
        timezone="UTC",
    )
    assert result["keyed"][0]["sourceBookingDateTime"] == "2026-10-01T00:30:00.123456000Z"
