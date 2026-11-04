"""Shared API plumbing: settings, injected dependencies and error handling.

Dependencies are plain functions so tests can replace them
(``app.dependency_overrides[get_tool_context] = ...``) without any network or database.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv
from fastapi import Depends

from risksignal.agent.base import LLMProvider, LLMProviderError
from risksignal.data.storage import DB_FILENAME, DEFAULT_DATA_DIR
from risksignal.tools.context import ToolContext
from risksignal.tools.schemas import ToolError

T = TypeVar("T")
ProviderFactory = Callable[[str], LLMProvider]
ChatProviderFactory = Callable[[str, list[str]], LLMProvider]

PROVIDERS = ("anthropic", "mock")


@dataclass(frozen=True)
class Settings:
    """Configuration from environment variables (a local ``.env`` file is also read).

    * ``RISKSIGNAL_DB_PATH``: SQLite database (default: data/synthetic/atlas_bank.db)
    * ``RISKSIGNAL_LLM_PROVIDER``: ``anthropic`` (default, needs ANTHROPIC_API_KEY) or ``mock``
      (deterministic offline provider, for demos without an API key)
    """

    db_path: Path
    llm_provider: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        db_path=Path(os.environ.get("RISKSIGNAL_DB_PATH") or DEFAULT_DATA_DIR / DB_FILENAME),
        llm_provider=(os.environ.get("RISKSIGNAL_LLM_PROVIDER") or "anthropic").strip().lower(),
    )


@lru_cache(maxsize=1)
def get_tool_context() -> ToolContext:
    return ToolContext(db_path=get_settings().db_path)


def llm_is_configured(settings: Settings) -> bool:
    if settings.llm_provider == "mock":
        return True
    return settings.llm_provider == "anthropic" and bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_provider_factory() -> ProviderFactory:
    """Returns a function that builds the LLM provider for one question.

    Raises ``LLMProviderError`` (reported as HTTP 503) if the provider is misconfigured,
    for example when ANTHROPIC_API_KEY is missing.
    """
    provider_name = get_settings().llm_provider

    def build(question: str) -> LLMProvider:
        if provider_name == "mock":
            from risksignal.agent.mock_provider import provider_for_question
            return provider_for_question(question)
        if provider_name == "anthropic":
            from risksignal.agent.anthropic_provider import AnthropicProvider
            return AnthropicProvider()
        raise LLMProviderError(
            f"Unknown RISKSIGNAL_LLM_PROVIDER '{provider_name}'. Use one of: {', '.join(PROVIDERS)}.")

    return build


def get_chat_provider_factory(settings: Settings = Depends(get_settings)) -> ChatProviderFactory:
    """Returns a function that builds the LLM provider for one assistant message.

    It receives the message and the text of the earlier turns, so the offline mock can resolve
    follow-up questions. Raises ``LLMProviderError`` (HTTP 503) if the provider is misconfigured.
    """

    def build(message: str, history: list[str]) -> LLMProvider:
        if settings.llm_provider == "mock":
            from risksignal.agent.mock_assistant import assistant_provider
            return assistant_provider(message, history)
        if settings.llm_provider == "anthropic":
            from risksignal.agent.anthropic_provider import AnthropicProvider
            return AnthropicProvider()
        raise LLMProviderError(
            f"Unknown RISKSIGNAL_LLM_PROVIDER '{settings.llm_provider}'. Use one of: {', '.join(PROVIDERS)}.")

    return build


# --------------------------------------------------------------------------- errors

_STATUS_FOR_ERROR_TYPE = {
    "unknown_system": 404,
    "unknown_scenario": 404,
    "invalid_argument": 422,
    "model_error": 422,
    "data_unavailable": 503,
    "internal_error": 500,
}


class ApiError(Exception):
    """An expected failure, rendered as a JSON error body with an HTTP status code."""

    def __init__(self, status_code: int, error_type: str, message: str, suggestions: list[str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.suggestions = suggestions or []


def unwrap_tool_result(result: T | ToolError) -> T:
    """Return a successful tool result, or raise the matching ``ApiError`` for a ``ToolError``."""
    if isinstance(result, ToolError):
        raise ApiError(_STATUS_FOR_ERROR_TYPE.get(result.error_type, 500), result.error_type,
                       result.message, result.suggestions)
    return result
