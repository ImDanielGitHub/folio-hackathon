import pytest

from folio_api.demo_domain import DomainError, apply_action, calculate_capacity, initial_state


def scenario(**changes):
    return dict(
        regularIncomeMinor=500000,
        variableIncomeMinor=100000,
        committedCostsMinor=100000,
        livingCostsMinor=150000,
        savingsReserveMinor=50000,
        availableBalanceMinor=200000,
        protectedBalanceMinor=100000,
        oneOffCostMinor=150000,
        **changes,
    )


def saved(values):
    return apply_action(initial_state(), "save_capacity_scenario", values)


def test_explicit_scenario_excludes_variable_income_and_separates_cash():
    result = calculate_capacity(saved(scenario()))
    assert result["monthlyCapacityMinor"] == 200000
    assert result["cashHeadroomAfterPurchaseMinor"] == -50000
    assert result["guaranteedIncome"] is False


def test_variable_income_is_only_included_by_explicit_choice():
    result = calculate_capacity(saved(scenario(includeVariableIncome=True)))
    assert result["monthlyCapacityMinor"] == 300000
    assert any("uncertain" in value for value in result["assumptions"])


def test_missing_is_not_zero_and_zero_income_is_valid():
    values = scenario()
    values["regularIncomeMinor"] = None
    values["availableBalanceMinor"] = None
    result = calculate_capacity(saved(values))
    assert result["status"] == "needs_input" and result["monthlyCapacityMinor"] is None
    assert result["cashHeadroomAfterPurchaseMinor"] is None
    values["regularIncomeMinor"] = 0
    assert calculate_capacity(saved(values))["monthlyCapacityMinor"] == -300000


def test_scope_currency_and_integer_boundaries():
    state = saved(scenario())
    assert calculate_capacity(state, "business")["status"] == "needs_input"
    for field, value in [
        ("currency", "USD"),
        ("regularIncomeMinor", True),
        ("regularIncomeMinor", 1.2),
        ("regularIncomeMinor", -1),
    ]:
        values = scenario()
        values[field] = value
        with pytest.raises(DomainError):
            saved(values)


def test_capacity_is_reversible():
    state = saved(scenario())
    undone = apply_action(state, "undo", {})
    assert calculate_capacity(undone)["status"] == "needs_input"


def test_month_uses_workspace_timezone():
    state = saved(scenario())
    state["asOf"] = "2026-09-30T12:30:00Z"
    assert calculate_capacity(state)["period"] == "2026-10"
    state["timezone"] = "America/Los_Angeles"
    assert calculate_capacity(state)["period"] == "2026-09"


async def test_model_tool_uses_the_saved_scope_bound_scenario():
    from folio_api.finance_tools import make_tool_executor

    state = saved(scenario())
    result = await make_tool_executor(state, "personal")("calculate_capacity", {}, "test-op")
    assert result["monthlyCapacityMinor"] == 200000
    other = await make_tool_executor(state, "business")("calculate_capacity", {}, "test-op")
    assert other["status"] == "needs_input"


def test_capacity_api_persists_assumptions_and_reloads(tmp_path):
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from folio_api.app import create_app

    client = TestClient(create_app(f"sqlite:///{tmp_path / 'capacity.db'}", testing=True))
    client.headers.update({"Origin": "http://testserver"})
    client.post("/v1/demo/session", json={})
    response = client.post(
        "/v1/demo/actions",
        json={
            "operationId": str(uuid4()),
            "expectedVersion": 1,
            "type": "save_capacity_scenario",
            "payload": scenario(),
        },
    )
    assert response.status_code == 200
    assert client.get("/v1/demo/capacity").json()["monthlyCapacityMinor"] == 200000
    assert client.get("/v1/demo/capacity?scope=business").json()["status"] == "needs_input"
