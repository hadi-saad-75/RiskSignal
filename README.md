# RiskSignal

**An agentic Operational Risk investigation and stochastic scenario prototype (research prototype, synthetic data only).**

> **Development status: working prototype.**
> - **Done:** repository structure, domain documentation, the synthetic Atlas Bank dataset (generator, validation, CSV and SQLite storage), the stochastic frequency-severity engine, the stress scenario engine, the dependency graph, the deterministic tool layer, the investigation agent, the FastAPI backend, the Streamlit dashboard, and Docker setup for local demonstration.
> - **Not built:** authentication, cloud deployment and anything listed as future research.
> - **Not yet exercised in development:** the live Anthropic investigator (no API key was available; the offline mock provider is fully tested) and the Docker images (no Docker engine was available; the build steps, health check and minimal UI environment were checked by emulating them with plain Python).

## Objective

RiskSignal explores how technology-related Operational Risk (outages, failed deployments, vendor failures, control failures) can be investigated by combining:

- a small synthetic dataset for a fictional institution, **Atlas Bank**,
- a dependency graph (systems, business processes, vendors, controls),
- a classical **frequency-severity** loss model with Monte Carlo simulation,
- an **AI investigation agent** that gathers evidence by calling deterministic Python tools.

The agent calls only deterministic, read-only Python tools and is instructed to calculate or invent nothing itself: every risk number is computed by a tool, and any number the agent writes is checked against the tool outputs (a best-effort check, not a guarantee; see [docs/agent_design.md](docs/agent_design.md)).

## Quick start

### Option A: Docker (one command)

Requires Docker with Compose v2.

```bash
git clone <repository-url> RiskSignal
cd RiskSignal
docker compose up --build
```

Then open the dashboard at <http://localhost:8501>. The API documentation is at <http://localhost:8000/docs> and the health check at <http://localhost:8000/health>. Stop with `Ctrl+C`, then `docker compose down`.

- The first build downloads the dependencies and takes a few minutes. The synthetic Atlas Bank database is generated during the API image build (seeded, so it is identical every time).
- The dashboard container starts only after the API container reports healthy (`GET /health`).
- **Without an API key** everything works except the live AI Investigator, which explains that it needs `ANTHROPIC_API_KEY`. To try the AI Investigator offline with the deterministic mock provider:
  - macOS/Linux: `RISKSIGNAL_LLM_PROVIDER=mock docker compose up --build`
  - Windows PowerShell: `$env:RISKSIGNAL_LLM_PROVIDER="mock"; docker compose up --build`
- **With an API key**: copy `.env.example` to `.env` (macOS/Linux `cp .env.example .env`, Windows `Copy-Item .env.example .env`), set `ANTHROPIC_API_KEY=` to your key, then run `docker compose up --build`. `.env` is git-ignored and excluded from the Docker images.
- Ports are published on `localhost` only, because the application has no authentication.

### Option B: run locally with Python

Requires Python 3.12 or newer.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell   (cmd: .venv\Scripts\activate.bat)
source .venv/bin/activate           # macOS / Linux

# 2. Install the dependencies and the package (editable)
pip install -e ".[dev]"

# 3. Generate the synthetic Atlas Bank data (CSV files and data/synthetic/atlas_bank.db)
python -m risksignal.data.generator

# 4. Run the tests (offline: they use a mock LLM and need no API key)
pytest

# 5. Start the API (terminal 1)            -> http://127.0.0.1:8000/docs
uvicorn risksignal.api.main:app --reload

# 6. Start the dashboard (terminal 2)      -> http://localhost:8501
streamlit run src/risksignal/ui/app.py
```

To use the AI Investigator, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY=` before step 5, or start the API in offline mock mode (`RISKSIGNAL_LLM_PROVIDER=mock`, PowerShell: `$env:RISKSIGNAL_LLM_PROVIDER="mock"`). You can also try the agent without any server: `python -m risksignal.agent.investigator --mock "Investigate PAYMENT_ENGINE_01."`.

### Settings

All settings are environment variables (a local `.env` file is also read). None is required to run the deterministic parts.

| Variable | Used by | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | API | Enables the live AI investigator. Never commit it. |
| `ANTHROPIC_MODEL` | API | Optional: override the default Anthropic model. |
| `RISKSIGNAL_LLM_PROVIDER` | API | `anthropic` (default) or `mock` (offline, deterministic). |
| `RISKSIGNAL_API_URL` | Dashboard | Where the dashboard finds the API (default `http://127.0.0.1:8000`; `http://api:8000` in Docker). |
| `RISKSIGNAL_DB_PATH` | API | SQLite database path (default `data/synthetic/atlas_bank.db`). |

## Architecture

```
Synthetic Atlas Bank data
        |
        v
SQLite data access
        |
        v
NetworkX dependency graph
        |
        v
Stochastic frequency-severity engine
        |
        v
Deterministic Python tool layer
        |
        v
AI investigation agent (LLM behind a small interface)
        |
        v
FastAPI backend
        |
        v
Streamlit dashboard
```

See [docs/architecture.md](docs/architecture.md).

## Scientific positioning

- All data are **synthetic**. Nothing here represents any real bank, including JPMorgan.
- Model parameters are **illustrative**. There is **no claim of predictive validity**, no institution-specific calibration and no regulatory capital claim.
- The aim is to demonstrate architecture, agent orchestration, quantitative modelling mechanics, dependency analysis and scenario analysis.
- The AI agent is an investigation assistant. It makes no final risk decision.
- The elements deliberately left out (real loss data, calibration, tail modelling, validation, governance) are the work a real Operational Risk team would need to do.

See [docs/limitations.md](docs/limitations.md).

## The demo

1. Select `PAYMENT_ENGINE_01` in the dashboard and click **Investigate**.
2. The agent retrieves the system profile, recent incidents, KRIs, controls and dependencies, and identifies systems that share its vendors.
3. It runs a baseline Monte Carlo simulation and, optionally, a predefined vendor-outage stress scenario.
4. It writes a summary with four sections: observed evidence, model assumptions, simulation results, and suggested investigation questions.

## Generating the synthetic Atlas Bank dataset

```bash
python -m risksignal.data.generator              # default seed 42, writes to data/synthetic/
python -m risksignal.data.generator --seed 7     # a different (but still reproducible) dataset
```

The same seed always produces byte-identical files. The command writes one CSV per table (for inspection) and then builds `data/synthetic/atlas_bank.db` from those CSVs. **SQLite is the application's main data source**; the CSVs are the human-readable copy. The `.db` file is git-ignored because it can be regenerated at any time.

| Table | Rows (seed 42) | Content |
|---|---|---|
| `systems` | 20 | Technology systems, including `PAYMENT_ENGINE_01` and `PAYMENT_ENGINE_02`. |
| `processes` | 10 | Business processes (International Payments, Domestic Payments, Trade Settlement, Client Onboarding, Identity and Access Management, and others). |
| `vendors` | 8 | Fictional external vendors. |
| `controls` | 40 | Controls per system with a review date and a `current` / `due` / `overdue` status. |
| `incidents` | about 300 | Roughly five years of incidents (Oct 2021 to Sep 2026) in five categories with a financial loss and severity. |
| `kri_observations` | about 5,900 | Monthly values of five KRIs per system (vendor KRI only where a vendor dependency exists). |
| `dependencies` | about 77 | `SYSTEM SUPPORTS PROCESS`, `SYSTEM DEPENDS_ON VENDOR`, `SYSTEM DEPENDS_ON SYSTEM`. |

Checks run on every generation and every CSV load: unique IDs, foreign keys, non-negative losses, valid dates, and dependencies that reference existing entities.

### Why the data are synthetic

Atlas Bank is fictional. No real institution's data, including JPMorgan's, were used, and real operational loss data are confidential and institution specific. The dataset exists only to exercise the architecture and workflow.

- It must **not** be read as realistic, and it is **not** evidence of predictive performance.
- The generator contains no hidden predictive label, no "future incident probability" and no machine learning target.
- The focal system `PAYMENT_ENGINE_01` has a **deliberately constructed** story (recent incidents including failed deployments, an overdue control, mildly worsening KRIs, a vendor shared with `PAYMENT_ENGINE_02`). Other systems get some drift and overdue controls too. Whatever is found about it is a property of the constructed data, not a discovery about the world.
- Incident losses are drawn from Lognormal distributions **by construction**. A Lognormal model fitted later to these data will therefore fit well, and that says nothing about whether real losses behave this way.
- Incidents have no separate cause field. Deployment-related incidents are identified from their description text.

## Stochastic risk engine

The engine in `src/risksignal/stochastic/` simulates annual aggregate loss with a classical frequency-severity model:

```
N ~ Poisson(lambda)              number of incidents in one year
X_i ~ Lognormal(mu, sigma)       loss of incident i
L = X_1 + ... + X_N              annual aggregate loss
```

Monte Carlo simulation plays out many imaginary years (100,000 by default) and reports the mean, median, P95, P99 and Expected Shortfall at 95% and 99% (the average loss in the worst 5% / 1% of simulated years). Results are deterministic for a given seed and carry labels showing where each number came from: estimated from synthetic history, user-supplied, or simulated. The engine never uses an LLM.

```python
from datetime import date
from risksignal.data.storage import read_table
from risksignal.stochastic.simulation import run_system_simulation

incidents = read_table("incidents")  # needs data/synthetic/atlas_bank.db; see above
result = run_system_simulation(
    incidents, "PAYMENT_ENGINE_01",
    observation_start=date(2021, 10, 1), observation_end=date(2026, 9, 30),
    seed=42,                       # same seed, same result
    # lambda_override=6.0,         # optional user-supplied assumption
)
print(result.lambda_used, result.frequency_estimation_method)
print(result.severity_data_source, result.p95, result.expected_shortfall_95)
```

All parameters are illustrative and the synthetic losses were generated from Lognormal distributions, so a good fit proves nothing about real losses. See [docs/stochastic_model.md](docs/stochastic_model.md) for the full explanation (plain English first, then the equations).

## Stress scenarios

A scenario is a "what if" written as explicit numbers: a multiplier on the incident rate `lambda`, a shift of the log-severity mean `mu`, and a multiplier on the log-severity spread `sigma`. The engine applies it to the baseline, simulates both from common random numbers (year by year, so differences reflect the assumptions rather than sampling luck), and returns baseline and stress parameters, metrics, absolute differences and percentage differences. One predefined demonstration scenario, `SHARED_VENDOR_OUTAGE`, is included; users can also supply their own numbers.

```python
from risksignal.stochastic.scenario import SHARED_VENDOR_OUTAGE, make_user_scenario, run_scenario_analysis

comparison = run_scenario_analysis(
    incidents, "PAYMENT_ENGINE_01", SHARED_VENDOR_OUTAGE,   # or make_user_scenario(1.5, 0.0, 1.2)
    observation_start=date(2021, 10, 1), observation_end=date(2026, 9, 30),
)
print(comparison.baseline_metrics.p95, comparison.stress_metrics.p95)
print(comparison.percentage_differences.expected_shortfall_95)
```

**The scenario numbers are illustrative assumptions.** They are not calibrated, not expert-validated and not derived from the data or by an LLM, and the scenario does not infer any causal link from the dependency graph. See [docs/scenario_analysis.md](docs/scenario_analysis.md), which also describes how they could be calibrated with Operational Risk specialists.

## Dependency graph

A NetworkX graph built from the SQLite tables connects systems, business processes, vendors and controls (`SYSTEM SUPPORTS PROCESS`, `SYSTEM DEPENDS_ON VENDOR`, `SYSTEM DEPENDS_ON SYSTEM`, `SYSTEM PROTECTED_BY CONTROL`). It answers questions that single-system analysis cannot, such as "which other systems share this vendor?" Queries return structured Pydantic objects.

```python
from risksignal.graph.builder import load_graph
from risksignal.graph.queries import get_related_systems

graph = load_graph()   # reads data/synthetic/atlas_bank.db
for related in get_related_systems(graph, "PAYMENT_ENGINE_01").related_systems:
    print(related.system.system_id, [r.explanation for r in related.relationships])
```

A real bank graph would need verified configuration, service, process and vendor data. The synthetic graph demonstrates reasoning mechanics only. See [docs/dependency_graph.md](docs/dependency_graph.md).

## Agent tools

The AI agent does not query the database or calculate anything itself. It only calls seven deterministic, read-only Python tools: `get_system_profile`, `get_recent_incidents`, `get_kri_history`, `get_controls`, `get_dependencies`, `run_loss_simulation` and `compare_baseline_and_stress`. Each returns a structured Pydantic result labelled as *observed synthetic data* or *modelled output*, or a typed `ToolError` (tools never raise). Simulation results separate the observed basis, the model assumptions and the simulated outputs.

```python
from risksignal.tools.context import ToolContext
from risksignal.tools.incident_tools import get_recent_incidents
from risksignal.tools.simulation_tools import run_loss_simulation

ctx = ToolContext()   # reads data/synthetic/atlas_bank.db
incidents = get_recent_incidents(ctx, "PAYMENT_ENGINE_01", months=12)
print(incidents.counts)
simulation = run_loss_simulation(ctx, "PAYMENT_ENGINE_01", number_of_simulations=100_000, random_seed=42)
print(simulation.simulation_results.metrics.p95)
```

See [docs/agent_tools.md](docs/agent_tools.md) for why this makes the agent safer and more auditable.

## Investigation agent

The agent investigates a selected technology system by deciding which of the deterministic tools to call, then writes an evidence-based summary with sections for observed evidence, model assumptions, simulation results, connected exposures, suggested investigation questions and limitations. It is **instructed to calculate nothing itself and makes no risk decisions**: every risk number is computed by a tool, simulation results are described as outputs under stated assumptions (not forecasts), and each investigation returns an auditable tool activity log. Numbers in the answer that cannot be matched to any tool output are flagged (a best-effort check: it cannot prove an answer is right). The LLM sits behind a small provider interface (Anthropic live, deterministic mock for tests).

```bash
# Offline demo, no API key needed (deterministic mock provider)
python -m risksignal.agent.investigator --mock "Investigate PAYMENT_ENGINE_01."

# Live check (needs ANTHROPIC_API_KEY in the environment or in .env; sends only synthetic data)
python -m risksignal.agent.investigator "Investigate PAYMENT_ENGINE_01."
```

Generate the data first (`python -m risksignal.data.generator`). See [docs/agent_design.md](docs/agent_design.md) for the design, the safety rules and the limitations.

## REST API

A thin FastAPI backend exposes the existing business logic. It adds no calculations of its own: every endpoint calls the matching tool, simulation or agent function and returns its result.

```bash
python -m risksignal.data.generator                                  # once: create the synthetic data
uvicorn risksignal.api.main:app --reload                             # then start the API
# open http://127.0.0.1:8000/docs for the interactive documentation
```

Without an Anthropic key, run the agent endpoint in offline demo mode with the deterministic mock provider (PowerShell: `$env:RISKSIGNAL_LLM_PROVIDER="mock"`):

```bash
RISKSIGNAL_LLM_PROVIDER=mock uvicorn risksignal.api.main:app --reload
```

| Endpoint | Purpose |
|---|---|
| `GET /health` | Service status (database and language model availability). |
| `GET /overview` | Bank-wide counts and recent incidents (used by the dashboard). |
| `GET /systems` | All systems. |
| `GET /systems/{system_id}` | System profile. |
| `GET /systems/{system_id}/incidents?months=12` | Recent incidents with counts. |
| `GET /systems/{system_id}/controls` | Controls and review status. |
| `GET /systems/{system_id}/dependencies` | Vendors, processes, shared vendors and related systems. |
| `GET /systems/{system_id}/kri?months=12` | KRI history grouped by KRI. |
| `POST /simulations` | Baseline Monte Carlo loss simulation (`system_id`, `number_of_simulations`, `random_seed`). |
| `GET /scenarios` | The predefined illustrative scenarios and their assumptions. |
| `POST /scenarios/compare` | Baseline versus a predefined illustrative stress scenario (`scenario_id`, e.g. `SHARED_VENDOR_OUTAGE`). |
| `POST /scenarios/compare-custom` | Baseline versus stress numbers supplied by a person (`lambda_multiplier`, `severity_mu_shift`, `severity_sigma_multiplier`). Not available to the AI agent. |
| `POST /agent/investigate` | Ask the agent (`question`, optional `include_tool_outputs`). Returns the answer, a tool activity log and warnings. |

```bash
curl http://127.0.0.1:8000/systems/PAYMENT_ENGINE_01/incidents
curl -X POST http://127.0.0.1:8000/simulations -H "Content-Type: application/json" \
     -d '{"system_id": "PAYMENT_ENGINE_01", "number_of_simulations": 100000, "random_seed": 42}'
curl -X POST http://127.0.0.1:8000/agent/investigate -H "Content-Type: application/json" \
     -d '{"question": "Investigate PAYMENT_ENGINE_01."}'
```

Errors use one JSON shape, `{"error": {"type", "message", "suggestions"}}`, and never include stack traces: `404` unknown system or scenario (with suggestions), `422` invalid parameters (for example `months` outside 1 to 120, or fewer than 1,000 simulations), `503` database or language model unavailable, `500` unexpected failure (generic message). Settings come from environment variables: `RISKSIGNAL_DB_PATH`, `RISKSIGNAL_LLM_PROVIDER` (`anthropic` by default, or `mock`) and `ANTHROPIC_API_KEY`. All data are synthetic and simulation results are not forecasts.

## Dashboard (Streamlit)

A simple technical-demo dashboard with four pages. It talks **only to the FastAPI backend** and imports none of the engines: **Overview** (counts and recent incidents), **System Explorer** (profile, incidents, KRI charts, controls, dependencies and a shared-exposure map), **Scenario Lab** (estimated baseline model, baseline versus stress simulation with a loss distribution chart, optional advanced numeric assumptions) and **AI Investigator** (the agent's sectioned answer, tool activity log and simulation metadata). A banner on every page reminds the reader that the data are synthetic and the model is not calibrated.

```bash
# 1. Generate the synthetic data (once)
python -m risksignal.data.generator

# 2. Start the backend (terminal 1)
uvicorn risksignal.api.main:app --reload

# 3. Start the dashboard (terminal 2), then open http://localhost:8501
streamlit run src/risksignal/ui/app.py
```

- **Without an Anthropic key** the Overview, System Explorer and Scenario Lab work as normal. The AI Investigator shows a clear message that the live agent needs `ANTHROPIC_API_KEY`. For an offline demonstration of the whole dashboard, start the backend with the deterministic mock provider (`RISKSIGNAL_LLM_PROVIDER=mock`, PowerShell: `$env:RISKSIGNAL_LLM_PROVIDER="mock"`).
- **With a key**, put `ANTHROPIC_API_KEY=...` in `.env` (git-ignored) or the environment before starting the backend.
- If the backend runs somewhere else, set `RISKSIGNAL_API_URL` (default `http://127.0.0.1:8000`) before starting Streamlit.

The UI computes no risk figures: every number shown was returned by the API. See the notes on assumptions and limitations in the docs.

## Documentation

- [docs/project_brief.md](docs/project_brief.md): canonical project reference (scope, rules, exclusions).
- [docs/domain_model.md](docs/domain_model.md): Operational Risk concepts in plain language.
- [docs/agent_design.md](docs/agent_design.md): how the investigation agent works and its limits.
- [docs/agent_tools.md](docs/agent_tools.md): the deterministic tool layer the agent uses.
- [docs/dependency_graph.md](docs/dependency_graph.md): nodes, edges and shared-vendor reasoning.
- [docs/stochastic_model.md](docs/stochastic_model.md): the frequency-severity model and risk metrics.
- [docs/scenario_analysis.md](docs/scenario_analysis.md): stress scenarios and why their numbers need expert judgement.
- [docs/architecture.md](docs/architecture.md): layers and design rationale.
- [docs/limitations.md](docs/limitations.md): what this prototype is not.
- [docs/technical_review.md](docs/technical_review.md): internal technical review of the mathematics, architecture and agent (not an independent model validation), with remaining technical debt.
- [docs/institutional_validation.md](docs/institutional_validation.md): roadmap of what a real Operational Risk team would need to do to evaluate this prototype seriously (data, domain, modelling, validation, agent, security). Contains no results.
- [docs/research_extensions.md](docs/research_extensions.md): five research questions the prototype is built to make precise but does not answer (λ(t) from KRIs, tabular foundation models, dependency information, NLP signals, evidence-grounded agent). Contains no results.
- [docs/demo_script.md](docs/demo_script.md): a 13-minute live demonstration script built around `PAYMENT_ENGINE_01`, with reference values (checked by a test), caveats, likely technical questions with honest answers, and a troubleshooting table.
- [docs/deployment.md](docs/deployment.md): deploying the API on Render (Docker, mock provider) and the dashboard on Streamlit Community Cloud, with exact settings, post-deployment checks and a record of what was and was not verified.
