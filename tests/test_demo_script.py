"""Guards for docs/demo_script.md: the numbers and story facts it quotes must match the application.

The demo script quotes values read from the application (incident counts, KRI changes, model
parameters, baseline and stress metrics). These tests recompute every one of them from a freshly
generated seed-42 dataset using the real tools, so the script cannot silently go stale, and they
check the story facts the script relies on. Nothing is adjusted to fit the story: if the data
stop supporting a claim, a test fails.
"""

import re
from pathlib import Path

import pytest

from risksignal.data.generator import DEFAULT_SEED, generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.tools.context import ToolContext
from risksignal.tools.control_tools import get_controls
from risksignal.tools.graph_tools import get_dependencies
from risksignal.tools.incident_tools import get_recent_incidents
from risksignal.tools.kri_tools import get_kri_history
from risksignal.tools.simulation_tools import compare_baseline_and_stress, run_loss_simulation
from risksignal.ui.formatting import format_amount, format_decimal, format_percent

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "docs" / "demo_script.md").read_text(encoding="utf-8")
FOCAL, SIBLING = "PAYMENT_ENGINE_01", "PAYMENT_ENGINE_02"


@pytest.fixture(scope="module")
def ctx(tmp_path_factory: pytest.TempPathFactory) -> ToolContext:
    return ToolContext(db_path=save_atlas_bank(generate_atlas_bank(DEFAULT_SEED), tmp_path_factory.mktemp("demo_db")))


def kri_changes(ctx: ToolContext, months: int) -> dict[str, float]:
    return {s.kri_name: s.change_vs_previous_window_percent for s in get_kri_history(ctx, FOCAL, months).series}


# ----------------------------------------------------------------- the numbers quoted in the script


def test_reference_values_in_the_script_match_the_application(ctx: ToolContext) -> None:
    baseline = run_loss_simulation(ctx, FOCAL)
    stress = compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE")
    metrics = baseline.simulation_results.metrics
    results = stress.simulation_results
    expected = [
        format_decimal(baseline.model_assumptions.lambda_used, 2),  # lambda
        format_decimal(baseline.model_assumptions.severity_mu, 3),
        format_decimal(baseline.model_assumptions.severity_sigma, 3),
        format_decimal(baseline.observed_basis.observation_years, 2),
        format_amount(metrics.mean), format_amount(metrics.median), format_amount(metrics.p95),
        format_amount(metrics.p99), format_amount(metrics.expected_shortfall_95), format_amount(metrics.expected_shortfall_99),
        format_amount(results.stress_metrics.p95), format_amount(results.stress_metrics.expected_shortfall_95),
        format_percent(results.percentage_differences.p95),
    ]
    missing = [value for value in expected if value not in SCRIPT]
    assert not missing, f"demo_script.md is out of date; missing values: {missing}"


def test_baseline_inside_the_stress_comparison_is_the_same_as_the_baseline_run(ctx: ToolContext) -> None:
    # The Scenario Lab and the agent show the same baseline because they use the same tool and seed.
    baseline = run_loss_simulation(ctx, FOCAL).simulation_results.metrics
    compared = compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE").simulation_results.baseline_metrics
    assert baseline == compared


def test_kri_changes_quoted_in_the_script_match_the_application(ctx: ToolContext) -> None:
    for months in (12, 24):
        for name, change in kri_changes(ctx, months).items():
            assert change is not None
            assert format_percent(change) in SCRIPT, f"{months}-month change of {name} ({format_percent(change)}) not in the script"


def test_incident_control_and_vendor_facts_quoted_in_the_script(ctx: ToolContext) -> None:
    incidents = get_recent_incidents(ctx, FOCAL, 12)
    assert incidents.counts.total == 5 and incidents.counts.deployment_keyword_matches == 2
    assert incidents.counts.by_category == {"human_error": 1, "technology_failure": 2, "third_party_failure": 2}
    assert sum("Keystone Payment Rails" in i.description for i in incidents.incidents) == 2
    assert "5 (2 mention deployment, 2 are Keystone Payment Rails V04 events, 1 human error)" in SCRIPT

    controls = get_controls(ctx, FOCAL)
    overdue = next(c for c in controls.controls if c.control_id == "C002")
    assert len(controls.controls) == 4 and controls.overdue_control_ids == ["C002"] and controls.due_control_ids == ["C004"]
    assert overdue.name == "Pre-Release Regression Testing" and f"{overdue.days_since_last_review} days" in SCRIPT
    assert "C004 Vendor Performance Review" in SCRIPT

    deps = get_dependencies(ctx, FOCAL)
    shared = {s.vendor.vendor_id: [o.system_id for o in s.other_systems] for s in deps.shared_vendors}
    assert shared["V04"] == [SIBLING] and sorted(shared["V02"]) == ["CLEARING_INTERFACE_01", "MESSAGING_HUB_01"]
    assert {v.vendor_id: v.name for v in deps.vendors}["V04"] == "Keystone Payment Rails"


# ----------------------------------------------------------------- the story the script tells


def test_the_data_support_the_story_without_adjustment(ctx: ToolContext) -> None:
    focal = get_recent_incidents(ctx, FOCAL, 12)
    assert focal.counts.total >= 3 and focal.counts.deployment_keyword_matches >= 2  # recent incidents, some deployment related
    assert get_controls(ctx, FOCAL).overdue_control_ids  # at least one overdue control

    longer = kri_changes(ctx, 24)
    assert longer["failed_deployment_rate"] > 0 and longer["control_exception_count"] > 0
    assert longer["near_miss_count"] < 0  # the script says this one does not deteriorate
    assert kri_changes(ctx, 12)["control_exception_count"] == 0  # and that this one is flat over the last 12 months

    shared = {s.vendor.vendor_id: [o.system_id for o in s.other_systems] for s in get_dependencies(ctx, FOCAL).shared_vendors}
    assert SIBLING in shared["V04"]  # shared vendor with PAYMENT_ENGINE_02


def test_the_sibling_system_facts_stated_in_the_script(ctx: ToolContext) -> None:
    sibling = get_recent_incidents(ctx, SIBLING, 12)
    assert sibling.counts.total == 5  # "has recent incidents of its own"
    keystone = [i for i in sibling.incidents if "Keystone Payment Rails" in i.description]
    assert len(keystone) == 3
    focal_dates = {i.date for i in get_recent_incidents(ctx, FOCAL, 12).incidents if "Keystone Payment Rails" in i.description}
    assert {str(i.date) for i in keystone} & {str(d) for d in focal_dates} == {"2025-11-24"}  # hit on the same day
    assert not get_controls(ctx, SIBLING).overdue_control_ids and "24 November 2025" in SCRIPT


def test_the_stress_result_is_the_arithmetic_of_the_documented_assumptions(ctx: ToolContext) -> None:
    result = compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE")
    scenario = result.stress_assumptions.scenario
    assert (scenario.lambda_multiplier, scenario.severity_mu_shift, scenario.severity_sigma_multiplier) == (1.8, 0.2, 1.1)
    assert scenario.provenance == "predefined_illustrative"
    assert "λ ×1.8, μ +0.2, σ ×1.1" in SCRIPT


# ----------------------------------------------------------------- structure and honesty of the script


def test_script_follows_the_requested_ten_step_sequence() -> None:
    steps = re.findall(r"^### Step (\d+)\. (.+)$", SCRIPT, re.MULTILINE)
    assert [int(n) for n, _ in steps] == list(range(1, 11))
    titles = " ".join(t.lower() for _, t in steps)
    for word in ("problem", "payment_engine_01", "dependencies", "scenario analysis", "baseline", "stress", "assistant",
                 "evidence", "limitations", "real team"):
        assert word in titles, word
    assert "Likely technical questions" in SCRIPT and "Part 2" in SCRIPT and "Part 3" in SCRIPT


@pytest.mark.parametrize("question", [
    "Why Poisson?", "What if the variance exceeds the mean?", "Why Lognormal?", "What about heavy tails?", "Why not EVT?",
    "Why not Hawkes processes?", "Why not TabPFN, XGBoost or any predictive model?", "Why synthetic data?",
    "Why an LLM agent at all?", "What prevents hallucinated numbers?", "Why NetworkX?", "How would this scale?",
    "How could real KRIs affect λ?", "How would you validate this model?",
])
def test_all_requested_technical_questions_are_answered(question: str) -> None:
    match = re.search(rf"^\*\*{re.escape(question)}\*\*\n(.+)$", SCRIPT, re.MULTILINE)
    assert match and len(match.group(1)) > 80, question


def test_script_states_the_required_caveats() -> None:
    lowered = SCRIPT.lower()
    for phrase in ("synthetic", "illustrative", "constructed", "not a forecast", "no claim of predictive validity",
                   "not a language model", "best effort", "has not been exercised in development", "no results claimed",
                   "arithmetic of my assumptions", "not established", "live model behaviour has not been evaluated"):
        assert phrase in lowered, phrase


def test_script_does_not_overstate_open_research_questions() -> None:
    positive_claims = (r"\bproves that\b", r"\bdemonstrates that\b", r"\bwe showed\b", r"\boutperforms\b", r"\bsolves\b",
                       r"\bhas been validated\b", r"\bis validated\b")
    for pattern in positive_claims:
        assert not re.search(pattern, SCRIPT, re.IGNORECASE), pattern


def test_every_linked_document_exists() -> None:
    for target in re.findall(r"\]\(([^)#]+\.md)", SCRIPT):
        assert (ROOT / "docs" / target).is_file(), target


def test_setup_commands_in_the_script_are_real() -> None:
    for command in ("python -m risksignal.data.generator", "streamlit run src/risksignal/ui/app.py --client.toolbarMode viewer",
                    "uvicorn risksignal.api.main:app", "RISKSIGNAL_LLM_PROVIDER=mock", "docker compose up --build",
                    "python -m risksignal.agent.investigator --mock"):
        assert command in SCRIPT, command
    assert (ROOT / "src" / "risksignal" / "ui" / "app.py").is_file()
