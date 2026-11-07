# Agent Tools

The tool layer is the **only way the AI agent can read data or obtain numbers**. This document explains why the layer exists, what each tool does, and the rules it enforces.

> The agent (see [agent_design.md](agent_design.md)) calls only these tools. All data are synthetic and all model results are illustrative. See [limitations.md](limitations.md).

Code: [`src/risksignal/tools/`](../src/risksignal/tools).

---

## 1. Why deterministic tools make the agent safer and more auditable

A language model is good at deciding what to look at next and at writing clear prose. It is not a database, not a calculator and not a simulator, and it can state wrong things fluently. The design therefore gives the model **no way to touch data or numbers except through ordinary Python functions**:

- **No invented numbers.** Counts, dates, losses, percentiles and Expected Shortfall come from tool results. The agent may quote them and is instructed never to compute them; the investigator additionally flags any number in the answer that matches no tool output (best effort). A percentile from a Monte Carlo simulation cannot be produced by a language model anyway.
- **No direct database access.** The agent has no SQL tool. Tools use fixed `SELECT` statements and pass user input only as bound parameters, so arbitrary SQL cannot be run, and nothing can be written.
- **Auditability.** Each statement in an answer can be traced to a specific tool call with specific arguments and a structured result. A reviewer can replay the calls and get identical results.
- **Reproducibility.** Tools are deterministic. Simulations take an explicit seed, and "recent" is measured from the dataset's end date (not today's date), so the same call always returns the same answer.
- **Provenance.** Every result says whether it is *observed synthetic data* or *modelled output*. Model results separate the observed basis, the assumptions and the simulated outputs, so the agent's four-section answer (observed evidence, model assumptions, simulation results, questions) maps directly onto tool outputs.
- **Typed failure instead of improvisation.** If a system does not exist, the tool says so with suggestions. Without that, a model may fill the gap with something plausible. The agent can see the error and report it.
- **Testability.** Tools are plain functions with unit tests. The agent loop can later be tested with a mock LLM that calls them.
- **Replaceable model.** Because the LLM only touches this interface, the provider can change without touching any risk logic.

In short: **the model chooses and explains; Python retrieves and calculates.**

## 2. The tools

All tools take a `ToolContext` as first argument (the database path, the "as of" date and the graph; see section 5).

| Tool | Purpose | Kind of result |
|---|---|---|
| `get_system_profile(ctx, system_id)` | System details, criticality, primary business process, basic metadata (incident and control counts, KRIs tracked, data window). | Observed synthetic data |
| `get_recent_incidents(ctx, system_id, months=12)` | Incident records in the window (oldest first) with counts by category and severity, total loss, and a count of descriptions mentioning "deployment". | Observed synthetic data |
| `get_kri_history(ctx, system_id, months=12)` | The last `months` monthly observations of each KRI, grouped by KRI, with latest value, window mean, minimum and maximum, and the percentage change of the window mean against the previous window of the same length. | Observed synthetic data |
| `get_controls(ctx, system_id)` | Controls with type, last review date, review status and days since review; overdue and due control IDs. | Observed synthetic data |
| `get_dependencies(ctx, system_id)` | Vendors, supported processes, controls, shared vendors, related systems, upstream and downstream systems, and indirect vendors. Delegates to the graph module. | Observed synthetic data (structural) |
| `run_loss_simulation(ctx, system_id, number_of_simulations=100000, random_seed=42)` | Baseline Monte Carlo simulation of annual aggregate loss. Delegates to the stochastic engine. | Modelled output |
| `compare_baseline_and_stress(ctx, system_id, scenario_id, number_of_simulations=100000, random_seed=42)` | Baseline versus a **predefined** illustrative scenario (currently `SHARED_VENDOR_OUTAGE`), with absolute and percentage differences. Delegates to the scenario engine. | Modelled output |
| `get_kri_monitoring(ctx, system_id)` | Past-only rolling median/MAD review signals, explicit data status, source references and walk-forward flag workload. Not appetite or predictive accuracy. | Observed synthetic data and descriptive rule |
| `get_model_diagnostics(ctx, system_id)` | Training-only fit and a twelve-month synthetic holdout, pooling, conditional count interval, dispersion and individual-loss tail exceedances. | Modelled diagnostic output |
| `get_risk_workpaper(ctx, system_id)` | Existing evidence plus monitoring/diagnostics and source-linked questions for RCSA preparation, with a reproducible fingerprint. No rating or sign-off. | Mixed evidence, nested provenance labels |

Tools delegate rather than reimplement: simulation tools call `run_system_simulation` and `run_scenario_analysis` from the stochastic package, and the dependency tool calls the graph query functions. Tests check these calls with spies and compare results with direct calls.

### Additional conversational tools and restricted custom assumptions

The conversational registry adds four portfolio functions to the ten investigation/workbench tools. Custom numeric scenario assumptions remain restricted to explicit human inputs through the API/dashboard:

| Function | Used by | Agent access |
|---|---|---|
| `list_systems` | API, dashboard, conversational assistant | Conversational registry only |
| `get_bank_overview` | API, dashboard, conversational assistant | Conversational registry only |
| `get_portfolio_summary` | Conversational assistant | Conversational registry only |
| `list_scenarios` | API, dashboard, conversational assistant | Conversational registry only |
| `compare_baseline_and_custom_scenario` | API, dashboard "Advanced assumptions" | Not registered; only a person may supply free numeric stress assumptions |

Model-facing views omit chart histograms and bulky walk-forward `history` fields,
but retain latest calculations, summary statistics and source references. Full histories
remain in the monitoring/workpaper API and JSON export. Workbench AI drafts must come
from a completed run with matching source-workpaper fingerprint. This is a snapshot
identity check, not semantic verification or an authenticated audit signature.

### What the simulation results contain

A modelled result has three clearly separated sections:

1. `observed_basis`: the synthetic observations used (incident count, years observed, how many losses the severity fit used, which dataset, and any fallback notes).
2. `model_assumptions` (and `stress_assumptions` for scenarios): model form, `lambda`, `mu`, `sigma` and where each came from (estimated from history, bank-wide fallback, or scenario assumption), seed, number of simulations, and a list of plain-language assumption statements.
3. `simulation_results`: mean, median, P95, P99, Expected Shortfall 95 and 99, the closed-form mean as a sanity check, and a compact histogram.

Stress scenario numbers are labelled illustrative and not calibrated. The agent can only choose among predefined scenarios; it cannot supply its own numbers.

## 3. Result and error conventions

Every tool returns either a result model with `ok = true` or a `ToolError` with `ok = false`. **Tools never raise exceptions to the caller.** Both are Pydantic models that serialise to JSON.

| `error_type` | Meaning |
|---|---|
| `unknown_system` | The system ID does not exist. Includes suggestions (close matches, so a lowercase or mistyped ID is not silently accepted). |
| `unknown_scenario` | The scenario ID is not predefined. Suggestions list the available ones. |
| `invalid_argument` | A wrong type or out-of-range value (for example `months` outside 1 to 120, simulations outside 1,000 to 1,000,000, a negative seed, or a non-string system ID). |
| `model_error` | The stochastic engine refused to run, for example because there is not enough data to fit the model. The message says why. |
| `data_unavailable` | The database is missing or unreadable. The message says how to generate it. |
| `internal_error` | An unexpected bug. The message is generic; details are logged for developers and never shown to the user. |

## 4. Rules the layer enforces

- **Read-only.** There is no tool that writes, edits or deletes anything.
- **No arbitrary SQL.** SQL text is fixed in the tool modules. A test scans them to confirm they only contain `SELECT` statements without string interpolation, and that injection attempts are treated as unknown IDs.
- **No statistics in tools beyond simple descriptive ones** on observed data (counts, sums, means). All model statistics come from the stochastic package.
- **Arguments are validated** before use. Booleans are not accepted as integers.
- **No LLM or UI imports** in the tool modules.

## 5. The tool context

`ToolContext` holds the database path, the graph (built once on first use) and two dates:

- `as_of_date` is the "present" of the synthetic world: the end of the data (30 September 2026). "Last 12 months" is measured back from it, so results never depend on today's date.
- `observation_start` is the start of the data (1 October 2021). With `as_of_date` it defines the span over which incident frequency is measured.

Window rules: incidents use the half-open window (`as_of_date` minus `months` months, `as_of_date`]. KRI tools return the last `months` monthly observations.

## 6. How the demo uses them

For a broad `PAYMENT_ENGINE_01` investigation, the default offline script calls `get_system_profile`, `get_recent_incidents`, `get_kri_monitoring`, `get_controls` and `get_dependencies`. A financial-loss question additionally calls `run_loss_simulation`; an explicit stress request also calls `compare_baseline_and_stress`. The live LLM chooses from the same read-only tools, subject to the prompt and argument validation. Findings and follow-up questions cite returned record IDs. `get_kri_history` remains available for descriptive window comparisons.

## 7. Limitations and assumptions

- "Deployment-related" is a keyword match on the free-text description, because the data have no separate cause field. The tool says so.
- KRI comparison against the previous window is purely descriptive. No trend is projected and no meaning is attached.
- The tools cannot establish causation, risk ratings or decisions. Neither can the agent.
- The graph is built once per context. If the database is regenerated while an application runs, create a new context.
- Real use would need institution data, access control, audit logging and approved model governance. None exists here.
