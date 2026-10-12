"""Live LLM provider using the Anthropic Messages API with tool calling.

The API key is read from the ``ANTHROPIC_API_KEY`` environment variable (a local ``.env`` file
is also loaded if present). It is never logged, never stored in results and never committed.
The model name comes from the ``ANTHROPIC_MODEL`` environment variable or the constructor and
falls back to ``DEFAULT_MODEL``.
"""

import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from risksignal.agent.base import LLMMessage, LLMProvider, LLMProviderError, LLMResponse, ToolCall, ToolSpec

DEFAULT_MODEL = "claude-sonnet-5"
_STOP_REASONS = {"end_turn": "end_turn", "tool_use": "tool_use", "max_tokens": "max_tokens"}


def to_anthropic_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    """Convert provider-neutral messages to the Anthropic Messages API format."""
    converted: list[dict[str, Any]] = []
    for message in messages:
        blocks: list[dict[str, Any]] = []
        if message.text:
            blocks.append({"type": "text", "text": message.text})
        for call in message.tool_calls:
            blocks.append({"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments})
        for result in message.tool_results:
            blocks.append({"type": "tool_result", "tool_use_id": result.tool_call_id,
                           "content": result.content, "is_error": result.is_error})
        if blocks:
            converted.append({"role": message.role, "content": blocks})
    return converted


def to_anthropic_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]


def parse_response(response: Any) -> LLMResponse:
    """Read text and tool requests out of an Anthropic response object."""
    text_parts: list[str] = []
    calls: list[ToolCall] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
    stop = _STOP_REASONS.get(response.stop_reason, "other")
    return LLMResponse(text="".join(text_parts), tool_calls=calls, stop_reason=stop)


class AnthropicProvider(LLMProvider):
    """Calls Anthropic's Messages API. Pass ``client`` to inject a stand-in (used in tests)."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
        temperature: float | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
        self.temperature = temperature
        self.name = f"anthropic:{self.model}"
        if client is not None:
            self._client = client
            return
        load_dotenv()
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMProviderError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key, "
                "or set the environment variable."
            )
        self._client = anthropic.Anthropic(api_key=key, timeout=timeout)

    def complete(
        self, system: str, messages: list[LLMMessage], tools: list[ToolSpec], max_tokens: int
    ) -> LLMResponse:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": to_anthropic_messages(messages),
            "tools": to_anthropic_tools(tools),
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature
        try:
            response = self._client.messages.create(**request)
        except anthropic.AnthropicError as error:
            status = getattr(error, "status_code", None)
            detail = f", HTTP {status}" if status else ""
            raise LLMProviderError(f"Anthropic API request failed ({type(error).__name__}{detail}).") from error
        return parse_response(response)
