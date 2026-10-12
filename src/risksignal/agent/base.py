"""Provider-neutral LLM interface for the investigation agent.

The agent talks to a language model only through ``LLMProvider.complete``. Everything else
in RiskSignal is independent of any particular LLM vendor. Implementations: a live
Anthropic provider and a deterministic mock provider used by the automated tests.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMProviderError(Exception):
    """The language model could not be reached or returned an unusable response.

    Messages must never contain credentials.
    """


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolSpec(_Model):
    """A tool the model may request: a name, a description and a JSON Schema for its input."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(_Model):
    """A request from the model to run one tool."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(_Model):
    """The outcome of one tool call, sent back to the model as JSON text."""

    tool_call_id: str
    content: str
    is_error: bool = False


class LLMMessage(_Model):
    """One conversation turn.

    * user turn: ``text`` (the analyst's question) or ``tool_results`` (answers to tool calls)
    * assistant turn: optional ``text`` and zero or more ``tool_calls``
    """

    role: Literal["user", "assistant"]
    text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResultBlock] = Field(default_factory=list)


class LLMResponse(_Model):
    """What the model produced for one request. No tool calls means the answer is final."""

    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "other"] = "end_turn"


class LLMProvider(ABC):
    """Anything that can continue a tool-using conversation."""

    #: Short label recorded with each investigation, for example "mock" or "anthropic:<model>".
    name: str = "provider"

    @abstractmethod
    def complete(
        self, system: str, messages: list[LLMMessage], tools: list[ToolSpec], max_tokens: int
    ) -> LLMResponse:
        """Return the model's next turn. Raise ``LLMProviderError`` on failure."""
