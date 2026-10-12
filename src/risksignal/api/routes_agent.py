"""Agent endpoint: send an investigation request to the RiskSignal agent."""

from fastapi import APIRouter, Depends

from risksignal.agent.base import LLMProviderError
from risksignal.agent.investigator import Investigator
from risksignal.agent.tool_registry import build_default_registry
from risksignal.api.dependencies import ApiError, ProviderFactory, get_provider_factory, get_tool_context
from risksignal.api.schemas import ERROR_RESPONSES, InvestigationRequest, InvestigationResponse
from risksignal.tools.context import ToolContext

router = APIRouter(prefix="/agent", tags=["agent"], responses=ERROR_RESPONSES)


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
    if result.status == "llm_error":
        raise ApiError(503, "llm_unavailable", result.final_answer)

    activity = result.tool_activity
    if not request.include_tool_outputs:
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
