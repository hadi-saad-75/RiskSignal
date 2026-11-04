"""The RiskSignal conversational assistant.

The assistant answers free questions from an Operational Risk operator over several turns:
about one system, about the whole portfolio, or about the methods. It is the investigation
agent with a conversational prompt and a wider, still read-only, tool set: the same loop, the
same tool-only access to data and numbers, the same audit trail and the same check on numbers.

Earlier turns are passed back as plain text, so the API stays stateless: the caller (the
dashboard) keeps the conversation and sends it with each new message.
"""

from collections.abc import Sequence

from risksignal.agent.base import LLMMessage, LLMProvider
from risksignal.agent.investigator import DEFAULT_MAX_TOKENS, Investigator
from risksignal.agent.prompts import CHAT_SYSTEM_PROMPT
from risksignal.agent.schemas import ChatTurn, InvestigationResult
from risksignal.agent.tool_registry import ToolRegistry

MAX_HISTORY_TURNS = 20
ASSISTANT_MAX_STEPS = 12


def history_messages(turns: Sequence[ChatTurn], max_turns: int = MAX_HISTORY_TURNS) -> list[LLMMessage]:
    """Earlier turns as model messages that start with the user and end with the assistant.

    Keeps the most recent ``max_turns`` turns, skips empty ones and merges consecutive turns of
    the same role, so the conversation always alternates as the model API requires.
    """
    messages: list[LLMMessage] = []
    for turn in turns[-max_turns:]:
        text = turn.content.strip()
        if not text:
            continue
        if messages and messages[-1].role == turn.role:
            messages[-1] = LLMMessage(role=turn.role, text=f"{messages[-1].text}\n\n{text}")
        else:
            messages.append(LLMMessage(role=turn.role, text=text))
    while messages and messages[0].role != "user":
        messages.pop(0)
    while messages and messages[-1].role != "assistant":
        messages.pop()
    return messages


class Assistant:
    """Answers one message in the context of the conversation so far."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        *,
        max_steps: int = ASSISTANT_MAX_STEPS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._agent = Investigator(provider, registry, max_steps=max_steps, max_tokens=max_tokens,
                                   system_prompt=CHAT_SYSTEM_PROMPT)

    def reply(self, message: str, history: Sequence[ChatTurn] = ()) -> InvestigationResult:
        """Answer ``message``. Numbers already stated in the conversation count as grounded."""
        context = [turn.content for turn in history] + [message]
        return self._agent.investigate(message, history=history_messages(history), context=context)
