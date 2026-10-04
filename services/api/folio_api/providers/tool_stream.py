"""Bounded SSE decoding for Nemotron function calls and measured token usage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from jsonschema import Draft202012Validator

from folio_api.providers.nebius import (
    MODEL_ID,
    TOKEN_FACTORY_URL,
    InferenceUnavailable,
    NebiusClient,
)

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_FORBIDDEN_KEYS = frozenset(
    {
        "workspaceid",
        "tenantid",
        "sessiontoken",
        "apikey",
        "accesstoken",
        "password",
        "bankaccountnumber",
        "accountnumber",
        "rawhistory",
        "rawtransactions",
        "secret",
    }
)


def validate_minimised(value: Any) -> None:
    """Reject identifiers/credentials as fields; not a claim of anonymisation."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalised = re.sub(r"[^a-z]", "", str(key).lower())
            if normalised in _FORBIDDEN_KEYS:
                raise ValueError(
                    "Private identity/credential fields are forbidden in model context"
                )
            validate_minimised(child)
    elif isinstance(value, list | tuple):
        for child in value:
            validate_minimised(child)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    effect: str = "read"

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name) or not 1 <= len(self.description) <= 600:
            raise ValueError("Tool must have a bounded name and description")
        if self.effect not in {"read", "propose", "write"}:
            raise ValueError("Unknown tool effect")
        Draft202012Validator.check_schema(self.parameters)
        if self.parameters.get("type") != "object":
            raise ValueError("Tool arguments must be an object")
        if self.parameters.get("additionalProperties") is not False:
            raise ValueError("Tool schema must reject unknown properties")
        validate_minimised(self.parameters)

    def as_api_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
                "strict": True,
            },
        }


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]

    def as_message(self) -> dict[str, Any]:
        return {
            "id": self.call_id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, separators=(",", ":")),
            },
        }


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "totalTokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ModelTurn:
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: TokenUsage
    request_id: str


class NebiusToolClient(NebiusClient):
    async def turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 1500,
    ) -> ModelTurn:
        """Internal agent transport. Messages must originate from the scoped runner."""
        if not self.settings.api_key:
            raise InferenceUnavailable("Nebius is not configured; no live inference was made")
        if type(max_tokens) is not int or not 1 <= max_tokens <= 4096:
            raise ValueError("Output token budget must be 1–4096")
        if not 1 <= len(messages) <= 32 or len(json.dumps(messages)) > 64_000:
            raise ValueError("Agent messages exceed the context budget")
        if len(tools) > 16:
            raise ValueError("Too many tools")
        if self._transport is None:
            self._transport = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.timeout_seconds, connect=10),
                trust_env=False,
                follow_redirects=False,
            )
        body = {
            "model": MODEL_ID,
            "messages": messages,
            "tools": [tool.as_api_tool() for tool in tools],
            "tool_choice": "auto",
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "store": False,
        }
        try:
            async with self._transport.stream(
                "POST",
                TOKEN_FACTORY_URL,
                json=body,
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                follow_redirects=False,
            ) as response:
                response.raise_for_status()
                return await self._decode(response)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise InferenceUnavailable(
                "Nebius tool stream unavailable or invalid; no provider fallback was used"
            ) from None

    async def _decode(self, response: httpx.Response) -> ModelTurn:
        text_parts: list[str] = []
        fragments: dict[int, dict[str, str]] = {}
        request_id = ""
        model_seen = False
        finished: str | None = None
        usage: TokenUsage | None = None
        done = False
        total_characters = 0
        async for line in response.aiter_lines():
            total_characters += len(line)
            if total_characters > 256_000 or len(line) > 64_000:
                raise ValueError("SSE response too large")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                done = True
                break
            chunk = json.loads(data)
            if not isinstance(chunk, dict) or "error" in chunk:
                raise ValueError("Invalid SSE event")
            if "model" in chunk:
                if chunk["model"] != MODEL_ID:
                    raise ValueError("Model substitution refused")
                model_seen = True
            if "id" in chunk:
                value = chunk["id"]
                if not isinstance(value, str) or not _ID.fullmatch(value):
                    raise ValueError("Invalid request ID")
                if request_id and value != request_id:
                    raise ValueError("Request ID changed during stream")
                request_id = value
            if chunk.get("usage") is not None:
                raw_usage = chunk["usage"]
                if not isinstance(raw_usage, dict):
                    raise ValueError("Invalid token usage object")
                prompt = raw_usage.get("prompt_tokens")
                output = raw_usage.get("completion_tokens")
                if type(prompt) is not int or type(output) is not int or min(prompt, output) < 0:
                    raise ValueError("Invalid token usage")
                usage = TokenUsage(prompt, output)
            choices = chunk.get("choices", [])
            if not isinstance(choices, list) or len(choices) > 1:
                raise ValueError("Unexpected choices")
            if not choices:
                continue
            choice = choices[0]
            if not isinstance(choice, dict):
                raise ValueError("Invalid choice")
            if choice.get("index", 0) != 0:
                raise ValueError("Unexpected choice index")
            finish = choice.get("finish_reason")
            if finish is not None:
                if finished is not None or finish not in {"stop", "tool_calls"}:
                    raise ValueError("Truncated or invalid finish")
                finished = finish
            delta = choice.get("delta", {})
            if not isinstance(delta, dict):
                raise ValueError("Invalid delta")
            if delta.get("refusal"):
                raise ValueError("Provider refusal")
            content = delta.get("content")
            if content is not None:
                if not isinstance(content, str):
                    raise ValueError("Invalid visible content")
                text_parts.append(content)
            # reasoning_content is deliberately neither stored nor emitted.
            raw_calls = delta.get("tool_calls") or []
            if not isinstance(raw_calls, list):
                raise ValueError("Invalid tool deltas")
            for raw_call in raw_calls:
                if not isinstance(raw_call, dict):
                    raise ValueError("Invalid tool delta")
                index = raw_call.get("index")
                if type(index) is not int or not 0 <= index < 8:
                    raise ValueError("Tool call index outside bound")
                target = fragments.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if raw_call.get("id"):
                    if target["id"] and target["id"] != raw_call["id"]:
                        raise ValueError("Tool identity changed")
                    target["id"] = raw_call["id"]
                function = raw_call.get("function", {})
                if not isinstance(function, dict):
                    raise ValueError("Invalid function delta")
                for key in ("name", "arguments"):
                    part = function.get(key)
                    if part is not None:
                        if not isinstance(part, str):
                            raise ValueError("Tool delta must be text")
                        target[key] += part
                if len(target["arguments"]) > 8192:
                    raise ValueError("Tool arguments too large")
        if not done or not model_seen or not request_id or finished is None or usage is None:
            raise ValueError("Incomplete model stream or missing measured usage")
        calls: list[ToolCall] = []
        for index in sorted(fragments):
            fragment = fragments[index]
            if not _ID.fullmatch(fragment["id"]) or not _NAME.fullmatch(fragment["name"]):
                raise ValueError("Invalid function call")
            arguments = json.loads(fragment["arguments"])
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be an object")
            calls.append(ToolCall(fragment["id"], fragment["name"], arguments))
        text = "".join(text_parts)
        if len(text) > 32_000 or (not calls and not text.strip()):
            raise ValueError("Missing or unbounded completion")
        if (finished == "tool_calls") != bool(calls):
            raise ValueError("Finish reason does not match tool calls")
        self._last_verified_at = datetime.now(UTC).isoformat()
        return ModelTurn(text, tuple(calls), usage, request_id)
