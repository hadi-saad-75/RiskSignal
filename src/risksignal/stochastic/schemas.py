"""Pydantic result types for the stochastic engine.

Each object says where its numbers came from (historical synthetic observations,
estimated parameters, user-supplied assumptions, simulation outputs), so a reader can
always tell them apart. The 100,000 simulated annual losses are never stored here;
only summary statistics and an optional compact histogram are.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER = (
    "Synthetic data and illustrative model only. Not calibrated to any real institution, "
    "not predictive, and not a regulatory capital figure."
)

# How lambda was obtained.
FrequencyMethod = Literal[
    "system_history",  # estimated: this system's incident count / years observed
    "bank_wide_per_system_average",  # estimated fallback: too few incidents for this system
    "user_override",  # user-supplied assumption
]

# Which dataset the severity parameters were fitted to.
SeverityDataSource = Literal["system", "category", "bank_wide"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FrequencyEstimate(_Model):
    """Poisson rate lambda (expected incidents per year) and how it was obtained."""

    lambda_used: float = Field(gt=0)
    method: FrequencyMethod
    lambda_historical: float | None = Field(
        default=None,
        description="Rate implied by this system's own history alone (incidents / years). "
        "Shown for comparison when the value used differs from it.",
    )
    observed_incidents: int = Field(ge=0, description="Incidents recorded for this system in the window.")
    observation_years: float = Field(gt=0)
    note: str


class SeverityEstimate(_Model):
    """Lognormal parameters in log space, and which historical losses they were fitted to."""

    mu: float
    sigma: float = Field(ge=0)
    n_losses: int = Field(ge=2)
    data_source: SeverityDataSource
    data_description: str
    fallback_notes: list[str] = Field(
        default_factory=list,
        description="Why a more specific dataset was not used, if a fallback happened.",
    )


class LossMetrics(_Model):
    """Summary of the simulated annual aggregate loss distribution."""

    mean: float = Field(ge=0)
    median: float = Field(ge=0)
    p95: float = Field(ge=0)
    p99: float = Field(ge=0)
    expected_shortfall_95: float = Field(ge=0)
    expected_shortfall_99: float = Field(ge=0)


class LossHistogram(_Model):
    """Compact histogram of simulated annual losses over [0, upper limit].

    ``counts`` has ``len(bin_edges) - 1`` entries. Years with a loss above the last edge
    are not binned; they are counted in ``overflow_count`` so nothing is hidden.
    """

    bin_edges: list[float]
    counts: list[int]
    overflow_count: int = Field(ge=0)
    upper_limit_description: str


class SimulationResult(_Model):
    """Output of one Monte Carlo run for one system."""

    system_id: str
    incident_category: str | None = Field(
        default=None, description="If set, only incidents of this category were modelled."
    )

    # Frequency: N ~ Poisson(lambda_used)
    lambda_used: float = Field(gt=0)
    frequency_estimation_method: FrequencyMethod
    lambda_historical: float | None = None
    observed_incident_count: int = Field(ge=0)
    observation_years: float = Field(gt=0)
    frequency_note: str

    # Severity: X ~ Lognormal(severity_mu, severity_sigma), parameters in log space
    severity_mu: float
    severity_sigma: float = Field(ge=0)
    severity_data_source: SeverityDataSource
    severity_data_description: str
    severity_n_losses: int = Field(ge=2)
    severity_fallback_notes: list[str] = Field(default_factory=list)

    # Simulation settings
    number_of_simulations: int = Field(gt=0)
    random_seed: int

    # Simulation outputs: annual aggregate loss L = X_1 + ... + X_N
    mean_annual_loss: float = Field(ge=0)
    median_annual_loss: float = Field(ge=0)
    p95: float = Field(ge=0)
    p99: float = Field(ge=0)
    expected_shortfall_95: float = Field(ge=0)
    expected_shortfall_99: float = Field(ge=0)

    # Closed-form check: E[L] = lambda * exp(mu + sigma^2 / 2). Computed, not simulated.
    analytic_mean_annual_loss: float = Field(ge=0)

    histogram: LossHistogram | None = None
    disclaimer: str = DISCLAIMER


# ----------------------------------------------------------------------------- scenarios

SCENARIO_DISCLAIMER = (
    "Stress scenario assumptions are illustrative numbers chosen to demonstrate the mechanics. "
    "They are not empirically calibrated, not expert-validated and have no institutional validity. "
    "The data are synthetic."
)

ScenarioProvenance = Literal["predefined_illustrative", "user_supplied"]


class ModelParameters(_Model):
    """The three numbers that define the model: N ~ Poisson(lambda), X ~ Lognormal(mu, sigma)."""

    lambda_value: float = Field(gt=0, allow_inf_nan=False)
    mu: float = Field(allow_inf_nan=False)
    sigma: float = Field(ge=0, allow_inf_nan=False)


class BaselineModel(_Model):
    """Baseline parameters with the evidence behind them (estimated from synthetic history,
    or user-supplied if a lambda override was used)."""

    system_id: str
    incident_category: str | None = None
    parameters: ModelParameters
    frequency: FrequencyEstimate
    severity: SeverityEstimate


class Scenario(_Model):
    """Explicit stress assumptions, applied to baseline parameters as

        lambda_stress = lambda_multiplier * lambda_baseline
        mu_stress     = mu_baseline + severity_mu_shift
        sigma_stress  = severity_sigma_multiplier * sigma_baseline

    The default values (1, 0, 1) leave the baseline unchanged. The bounds are guard rails
    against typos and numerical overflow, not statements about what is realistic.
    """

    scenario_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str
    lambda_multiplier: float = Field(default=1.0, gt=0, le=100, allow_inf_nan=False)
    severity_mu_shift: float = Field(default=0.0, ge=-5, le=5, allow_inf_nan=False)
    severity_sigma_multiplier: float = Field(default=1.0, gt=0, le=5, allow_inf_nan=False)
    assumption_notes: list[str] = Field(default_factory=list)
    provenance: ScenarioProvenance = "user_supplied"


class MetricDifferences(_Model):
    """stress - baseline for each metric (absolute, in loss units; may be negative)."""

    mean: float
    median: float
    p95: float
    p99: float
    expected_shortfall_95: float
    expected_shortfall_99: float


class MetricPercentChanges(_Model):
    """100 * (stress - baseline) / baseline for each metric, in percent.

    ``None`` where the baseline value is zero, because a percentage change from zero is
    undefined.
    """

    mean: float | None
    median: float | None
    p95: float | None
    p99: float | None
    expected_shortfall_95: float | None
    expected_shortfall_99: float | None


class ParameterChanges(_Model):
    """How the scenario moved each model parameter.

    No percentage is given for mu: it is a log-space location that can be zero or negative,
    so a percentage change is not meaningful. Its shift acts multiplicatively on losses:
    the median loss exp(mu) is multiplied by exp(mu_absolute).
    """

    lambda_absolute: float
    lambda_percent: float
    mu_absolute: float
    sigma_absolute: float
    sigma_percent: float | None


class ScenarioComparison(_Model):
    """Baseline versus stress simulation for one system. Baseline and stress are kept apart:
    nothing in the ``baseline_*`` fields is affected by the scenario."""

    system_id: str
    scenario: Scenario
    baseline_model: BaselineModel

    baseline_parameters: ModelParameters
    stress_parameters: ModelParameters
    parameter_changes: ParameterChanges

    baseline_metrics: LossMetrics
    stress_metrics: LossMetrics
    absolute_differences: MetricDifferences
    percentage_differences: MetricPercentChanges

    # Closed form E[L] = lambda * exp(mu + sigma^2 / 2), computed, not simulated.
    baseline_analytic_mean_annual_loss: float = Field(ge=0)
    stress_analytic_mean_annual_loss: float = Field(ge=0)

    number_of_simulations: int = Field(gt=0)
    random_seed: int = Field(description="The same seed is used for the baseline and the stress run.")
    baseline_histogram: LossHistogram | None = None
    stress_histogram: LossHistogram | None = None

    disclaimer: str = SCENARIO_DISCLAIMER
