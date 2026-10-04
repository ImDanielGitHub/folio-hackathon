from __future__ import annotations

import json

import httpx
import pytest

from folio_api.providers.nebius import (
    MODEL_ID,
    TOKEN_FACTORY_URL,
    CloudProjection,
    EvidenceFact,
    InferenceUnavailable,
    NebiusClient,
    NebiusSettings,
)


def projection(*, synthetic: bool = True, approved: bool = False) -> CloudProjection:
    return CloudProjection(
        question="Why did September spending rise?",
        facts=(
            EvidenceFact(
                calculation_id="calc_month_change",
                label="September spending change",
                amount_minor=39670,
                currency="NZD",
                source_ids=("txn_aug_fixture", "txn_sep_fixture"),
            ),
        ),
        synthetic=synthetic,
        owner_approved=approved,
    )


def completion(content: str = "The change is shown in the linked calculation.") -> dict:
    return {
        "id": "chatcmpl_synthetic",
        "model": MODEL_ID,
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
    }


def test_settings_pin_provider_and_do_not_repr_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", " fixture-token ")
    monkeypatch.setenv("NEBIUS_TIMEOUT_SECONDS", "31")
    settings = NebiusSettings.from_env()
    assert settings.api_key == "fixture-token"
    assert settings.timeout_seconds == 31
    assert "fixture-token" not in repr(settings)
    assert TOKEN_FACTORY_URL == "https://api.tokenfactory.nebius.com/v1/chat/completions"
    assert MODEL_ID == "nvidia/nemotron-3-super-120b-a12b"


@pytest.mark.parametrize("timeout", [0, -5, 121, float("nan"), float("inf")])
def test_timeout_must_be_finite_and_bounded(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        NebiusSettings(timeout_seconds=timeout)


@pytest.mark.parametrize("amount", [1.5, True, "100"])
def test_fact_requires_integer_minor_units(amount: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        EvidenceFact("calc_test", "Amount", amount, "NZD", ("txn_one",))


def test_unknown_amount_stays_null() -> None:
    fact = EvidenceFact("calc_missing", "Missing evidence", None, "NZD", ())
    assert fact.as_dict()["amountMinor"] is None


def test_projection_requires_explicit_owner_egress_approval() -> None:
    with pytest.raises(ValueError, match="approval"):
        projection(synthetic=False)
    assert projection(synthetic=False, approved=True).as_dict()["dataMode"] == "owner_approved"


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [None, "fixture-token"])
async def test_configuration_is_offline_and_never_claims_live_inference(key: str | None) -> None:
    def unexpected(_: httpx.Request) -> httpx.Response:
        pytest.fail("Configuration checks must be offline")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as transport:
        provider = NebiusClient(NebiusSettings(api_key=key), transport=transport)
        state = provider.status()
        assert state["state"] == ("configured_unverified" if key else "unconfigured")
        assert state["liveInferenceVerified"] is False
        assert state["provider"] == "nebius_token_factory"
        assert state["silentFallback"] is False
        if not key:
            with pytest.raises(InferenceUnavailable, match="not configured"):
                await provider.generate(projection())


@pytest.mark.asyncio
async def test_generation_sends_only_typed_projection_with_receipt() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == TOKEN_FACTORY_URL
        assert request.headers["Authorization"] == "Bearer fixture-token"
        body = json.loads(request.content)
        assert body["model"] == MODEL_ID
        assert body["store"] is False
        assert body["max_tokens"] == 1500
        assert body["stream"] is False
        data = json.loads(body["messages"][1]["content"])
        assert data["facts"][0]["amountMinor"] == 39670
        assert data["facts"][0]["calculationId"] == "calc_month_change"
        assert set(data) == {"question", "facts", "dataMode"}
        return httpx.Response(200, json=completion())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider = NebiusClient(NebiusSettings(api_key="fixture-token"), transport=transport)
        result = await provider.generate(projection())
        assert result.receipt.provider == "nebius_token_factory"
        assert result.receipt.model == MODEL_ID
        assert result.receipt.request_id == "chatcmpl_synthetic"
        assert result.receipt.data_mode == "synthetic_demo"
        assert result.receipt.actual_inference is True
        assert provider.status()["liveInferenceVerified"] is True
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_json_schema_is_sent_and_invalid_model_json_fails_closed() -> None:
    schema = {
        "type": "object",
        "required": ["summary"],
        "properties": {"summary": {"type": "string"}},
        "additionalProperties": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["schema"] == schema
        return httpx.Response(200, json=completion('{"unapproved":"field"}'))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider = NebiusClient(NebiusSettings(api_key="fixture-token"), transport=transport)
        with pytest.raises(InferenceUnavailable, match="response"):
            await provider.generate(projection(), output_schema=schema)
        assert provider.status()["liveInferenceVerified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing", "reasoning_only", "refusal", "truncated", "model"])
async def test_untrusted_provider_shapes_are_rejected(fault: str) -> None:
    payload = completion()
    if fault == "missing":
        payload = {}
    elif fault == "reasoning_only":
        payload["choices"][0]["message"] = {"reasoning_content": "private reasoning"}
    elif fault == "refusal":
        payload["choices"][0]["message"]["refusal"] = "refused"
    elif fault == "truncated":
        payload["choices"][0]["finish_reason"] = "length"
    else:
        payload["model"] = "substituted-model"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as transport:
        provider = NebiusClient(NebiusSettings(api_key="fixture-token"), transport=transport)
        with pytest.raises(InferenceUnavailable):
            await provider.generate(projection())
        assert provider.status()["liveInferenceVerified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [302, 401, 429, 500])
async def test_errors_redact_provider_body_and_never_retry_or_follow_redirect(code: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            code,
            text="private body fixture-token",
            headers={
                "Location": "https://malicious.example/collect",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider = NebiusClient(NebiusSettings(api_key="fixture-token"), transport=transport)
        with pytest.raises(InferenceUnavailable) as error:
            await provider.generate(projection())
    assert calls == 1
    assert "fixture-token" not in str(error.value)
    assert "private body" not in str(error.value)


@pytest.mark.asyncio
async def test_timeout_is_redacted() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret prompt in library error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        provider = NebiusClient(NebiusSettings(api_key="fixture-token"), transport=transport)
        with pytest.raises(InferenceUnavailable) as error:
            await provider.generate(projection())
    assert "secret prompt" not in str(error.value)
