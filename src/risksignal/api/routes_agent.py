"""Agent endpoints: one-shot investigations and the conversational assistant."""

from fastapi import APIRouter, Depends

from risksignal.agent.assistant import Assistant
from risksignal.agent.base import LLMProviderError
from risksignal.agent.investigator import Investigator
from risksignal.agent.schemas import ChatTurn, InvestigationResult
from risksignal.agent.tool_registry import build_chat_registry, build_default_registry
from risksignal.api.dependencies import (
    ApiError,
    ChatProviderFactory,
    ProviderFactory,
    get_chat_provider_factory,
    get_provider_factory,
    get_tool_context,
)
from risksignal.api.schemas import ERROR_RESPONSES, ChatRequest, InvestigationRequest, InvestigationResponse
from risksignal.tools.context import ToolContext

router = APIRouter(prefix="/agent", tags=["agent"], responses=ERROR_RESPONSES)


def _response(result: InvestigationResult, include_tool_outputs: bool) -> InvestigationResponse:
    if result.status == "llm_error":
        raise ApiError(503, "llm_unavailable", result.final_answer)
    activity = result.tool_activity
    if not include_tool_outputs:
        activity = [a.model_copy(update={"output": None}) for a in activity]
    return InvestigationResponse(
        question=result.question,
        status=result.status,
        final_response=result.final_answer,
        activity_log=result.activity_log(),
        tool_activity=activity,
        warnings=result.warnings,
        ungrounded_numbers=result.ungrounded_numbers,
        provider=result.provider,
        llm_calls=result.llm_calls,
        disclaimer=result.disclaimer,
    )


@router.post("/investigate", response_model=InvestigationResponse, summary="Investigate a system with the agent")
def investigate(
    request: InvestigationRequest,
    ctx: ToolContext = Depends(get_tool_context),
    provider_factory: ProviderFactory = Depends(get_provider_factory),
) -> InvestigationResponse:
    """Ask the investigation agent a question, for example "Investigate PAYMENT_ENGINE_01."

    The agent decides which deterministic tools to call. Risk numbers are computed by those tools, not by
    the language model, and numbers in the answer that match no tool output are flagged (best effort, not
    proof of correctness). It makes no risk decisions. The response contains the answer, a log of the tool
    calls and warnings.
    A live request can take a while because the language model is called several times.
    """
    try:
        provider = provider_factory(request.question)
    except LLMProviderError as error:
        raise ApiError(503, "llm_unavailable", str(error)) from error

    result = Investigator(provider, build_default_registry(ctx)).investigate(request.question)
    return _response(result, request.include_tool_outputs)


@router.post("/chat", response_model=InvestigationResponse, summary="Ask the conversational assistant")
def chat(
    request: ChatRequest,
    ctx: ToolContext = Depends(get_tool_context),
    provider_factory: ChatProviderFactory = Depends(get_chat_provider_factory),
) -> InvestigationResponse:
    """Send one message to the assistant, with the conversation so far in ``history``.

    The assistant answers free questions about one system, the whole portfolio or the methods, and adapts
    the length and shape of its answer to the question. It uses the same read-only tools as the
    investigation agent plus bank-wide ones (system list, portfolio comparison, bank overview, scenario
    list), and the same check on numbers. ``final_response`` holds the reply.
    """
    message = request.message.strip()
    if not message:
        raise ApiError(422, "invalid_argument", "The message must not be empty.")
    history = [ChatTurn(role=turn.role, content=turn.content) for turn in request.history]
    try:
        provider = provider_factory(message, [turn.content for turn in history])
    except LLMProviderError as error:
        raise ApiError(503, "llm_unavailable", str(error)) from error

    result = Assistant(provider, build_chat_registry(ctx)).reply(message, history)
    return _response(result, request.include_tool_outputs)
