"""Read-only adapter for the statistical model diagnostics."""

from risksignal.stochastic.diagnostics import evaluate_temporal_model
from risksignal.tools.context import ToolContext, ToolFailure, guarded
from risksignal.tools.workbench_schemas import ModelDiagnosticsResult


@guarded("get_model_diagnostics")
def get_model_diagnostics(ctx: ToolContext, system_id: str) -> ModelDiagnosticsResult:
    ctx.get_system(system_id)
    try:
        result = evaluate_temporal_model(
            ctx.incidents_frame(), system_id, ctx.observation_start, ctx.as_of_date, ctx.system_count(),
        )
    except ValueError as error:
        raise ToolFailure("data_unavailable", f"Cannot evaluate incident history: {error}") from error
    return ModelDiagnosticsResult(**result.model_dump())
