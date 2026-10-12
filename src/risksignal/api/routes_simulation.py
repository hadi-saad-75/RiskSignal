"""Simulation endpoints: baseline loss simulation and baseline-versus-stress comparison.

These call the simulation tools, which call the stochastic engine. No calculation happens here.
"""

from fastapi import APIRouter, Depends

from risksignal.api.dependencies import get_tool_context, unwrap_tool_result
from risksignal.api.schemas import (
    ERROR_RESPONSES,
    CustomScenarioRequest,
    ScenarioCompareRequest,
    SimulationRequest,
)
from risksignal.tools.context import ToolContext
from risksignal.tools.schemas import LossSimulationResult, ScenarioComparisonResult, ScenarioListResult
from risksignal.tools.simulation_tools import (
    compare_baseline_and_custom_scenario,
    compare_baseline_and_stress,
    list_scenarios,
    run_loss_simulation,
)

router = APIRouter(tags=["simulation"], responses=ERROR_RESPONSES)


@router.post("/simulations", response_model=LossSimulationResult, summary="Run baseline loss simulation")
def simulate(request: SimulationRequest, ctx: ToolContext = Depends(get_tool_context)) -> LossSimulationResult:
    """Monte Carlo simulation of annual aggregate loss (Poisson frequency, Lognormal severity).

    Modelled output under illustrative assumptions fitted to synthetic data. Not a forecast.
    The same seed always returns the same result.
    """
    return unwrap_tool_result(
        run_loss_simulation(ctx, request.system_id, request.number_of_simulations, request.random_seed))


@router.get("/scenarios", response_model=ScenarioListResult, summary="List predefined scenarios")
def scenarios(ctx: ToolContext = Depends(get_tool_context)) -> ScenarioListResult:
    """The predefined illustrative stress scenarios with their assumptions and notes."""
    return unwrap_tool_result(list_scenarios(ctx))


@router.post("/scenarios/compare", response_model=ScenarioComparisonResult, summary="Compare baseline and stress scenario")
def compare_scenario(
    request: ScenarioCompareRequest, ctx: ToolContext = Depends(get_tool_context)
) -> ScenarioComparisonResult:
    """Baseline versus a predefined illustrative stress scenario (for example ``SHARED_VENDOR_OUTAGE``).

    The scenario numbers are illustrative assumptions, not calibrated estimates.
    """
    return unwrap_tool_result(compare_baseline_and_stress(
        ctx, request.system_id, request.scenario_id, request.number_of_simulations, request.random_seed))


@router.post("/scenarios/compare-custom", response_model=ScenarioComparisonResult,
             summary="Compare baseline and a user-defined stress scenario")
def compare_custom_scenario(
    request: CustomScenarioRequest, ctx: ToolContext = Depends(get_tool_context)
) -> ScenarioComparisonResult:
    """Baseline versus a stress scenario defined by explicit numbers: a multiplier on the incident
    rate, a shift of the log-severity mean and a multiplier on the log-severity spread.

    The numbers are user-supplied assumptions, not estimates and not calibrated. Unlike the
    predefined scenarios, this endpoint is not available to the AI agent.
    """
    return unwrap_tool_result(compare_baseline_and_custom_scenario(
        ctx, request.system_id, request.lambda_multiplier, request.severity_mu_shift,
        request.severity_sigma_multiplier, request.number_of_simulations, request.random_seed))
