# RiskSignal

**An agentic Operational Risk investigation and stochastic scenario prototype (research prototype, synthetic data only).**

> **Development status: early version.**
> - **Done:** repository structure, domain documentation, the synthetic Atlas Bank dataset (generator, validation, CSV and SQLite storage), the stochastic frequency-severity engine, the stress scenario engine, the dependency graph, the deterministic tool layer, the analysis assistant (conversation and full investigations), the FastAPI backend, the Streamlit dashboard, and Docker setup for local demonstration.
> - **Not built:** everything in the [roadmap](#roadmap-what-this-early-version-does-not-do-yet), cloud deployment and anything listed as future research.
> - **Not yet exercised in development:** the live Anthropic model (no API key was available; the offline mock provider is fully tested) and the Docker images (no Docker engine was available; the build steps, health check and minimal UI environment were checked by emulating them with plain Python).

## Signal-led AI investigation

The dashboard opens **Risk Investigator**: select a system, scan up to three monitoring indicators, and click **Investigate system**. Read a short summary, at most three source-linked findings and three ordered next investigation questions. Evidence, review tools and quantitative details stay expandable. **Scenario Analysis** supports optional financial what-ifs.

The top navigation has four pages: **Introduction**, **Risk Investigator**, **Scenario Analysis** and **Way Forward**. Introduction (`/introduction`) covers current approaches, the need, goal and LLM idea. Way Forward (`/way-forward`) covers approved real bank data, regulatory/internal review, expert input, prediction validation and a supervised pilot on one real analyst task. The Database page remains removed; source evidence is available within Risk Investigator.

- Requires Streamlit 1.65 or newer, aligned with the existing Cloud pin and the accessible dataframe APIs used by the workbench. No new packages are needed.
- [Industry research and ranked requirements](docs/industry_research.md), with a [34-role evidence register](docs/research/job_evidence.csv). Source/date limitations are explicit; this is not 34 fully retrieved and dated AI operational-risk postings.
- [Application audit, gap analysis, implementation, testing and roadmap](docs/platform_upgrade.md).
- **Risk Investigator** replaces the separate Assistant and Risk workbench navigation entries. Monitoring and evidence review tools remain available in collapsed supporting sections. Monitoring itself needs no model API key.
- All workpapers remain drafts. Review dates do not prove control effectiveness; anomaly signals are not approved appetite breaches; synthetic holdout diagnostics are not predictive validation.
- Evidence/review notes are session-local until downloaded as JSON, not a persistent case-management audit trail.
- The final reduction and local validation record is in [docs/FINAL_SIMPLIFICATION_AND_AUDIT.md](docs/FINAL_SIMPLIFICATION_AND_AUDIT.md).

## Objective

RiskSignal explores how technology-related Operational Risk (outages, failed deployments, vendor failures, control failures) can be investigated by combining:

- a small synthetic dataset for a fictional institution, **Atlas Bank**,
- a dependency graph (systems, business processes, vendors, controls),
- a classical **frequency-severity** loss model with Monte Carlo simulation,
- an **AI analysis assistant** that answers an operator's questions, and runs full investigations, by calling deterministic Python tools.

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
- **Without an API key** everything works except the live Assistant, which explains that it needs `ANTHROPIC_API_KEY`. To try the Assistant offline with the deterministic mock provider:
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

To use the Assistant with a live model, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY=` before step 5, or start the API in offline mock mode (`RISKSIGNAL_LLM_PROVIDER=mock`, PowerShell: `$env:RISKSIGNAL_LLM_PROVIDER="mock"`). You can also try the agent without any server: `python -m risksignal.agent.investigator --mock "Investigate PAYMENT_ENGINE_01."`.

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

- All data are **synthetic**. Nothing here represents any real bank or financial institution.
- Model parameters are **illustrative**. There is **no claim of predictive validity**, no institution-specific calibration and no regulatory capital claim.
- The aim is to demonstrate architecture, agent orchestration, quantitative modelling mechanics, dependency analysis and scenario analysis.
- The AI agent is an investigation assistant. It makes no final risk decision.
- The elements deliberately left out (real loss data, calibration, tail modelling, validation, governance) are the work a real Operational Risk team would need to do.

See [docs/limitations.md](docs/limitations.md).

## The demo

1. Open **Risk Investigator** at `/`, with `PAYMENT_ENGINE_01` selected.
2. Notice the unusual failed-deployment indicator, then click **Investigate system**.
3. Read the summary and justified next investigations. Follow a source link and expand one incident, control or shared supplier.
4. Optionally run **Scenario Analysis** at `/scenario-lab`: compare annual losses under stated assumptions, not forecasts.
5. Close with the limits: synthetic records, a scripted offline provider unless a live LLM is configured, and an analyst who remains responsible for decisions.

Use the [presentation-day commands](docs/README_PRESENTATION.md) and [five-minute script](docs/demo_script.md).

## Roadmap: what this early version does not do yet

RiskSignal is deliberately an early version of an analysis assistant. It shows the approach end to end on synthetic data; turning it into an assistant an Operational Risk team could rely on is the next stage of work:

1. **Evaluation with a live model.** A set of real operator questions with expected evidence, to measure how often the assistant picks the right tools, how often every figure is grounded, and whether analysts find the answers useful.
2. **Institutional data.** Connectors to the incident, control and KRI systems of record instead of the synthetic Atlas Bank data, with data-quality checks.
3. **Saved cases and audit trail.** Conversations and investigations stored as case files that a reviewer can reopen, comment on and sign off.
4. **Wider analysis.** Trend tests, links between KRIs and later incidents, more stress scenarios, and search over policies, procedures and past reviews.
5. **Access control and approved hosting.** Authentication, entitlements by business area, and a language model hosted under the institution's approval.
6. **Analyst feedback.** Marking answers as useful or wrong, so that prompts and tools improve on real use.

The **Way Forward** page presents these next steps without claiming they are already achieved. See [institutional validation](docs/institutional_validation.md).

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

Atlas Bank is fictional. No real institution's data were used, and operational loss data are institution-specific. The dataset exists only to exercise the architecture and workflow.

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

The AI agent does not query the database or calculate anything itself. Its ten deterministic, read-only investigation tools include the original `get_system_profile`, `get_recent_incidents`, `get_kri_history`, `get_controls`, `get_dependencies`, `run_loss_simulation` and `compare_baseline_and_stress`, plus `get_kri_monitoring`, `get_model_diagnostics` and `get_risk_workpaper`. Each returns a structured Pydantic result labelled as observed synthetic data, modelled output or a mixed-evidence workpaper, or a typed `ToolError` (tools never raise). Simulation results separate the observed basis, the model assumptions and the simulated outputs.

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

The conversational assistant (below) also has four read-only bank-wide tools: `list_systems`, `get_portfolio_summary` (every system side by side over a window: incidents, high or critical incidents, recorded loss, change on the previous window and overdue control reviews), `get_bank_overview` and `list_scenarios`.

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

### Conversational assistant

The assistant lets an operator ask free questions over several turns: about one system ("What incidents did CORE_LEDGER_01 have?", "And its controls?"), about the whole portfolio ("Which systems should I look at first?") or about the methods ("What is Expected Shortfall?"). It is the same agent loop with a conversational prompt ([prompts.py](src/risksignal/agent/prompts.py)) that shares the investigation's ground rules: tools only, no invented facts, no calculations of its own, no risk verdicts. It adapts the length and shape of each answer to the question, remembers the conversation (the caller sends earlier turns with each message, so the API stays stateless), and every answer comes with its tool activity and the same check on numbers. Answers replace long dashes and semicolons with ordinary prose punctuation. In offline mode a deterministic stand-in ([mock_assistant.py](src/risksignal/agent/mock_assistant.py)) recognises the common question types and writes answers only from tool results. The conversational API and unfinished UI component remain available in the codebase, but the preview is not displayed in the presentation.

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
| `GET /systems/{system_id}/monitoring` | Past-only KRI review signals, data status and walk-forward flag workload. |
| `GET /systems/{system_id}/model-diagnostics` | Training-only fit and synthetic temporal holdout diagnostics. |
| `GET /systems/{system_id}/workpaper` | Source-linked draft RCSA evidence, questions and content fingerprint. |
| `POST /simulations` | Baseline Monte Carlo loss simulation (`system_id`, `number_of_simulations`, `random_seed`). |
| `GET /scenarios` | The predefined illustrative scenarios and their assumptions. |
| `POST /scenarios/compare` | Baseline versus a predefined illustrative stress scenario (`scenario_id`, e.g. `SHARED_VENDOR_OUTAGE`). |
| `POST /scenarios/compare-custom` | Baseline versus stress numbers supplied by a person (`lambda_multiplier`, `severity_mu_shift`, `severity_sigma_multiplier`). Not available to the AI agent. |
| `POST /agent/investigate` | Ask the agent (`question`, optional `include_tool_outputs`). Returns the answer, a tool activity log and warnings. |
| `POST /agent/chat` | Send one message to the conversational assistant (`message`, `history` of earlier `{role, content}` turns, optional `include_tool_outputs`). Same response shape; the reply is in `final_response`. |

```bash
curl http://127.0.0.1:8000/systems/PAYMENT_ENGINE_01/incidents
curl -X POST http://127.0.0.1:8000/simulations -H "Content-Type: application/json" \
     -d '{"system_id": "PAYMENT_ENGINE_01", "number_of_simulations": 100000, "random_seed": 42}'
curl -X POST http://127.0.0.1:8000/agent/investigate -H "Content-Type: application/json" \
     -d '{"question": "Investigate PAYMENT_ENGINE_01."}'
```

Errors use one JSON shape, `{"error": {"type", "message", "suggestions"}}`, and never include stack traces: `404` unknown system or scenario (with suggestions), `422` invalid parameters (for example `months` outside 1 to 120, or fewer than 1,000 simulations), `503` database or language model unavailable, `500` unexpected failure (generic message). Settings come from environment variables: `RISKSIGNAL_DB_PATH`, `RISKSIGNAL_LLM_PROVIDER` (`anthropic` by default, or `mock`) and `ANTHROPIC_API_KEY`. All data are synthetic and simulation results are not forecasts.

## Dashboard (Streamlit)

A focused analyst workspace with four navigation destinations. It talks **only to the FastAPI backend** and imports none of the engines:

- **Risk Investigator** (default), a three-indicator snapshot, prominent investigation action, concise findings and ordered follow-up questions. System profiles, incidents, one selected KRI chart, controls, direct/indirect dependencies, tool activity, RCSA questions, diagnostics and review/export are supporting disclosures.
- **Scenario Analysis**, optional baseline/stress comparisons. Three headline metrics, with distributions, assumptions and all other metrics expandable. No simulation runs just by opening a page.
- **Introduction**, current approaches, need, goal and idea, available without database access.
- **Way Forward**, practical steps for approved data, expert/regulatory review, real-task LLM evaluation and out-of-sample loss-model assessment.

Losses use **synthetic monetary units**, not a specified real currency. The UI explains lowercase **λ** as the annual incident rate, **μ** as the mean of log-losses and **σ** as the standard deviation of log-losses. Custom multipliers change λ or σ, not every loss by that percentage.

Displayed prose replaces long dashes and semicolons, including a display-only copy of evidence text. Raw API tool outputs, stored records, numeric results, identifiers, SQL, CSS and URLs remain unchanged. Synthetic-data and conditional-model notices remain visible without a large promotional banner.

```bash
# 1. Generate the synthetic data (once)
python -m risksignal.data.generator

# 2. Start the backend (terminal 1)
uvicorn risksignal.api.main:app --reload

# 3. Start the dashboard (terminal 2), then open http://localhost:8501
streamlit run src/risksignal/ui/app.py
```

 The Assistant shows a clear message that the live agent needs `ANTHROPIC_API_KEY`. For an offline demonstration of the whole dashboard, start the backend with the deterministic mock provider (`RISKSIGNAL_LLM_PROVIDER=mock`, PowerShell: `$env:RISKSIGNAL_LLM_PROVIDER="mock"`).
- **With a key**, put `ANTHROPIC_API_KEY=...` in `.env` (git-ignored) or the environment before starting the backend.
- **Without a key**, Scenario Analysis and supporting monitoring evidence work normally. Set `RISKSIGNAL_LLM_PROVIDER=mock` for scripted offline investigations and drafts, or configure a live provider for genuine LLM tool calling.
- If the backend runs somewhere else, set `RISKSIGNAL_API_URL` (default `http://127.0.0.1:8000`) before starting Streamlit.

The UI computes no risk figures: every number shown was returned by the API. See the notes on assumptions and limitations in the docs.

**Visual design.** Independent Inter sans-serif typography, with Segoe UI/Arial fallbacks, replaces the old serif/institutional presentation. White and soft grey surfaces, navy `#183153`, blue `#2864A0`, dark text `#172B45` and subtle borders `#DFE5EC` provide hierarchy without decorative cards. Inter is open-licensed; no proprietary brand assets are used. Font downloads are optional for readability. Local theme tokens and Plotly styling live in [src/risksignal/ui/theme.py](src/risksignal/ui/theme.py), with base settings in [.streamlit/config.toml](.streamlit/config.toml). The local configuration is the presentation target; historical Docker/deployment material is not a readiness claim.

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
- [docs/demo_script.md](docs/demo_script.md): the investigator-first five-minute route, with an optional technical walkthrough, tested reference values and honest Q&A.
- [docs/FINAL_SIMPLIFICATION_AND_AUDIT.md](docs/FINAL_SIMPLIFICATION_AND_AUDIT.md): feature reductions, local checks, mathematical checks and remaining limitations.
- [docs/deployment.md](docs/deployment.md): deploying the API on Render (Docker, mock provider) and the dashboard on Streamlit Community Cloud, with exact settings, post-deployment checks and a record of what was and was not verified.

## Presentation Questions and Answers

This bank is grounded in the implementation and documentation in this repository. The short answer is a presentation-ready version; the technical answer is for follow-up. “Careful” marks the boundary that should not be crossed in a claim. All file links below are repository-relative.

### CATEGORY 1: PROJECT PURPOSE AND POSITIONING

**Q1. Why did you build RiskSignal?**

- **Presentation answer:** To demonstrate how an Operational Risk analyst could bring system, incident, KRI, control, dependency and quantitative evidence into one investigation workflow.
- **Technical detail:** The prototype joins synthetic records and a dependency graph to a compound frequency-severity simulation and a tool-calling agent.
- **Caution:** It is a research prototype, not a product proven to improve bank decisions.
- **Project evidence:** [project brief](docs/project_brief.md), [architecture](docs/architecture.md).

**Q2. What problem are you trying to solve?**

- **Presentation answer:** Relevant evidence is often split across inventories, incident systems, controls, KRIs and vendor maps; an analyst must assemble it and trace connections.
- **Technical detail:** RiskSignal demonstrates a read-only, structured workflow that gathers that evidence for one selected technology system.
- **Caution:** The repository demonstrates the workflow on one small fictional dataset; it does not establish that this is how any specific bank currently works.
- **Project evidence:** [domain model](docs/domain_model.md), [agent tools](docs/agent_tools.md).

**Q3. What is genuinely new if banks already have simulators and risk tools?**

- **Presentation answer:** The contribution is the combination and orchestration pattern, not a new loss model: an agent selects deterministic evidence tools and leaves a trace.
- **Technical detail:** Separate model, graph, tools, agent, API and UI layers let the model organise questions while Python functions retrieve and calculate.
- **Caution:** Do not claim novelty over commercial or internal tools without a comparison; this is a prototype demonstration.
- **Project evidence:** [architecture](docs/architecture.md), [agent design](docs/agent_design.md).

**Q4. Why is the agent the main added value?**

- **Presentation answer:** It can choose which evidence to gather for a question and turn the results into a reviewable summary; it does not replace the calculations.
- **Technical detail:** The investigator chooses among ten typed, read-only tools and returns the answer with tool activity, outputs and warnings.
- **Caution:** Tool selection and wording still depend on the LLM; the number-grounding check is best-effort, not a correctness proof.
- **Project evidence:** [investigator](src/risksignal/agent/investigator.py), [agent design](docs/agent_design.md).

**Q5. Why use synthetic data?**

- **Presentation answer:** It allows a safe, reproducible public demonstration without using confidential bank records.
- **Technical detail:** Seeded data exercise the schema, graph, tools, simulation, API and UI; they are not evidence about real loss behaviour.
- **Caution:** The generator deliberately constructs parts of the focal system’s story, so findings are properties of the generated scenario.
- **Project evidence:** [data generator](src/risksignal/data/generator.py), [limitations](docs/limitations.md).

**Q6. Why did you not train a predictive model on the synthetic data?**

- **Presentation answer:** There is no meaningful predictive target or planted KRI-to-future-loss signal to learn.
- **Technical detail:** The generator explicitly has no hidden future-probability label; KRIs are generated independently of the incident table. Predictive results would mostly measure artifacts of the generator.
- **Caution:** A model can technically be fit, but that would not make its results valid or informative for a bank.
- **Project evidence:** [data generator](src/risksignal/data/generator.py), [research extensions](docs/research_extensions.md).

**Q7. Why is this not a bank risk model?**

- **Presentation answer:** It contains no real bank data, taxonomy, model, process or validated parameters. “Atlas Bank” is fictional.
- **Technical detail:** Its estimates come from generated incidents, and its scenario adjustments are illustrative assumptions.
- **Caution:** Do not imply endorsement, representativeness or any relationship to a real institution's internal risk processes.
- **Project evidence:** [limitations](docs/limitations.md), [agent prompt](src/risksignal/agent/prompts.py).

**Q8. What would you need from an institution to make it useful?**

- **Presentation answer:** Agreed intended use, trustworthy point-in-time incident and loss data, KRIs, controls, system/vendor dependencies, taxonomy and analyst participation.
- **Technical detail:** Then reproduce a transparent baseline, compare alternatives using time-ordered validation, test the agent with real analyst tasks, and complete governance and security reviews.
- **Caution:** Access to data alone is not sufficient; definitions, quality, permissions and intended-use governance come first.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md).

**Q9. What would you say this project is, and is not?**

- **Presentation answer:** It is a working research prototype for evidence gathering and illustrative scenario analysis; it is not predictive, validated, production-secure or regulatory capital software.
- **Technical detail:** The code and mathematics have been technically reviewed, but that review explicitly is not independent model validation.
- **Caution:** “Tested code” must not be shortened to “validated model.”
- **Project evidence:** [limitations](docs/limitations.md), [technical review](docs/technical_review.md).

### CATEGORY 2: OPERATIONAL RISK

**Q1. What is Operational Risk?**

- **Presentation answer:** Under the Basel definition cited in the project, it is the risk of loss from inadequate or failed processes, people and systems, or external events.
- **Technical detail:** The prototype focuses on technology-related events such as outages, failed deployments, vendor failures and control failures.
- **Caution:** Do not present this technology-focused scope as a complete Operational Risk taxonomy.
- **Project evidence:** [domain model](docs/domain_model.md).

**Q2. What is an incident?**

- **Presentation answer:** An event that happened and had an operational effect, for example a system outage or a failed release.
- **Technical detail:** In the dataset, an incident has a date, affected system, category, description, financial loss and severity label.
- **Caution:** A recorded incident is not automatically equivalent to a loss event under a particular bank’s policy; definitions need alignment.
- **Project evidence:** [domain model](docs/domain_model.md), [data schemas](src/risksignal/data/schemas.py).

**Q3. What is a near miss?**

- **Presentation answer:** An event that could have caused harm but did not, perhaps because it was caught in time.
- **Technical detail:** It may be a useful leading signal, but the frequency-severity model fits recorded incident counts and positive losses; it does not model near misses as a separate event class.
- **Caution:** Do not count a near miss as a realised loss in this model.
- **Project evidence:** [domain model](docs/domain_model.md), [limitations](docs/limitations.md).

**Q4. What is a control?**

- **Presentation answer:** A safeguard intended to prevent an event or reduce its impact.
- **Technical detail:** RiskSignal records controls and review status, such as current, due or overdue, as investigation evidence. It does not translate control effectiveness into a change in λ or severity.
- **Caution:** An overdue review is a prompt to investigate, not proof that a control failed.
- **Project evidence:** [domain model](docs/domain_model.md), [control tools](src/risksignal/tools/control_tools.py).

**Q5. What is a KRI?**

- **Presentation answer:** A Key Risk Indicator is a metric used to monitor a condition that may be relevant to risk.
- **Technical detail:** RiskSignal displays monthly KRI histories and summary comparisons; it does not use them in the loss model or predict incidents from them.
- **Caution:** A KRI is not automatically a leading indicator; its definition, lag and relationship to outcomes must be tested.
- **Project evidence:** [domain model](docs/domain_model.md), [KRI tools](src/risksignal/tools/kri_tools.py).

**Q6. What is the difference between a KRI and an incident?**

- **Presentation answer:** An incident records an event that occurred; a KRI is a measurement that can help an analyst monitor conditions.
- **Technical detail:** In this prototype, incident counts and losses estimate the illustrative model, while KRI observations are displayed separately as evidence.
- **Caution:** Do not say the KRI predicts the incident in this implementation.
- **Project evidence:** [KRI tools](src/risksignal/tools/kri_tools.py), [simulation](src/risksignal/stochastic/simulation.py).

**Q7. Why do dependencies and vendors matter?**

- **Presentation answer:** A process depends on systems, and systems may depend on other systems or vendors; a shared dependency can expose multiple services to a common disruption.
- **Technical detail:** A directed NetworkX graph supports queries for related systems, shared vendors, upstream/downstream systems and processes.
- **Caution:** The graph indicates structural exposure, not causal propagation or a probability of joint failure.
- **Project evidence:** [graph builder](src/risksignal/graph/builder.py), [dependency graph](docs/dependency_graph.md).

**Q8. What is concentration risk in this context?**

- **Presentation answer:** Several important systems may rely on the same vendor or service, so one disruption could matter to more than one business process.
- **Technical detail:** RiskSignal identifies shared vendors in graph queries; its loss simulation is system-by-system and does not model joint vendor-driven losses.
- **Caution:** A shared vendor is a reason to investigate concentration, not evidence that systems fail together.
- **Project evidence:** [graph queries](src/risksignal/graph/queries.py), [limitations](docs/limitations.md).

### CATEGORY 3: MATHEMATICS

**Q1. Why did you choose a Poisson distribution?**

- **Presentation answer:** It is a transparent baseline for an incident count over a fixed period, with one interpretable rate parameter.
- **Technical detail:** Under the model, annual count N is Poisson(λ), with mean and variance both λ.
- **Caution:** It is a demonstration choice, not a conclusion that operational incidents meet Poisson assumptions.
- **Project evidence:** [frequency model](src/risksignal/stochastic/frequency.py), [stochastic model](docs/stochastic_model.md).

**Q2. What does λ mean?**

- **Presentation answer:** λ is the modelled average incident count per system-year.
- **Technical detail:** It is the expected value of the annual Poisson count; it is not the probability of an incident and not a time-varying risk score.
- **Caution:** Say “under the model assumptions,” not “the system will have λ incidents.”
- **Project evidence:** [frequency model](src/risksignal/stochastic/frequency.py).

**Q3. How is λ estimated?**

- **Presentation answer:** Count incidents in the observation window and divide by the number of years.
- **Technical detail:** The MLE is n/T. The implementation counts both date endpoints, uses days/365.25, uses system history at five or more events, and otherwise falls back to the bank-wide per-system average; an optional user override is labelled.
- **Caution:** The five-event threshold is illustrative, not evidence of estimate stability.
- **Project evidence:** [frequency model](src/risksignal/stochastic/frequency.py), [simulation](src/risksignal/stochastic/simulation.py).

**Q4. What assumptions does Poisson make?**

- **Presentation answer:** A constant average rate and independent event arrivals over the modelled interval.
- **Technical detail:** The count variance equals its mean; a stationary Poisson model also assumes the rate is not changing over that interval.
- **Caution:** Real operational incidents may cluster, change with exposure or share causes, violating these assumptions.
- **Project evidence:** [frequency model](src/risksignal/stochastic/frequency.py), [limitations](docs/limitations.md).

**Q5. What if variance is larger than the mean?**

- **Presentation answer:** That is over-dispersion relative to a Poisson count and signals the baseline may not capture the observed variability.
- **Technical detail:** Diagnose it using counts at a meaningful system/time granularity, while checking trend, seasonality, exposure and heterogeneity; those can also create apparent over-dispersion.
- **Caution:** The prototype does not perform this diagnosis or adjust λ for it.
- **Project evidence:** [limitations](docs/limitations.md), [research extensions](docs/research_extensions.md).

**Q6. Why might Negative Binomial be better?**

- **Presentation answer:** It can represent count variance greater than the mean, often by allowing the rate to vary across observations.
- **Technical detail:** It is a candidate extension to test against Poisson on time-ordered real data with uncertainty and suitable baselines.
- **Caution:** It is not implemented here and is not automatically superior; added flexibility can overfit sparse data.
- **Project evidence:** [research extensions](docs/research_extensions.md), [limitations](docs/limitations.md).

**Q7. Why a Lognormal distribution for severity?**

- **Presentation answer:** Losses are non-negative and often right-skewed, and Lognormal is a simple, transparent illustrative distribution.
- **Technical detail:** The project estimates it by maximum likelihood in log space, using the most specific source with at least 15 positive losses (system, requested category, then bank-wide), and simulates independent severities conditional on the count.

- **Caution:** The generator itself draws losses from Lognormal distributions, so its fit to this data is circular evidence.

- **Project evidence:** [severity model](src/risksignal/stochastic/severity.py), [data generator](src/risksignal/data/generator.py).

**Q8. What are μ and σ?**

- **Presentation answer:** They are the mean and standard deviation of log loss, not of loss in dollars.
- **Technical detail:** If ln(X) is Normal(μ, σ²), the median loss is exp(μ), and the mean is exp(μ + σ²/2). A larger σ spreads more mass into the right tail.
- **Caution:** Avoid describing μ as average loss or σ as dollar volatility.
- **Project evidence:** [severity model](src/risksignal/stochastic/severity.py).

**Q9. What is a heavy tail?**

- **Presentation answer:** It means very large losses remain more plausible than they would under a thin-tailed distribution.
- **Technical detail:** Tail choice strongly affects P99 and Expected Shortfall; high-severity estimates are especially sensitive to σ and sparse observations.
- **Caution:** “Heavy tail” is comparative, not a claim that a particular model captures the true bank-loss tail.
- **Project evidence:** [stochastic model](docs/stochastic_model.md), [technical review](docs/technical_review.md).

**Q10. Why might Lognormal be insufficient?**

- **Presentation answer:** Real losses may have different tail behaviour, reporting thresholds, multiple populations, dependence or changing conditions.
- **Technical detail:** Compare candidate severity distributions and tail diagnostics out of sample; account for truncation, parameter uncertainty and sample size.
- **Caution:** The synthetic losses were generated as Lognormal, so this repository cannot tell us which alternative is right for a bank.
- **Project evidence:** [limitations](docs/limitations.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q11. When would EVT or Generalized Pareto be relevant?**

- **Presentation answer:** When the question is specifically about rare, extreme losses and there is enough suitable tail data to estimate beyond a threshold.
- **Technical detail:** A peaks-over-threshold Generalized Pareto approach could model exceedances, but threshold selection, uncertainty and sparse-tail validation are central.
- **Caution:** EVT/GPD is not implemented; a few synthetic extremes do not justify a tail model.
- **Project evidence:** [research extensions](docs/research_extensions.md), [limitations](docs/limitations.md).

**Q12. What is Monte Carlo simulation?**

- **Presentation answer:** Repeatedly generate possible years under stated assumptions and summarize their annual losses.
- **Technical detail:** Each year draws a Poisson count and then that many Lognormal severities; the losses are summed and metrics computed from the resulting sample.
- **Caution:** It samples the assumed model; it does not make the assumptions true.
- **Project evidence:** [simulation engine](src/risksignal/stochastic/simulation.py).

**Q13. Why Monte Carlo rather than one expected-loss value?**

- **Presentation answer:** One mean cannot show the spread or tail of possible outcomes; simulation gives percentile and tail summaries as well.
- **Technical detail:** The compound aggregate distribution is summarized numerically; the engine also reports the closed-form mean λ·exp(μ+σ²/2) as a check.
- **Caution:** More distributional detail does not imply more empirical certainty.
- **Project evidence:** [simulation engine](src/risksignal/stochastic/simulation.py), [metrics](src/risksignal/stochastic/metrics.py).

**Q14. Why 100,000 simulations?**

- **Presentation answer:** It gives a useful computationally inexpensive demonstration sample, including roughly 1,000 draws in the worst 1% tail.
- **Technical detail:** It is the default, not a statistical guarantee. P99 and ES99 remain Monte Carlo estimates; documented seed-to-seed noise is larger for tail metrics than for the mean.
- **Caution:** More simulations reduce sampling noise, not model error, data error or parameter uncertainty.
- **Project evidence:** [simulation engine](src/risksignal/stochastic/simulation.py), [technical review](docs/technical_review.md).

**Q15. What are P95 and P99?**

- **Presentation answer:** They are simulated annual-loss thresholds exceeded in about 5% and 1% of modelled years, respectively.
- **Technical detail:** They are empirical quantiles of the simulated annual aggregate losses, computed with NumPy’s inverted-CDF quantile convention.
- **Caution:** They are conditional on this model and are not forecasts, capital requirements or probabilities of a named event.
- **Project evidence:** [metrics](src/risksignal/stochastic/metrics.py).

**Q16. What is Expected Shortfall?**

- **Presentation answer:** It is the average loss in the worst fraction of simulated years beyond the selected percentile.
- **Technical detail:** ES95 averages the worst 5% and ES99 the worst 1%, using a fractional boundary weight where needed.
- **Caution:** It is still an estimate under illustrative assumptions, not an institution’s validated tail exposure.
- **Project evidence:** [metrics](src/risksignal/stochastic/metrics.py).

**Q17. How is Expected Shortfall different from P95?**

- **Presentation answer:** P95 is the threshold for the worst 5%; ES95 is the average loss within that worst 5%.
- **Technical detail:** P95 is a quantile; ES95 aggregates tail severity and, under the implemented estimator, is at least P95.
- **Caution:** A higher ES does not mean there is a higher probability of crossing P95.
- **Project evidence:** [metrics](src/risksignal/stochastic/metrics.py).

**Q18. What is the difference between a simulation and a forecast?**

- **Presentation answer:** A simulation shows outcomes generated under explicit assumptions; a forecast claims relevance to future observations. This prototype only does the former.
- **Technical detail:** Parameters are estimated in sample from synthetic history and are treated as fixed; there is no prospective or out-of-sample validation.
- **Caution:** Always call results “simulated outcomes under assumptions,” not predictions.
- **Project evidence:** [limitations](docs/limitations.md), [stochastic model](docs/stochastic_model.md).

**Q19. How would you introduce dynamic λ(t)?**

- **Presentation answer:** Replace a constant incident rate with a rate that changes by time and system, then test whether that improves a defined early-warning task.
- **Technical detail:** The research roadmap proposes a system-period count model with exposure and log λ(s,t)=system effect + function of lagged signals, compared with constant-rate and simple baselines.
- **Caution:** No λ(t) model exists in the code; first agree the target and available point-in-time data.
- **Project evidence:** [research extensions](docs/research_extensions.md).

**Q20. Could KRIs estimate λ(t)?**

- **Presentation answer:** Possibly, but this is an open research question, not a current capability.
- **Technical detail:** A lagged KRI could be tested as a predictor of future incident counts using rolling-origin evaluation, proper scoring rules, calibration and leakage controls.
- **Caution:** Current synthetic KRIs are independent of the incidents and are not used in λ estimation.
- **Project evidence:** [KRI tools](src/risksignal/tools/kri_tools.py), [research extensions](docs/research_extensions.md).

**Q21. What about Hawkes processes?**

- **Presentation answer:** A Hawkes process models events whose occurrence can temporarily increase the rate of further events. This is useful to investigate clustering hypotheses.
- **Technical detail:** It would require reliable timestamps and a defensible event-excitation structure, then comparison against simpler count models.
- **Caution:** Hawkes is a documented future research idea, not part of the implementation or a conclusion from the synthetic data.
- **Project evidence:** [research extensions](docs/research_extensions.md), [limitations](docs/limitations.md).

**Q22. What about dependence between operational risks?**

- **Presentation answer:** It matters: common vendors or shared platforms can create correlated outcomes, but the current baseline assumes independence.
- **Technical detail:** Frequency and severity are independent in the compound model, and system simulations are separate; the vendor stress does not simulate joint system losses.
- **Caution:** A graph edge shows a dependency record, not a calibrated dependence parameter or causal effect.
- **Project evidence:** [limitations](docs/limitations.md), [scenario engine](src/risksignal/stochastic/scenario.py).

### CATEGORY 4: AGENT AND AI

**Q1. Why use an agent rather than a normal chatbot?**

- **Presentation answer:** The agent can choose which deterministic evidence tools to call before it writes, instead of answering only from general model knowledge.
- **Technical detail:** Its access is limited to a typed registry; each call is logged with inputs, status and output.
- **Caution:** It is still an LLM-based workflow and can misstate or omit evidence; human review remains necessary.
- **Project evidence:** [agent design](docs/agent_design.md), [tool registry](src/risksignal/agent/tool_registry.py).

**Q2. What makes the system agentic?**

- **Presentation answer:** It receives a task, chooses tools, observes their results and can continue until it produces a response.
- **Technical detail:** A bounded investigator loop runs up to ten model turns; tool execution goes through a registry, not arbitrary code.
- **Caution:** It is a deliberately simple tool-calling loop, not an autonomous risk decision-maker.
- **Project evidence:** [investigator](src/risksignal/agent/investigator.py), [agent design](docs/agent_design.md).

**Q3. What tools can the agent call?**

- **Presentation answer:** System profile, recent incidents, KRI history, controls, dependencies, baseline loss simulation and predefined baseline-versus-stress comparison.
- **Technical detail:** Seven read-only functions are registered; custom numeric stress assumptions are deliberately not exposed to the agent.
- **Caution:** Do not imply the agent can query arbitrary databases, browse systems or write records.
- **Project evidence:** [tool registry](src/risksignal/agent/tool_registry.py), [agent tools](docs/agent_tools.md).

**Q4. Why can’t the LLM calculate risk metrics?**

- **Presentation answer:** A language model is not a reproducible numerical engine; Python provides the calculations that can be tested and replayed.
- **Technical detail:** The prompt instructs it not to calculate; deterministic tools produce the simulation metrics and the agent flags unmatched numbers as a best-effort check.
- **Caution:** The code does not guarantee every sentence is correct or that every hallucinated number will be caught.
- **Project evidence:** [agent prompt](src/risksignal/agent/prompts.py), [number check](src/risksignal/agent/investigator.py).

**Q5. How do you reduce hallucination risk?**

- **Presentation answer:** Restrict data access to read-only tools, require evidence-backed summaries, log tool activity and check numeric claims against returned values.
- **Technical detail:** The prompt and registry validate tool names and arguments; unmatched numbers create warnings.
- **Caution:** This is risk reduction, not hallucination elimination or a guarantee of factual grounding.
- **Project evidence:** [tool registry](src/risksignal/agent/tool_registry.py), [agent design](docs/agent_design.md).

**Q6. What is the purpose of the mock provider?**

- **Presentation answer:** It lets tests and offline demos exercise the workflow without an API key or network call.
- **Technical detail:** It deterministically replays scripted tool requests and forms its final response from the tool outputs.
- **Caution:** It is a script, not an LLM; do not present its output as a live AI result.
- **Project evidence:** [mock provider](src/risksignal/agent/mock_provider.py), [demo script](docs/demo_script.md).

**Q7. Why not use a live Anthropic model in the public demo?**

- **Presentation answer:** The documented public deployment uses synthetic data and the deterministic mock; it avoids sending demo interactions to a live external model.
- **Technical detail:** The live provider exists behind a replaceable interface, but the deployment guide intentionally configures `RISKSIGNAL_LLM_PROVIDER=mock`.
- **Caution:** The live Anthropic path was not exercised in development according to the project status; do not claim it was production-tested.
- **Project evidence:** [deployment](docs/deployment.md), [limitations](docs/limitations.md).

**Q8. Could this use an institution’s approved internal model?**

- **Presentation answer:** The provider interface is designed to be replaceable, so an approved model could be explored without changing the risk engine.
- **Technical detail:** It would require an institution-approved provider implementation, environment, controls, evaluation and integration; none is supplied here.
- **Caution:** “Replaceable by design” does not mean an internal model is already integrated or approved.
- **Project evidence:** [provider interface](src/risksignal/agent/base.py), [agent design](docs/agent_design.md).

**Q9. How would you move from suggested questions to evidence-backed proposed answers?**

- **Presentation answer:** Add authorised evidence sources and retrieval, require source citations for each claim, then evaluate answers against analyst-reviewed cases.
- **Technical detail:** Preserve source identifiers, timestamps and provenance in tool results; distinguish retrieved facts, inference and recommendation, with abstention on missing evidence.
- **Caution:** The current agent suggests questions; it does not resolve them or provide evidence-backed remediation recommendations.
- **Project evidence:** [agent design](docs/agent_design.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q10. Would you fine-tune the model?**

- **Presentation answer:** Not as the first step. I would first measure the actual failure modes and test retrieval, prompt and tool improvements.
- **Technical detail:** Fine-tuning needs representative, governed examples and a stable evaluation set; it does not itself provide current facts or provenance.
- **Caution:** No fine-tuning has been done or is required by this prototype.
- **Project evidence:** [research extensions](docs/research_extensions.md), [agent design](docs/agent_design.md).

**Q11. Why might retrieval be better than immediate fine-tuning?**

- **Presentation answer:** Historical investigation knowledge changes, and retrieval can surface a relevant case with its source instead of baking it into model weights.
- **Technical detail:** A governed, permission-aware case index could be evaluated for retrieval relevance and answer traceability before considering tuning.
- **Caution:** Historical-case retrieval is not implemented, and stale or biased cases can mislead just as stale training data can.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q12. What is RAG?**

- **Presentation answer:** Retrieval-Augmented Generation retrieves relevant material and supplies it to a language model as context for its response.
- **Technical detail:** A production design would need access controls, provenance, freshness, relevance testing and a clear abstention strategy.
- **Caution:** RiskSignal currently has no document retrieval or vector store.
- **Project evidence:** [architecture](docs/architecture.md), [agent design](docs/agent_design.md).

**Q13. What is GraphRAG?**

- **Presentation answer:** GraphRAG combines graph-structured relationships with retrieval to find connected entities and supporting information.
- **Technical detail:** RiskSignal has a NetworkX dependency graph, but no GraphRAG pipeline, document retrieval, graph embeddings or graph-grounded generation.
- **Caution:** Do not equate graph queries with GraphRAG.
- **Project evidence:** [graph queries](src/risksignal/graph/queries.py), [architecture](docs/architecture.md).

**Q14. What is SCAIR?**

- **Presentation answer:** SCAIR is not defined or used anywhere in this repository, so I would not attribute a particular expansion or capability to RiskSignal.
- **Technical detail:** If the reviewer means a specific institutional method or paper, I would first confirm its full name and intended meaning, then assess it separately.
- **Caution:** Do not invent an acronym expansion or imply implementation.
- **Project evidence:** [project brief](docs/project_brief.md), [research extensions](docs/research_extensions.md).

**Q15. What is a Tabular Foundation Model?**

- **Presentation answer:** It is a pretrained model intended to make predictions on tabular data, potentially useful when a new dataset is small.
- **Technical detail:** The research document mentions TabPFN as a candidate to compare with tuned statistical and gradient-boosting baselines on identical splits and metrics.
- **Caution:** No TFM is used here, and it is an empirical question whether one helps this domain.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q16. How could TFM or TabPFN fit into future work?**

- **Presentation answer:** As a challenger for an explicitly defined early-warning task, not as an assumed upgrade.
- **Technical detail:** Compare it with Poisson/logistic and XGBoost using the same point-in-time features, time splits, tuning budget, metrics and uncertainty analysis.
- **Caution:** Sparse, heterogeneous Operational Risk data can make flexible methods overfit; synthetic data cannot establish performance.
- **Project evidence:** [research extensions](docs/research_extensions.md).

**Q17. How would you evaluate whether the agent is useful?**

- **Presentation answer:** Give analysts representative tasks and test whether the agent saves time without reducing evidence quality or oversight.
- **Technical detail:** Use a controlled comparison with existing workflow; score completeness, correctness, traceability, tool choices, review effort and analyst time.
- **Caution:** A fluent answer or positive user feedback alone is not proof of operational value.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md), [research extensions](docs/research_extensions.md).

**Q18. How measure hallucination, tool selection, traceability and time saved?**

- **Presentation answer:** Use adjudicated tasks, explicit rubrics, complete tool traces and timed analyst studies.
- **Technical detail:** Measure unsupported-claim rate, correct/necessary tool-call precision and recall, claim-to-source coverage, task completion time and correction/review burden; report uncertainty and task difficulty.
- **Caution:** The current numeric warning is not a general hallucination-rate metric, and the repository reports no such evaluation results.
- **Project evidence:** [investigator](src/risksignal/agent/investigator.py), [research extensions](docs/research_extensions.md).

### CATEGORY 5: SOFTWARE ARCHITECTURE

**Q1. Why FastAPI?**

- **Presentation answer:** It exposes the existing tools and agent through a typed HTTP API without putting model calculations in the web layer.
- **Technical detail:** Routes validate request/response schemas and delegate to the relevant tool, simulation or investigator function.
- **Caution:** FastAPI is an implementation choice, not a claim of production readiness.
- **Project evidence:** [API main](src/risksignal/api/main.py), [API routes](src/risksignal/api/).

**Q2. Why Streamlit?**

- **Presentation answer:** It provides a quick, readable demonstration dashboard while keeping presentation separate from the risk logic.
- **Technical detail:** The UI calls the FastAPI backend through an HTTP client and renders returned values; it imports no simulation engine.
- **Caution:** It is a demo interface, not a bank-grade authenticated analyst application.
- **Project evidence:** [Streamlit app](src/risksignal/ui/app.py), [API client](src/risksignal/ui/api_client.py).

**Q3. Why SQLite?**

- **Presentation answer:** It keeps this small, reproducible prototype easy to run with one local database file and no separate database server.
- **Technical detail:** The generated CSVs are loaded into SQLite, which is the application’s primary data source.
- **Caution:** Production persistence, concurrent workloads, access control, audit and backup requirements need a deliberate institutional design.
- **Project evidence:** [data storage](src/risksignal/data/storage.py), [architecture](docs/architecture.md).

**Q4. Why NetworkX?**

- **Presentation answer:** It is a simple in-process way to represent and query the prototype’s system, process, control and vendor relationships.
- **Technical detail:** The graph is built from SQLite records and used for dependency and shared-vendor queries.
- **Caution:** Its graph is only as accurate as the source relationships, which are synthetic here.
- **Project evidence:** [graph builder](src/risksignal/graph/builder.py), [graph queries](src/risksignal/graph/queries.py).

**Q5. Why not Neo4j?**

- **Presentation answer:** The dataset is small and the required graph queries are straightforward, so an additional database service would add needless setup.
- **Technical detail:** NetworkX provides in-memory traversal; a graph database could be reconsidered for governed, large, frequently updated relationship data and operational needs.
- **Caution:** The repository has no Neo4j integration or benchmark showing one option is superior at bank scale.
- **Project evidence:** [architecture](docs/architecture.md), [dependency graph](docs/dependency_graph.md).

**Q6. Why Docker?**

- **Presentation answer:** Dockerfiles and Compose describe a consistent way to package the API and dashboard for a local demonstration.
- **Technical detail:** The API image generates the synthetic DB; the UI waits for the API health check.
- **Caution:** The README says Docker images were not actually built in the development environment; do not say the container deployment was verified end-to-end.
- **Project evidence:** [Dockerfile.api](Dockerfile.api), [docker-compose](docker-compose.yml), [README status](README.md).

**Q7. What is the difference between Docker and Render?**

- **Presentation answer:** Docker packages and runs the application; Render is a hosting platform that can run the packaged API service.
- **Technical detail:** The deployment guide configures Render to build the API from `Dockerfile.api`; that describes a deployment route, not Docker as a hosting provider.
- **Caution:** The guide records that deployment on Render itself was not verified during development.
- **Project evidence:** [deployment guide](docs/deployment.md), [Dockerfile.api](Dockerfile.api).

**Q8. What does Render do?**

- **Presentation answer:** In the documented public-demo setup, Render hosts the FastAPI backend and synthetic SQLite data.
- **Technical detail:** The service runs the API container, uses `/health`, and is configured with the mock LLM provider.
- **Caution:** A deployment recipe exists; do not infer from the repository alone that a live Render service is currently deployed.
- **Project evidence:** [deployment guide](docs/deployment.md).

**Q9. What does Streamlit Community Cloud do?**

- **Presentation answer:** In the documented setup, it hosts the Streamlit dashboard, which calls the API over HTTPS.
- **Technical detail:** A lightweight entrypoint reads `RISKSIGNAL_API_URL` from app secrets and delegates to the existing UI.
- **Caution:** The platform deployment itself is documented but was not verified in development.
- **Project evidence:** [deployment guide](docs/deployment.md), [cloud entrypoint](deploy/streamlit_cloud/streamlit_app.py).

**Q10. What role does GitHub play?**

- **Presentation answer:** It hosts the source repository and can connect to the documented Render auto-deploy flow.
- **Technical detail:** The guide points Render at the repository’s `main` branch; project tests are in `tests/`.
- **Caution:** Do not claim a configured CI workflow or a live deployment unless you verify it separately.
- **Project evidence:** [deployment guide](docs/deployment.md), [tests](tests/).

**Q11. What is Uvicorn?**

- **Presentation answer:** It is the ASGI server used to run the FastAPI application.
- **Technical detail:** The local instructions launch `risksignal.api.main:app` with Uvicorn; the Docker command binds to the configured port.
- **Caution:** Uvicorn serves the API; it does not implement the risk model or provide authentication by itself.
- **Project evidence:** [README quick start](README.md), [Dockerfile.api](Dockerfile.api).

**Q12. Why separate frontend and backend?**

- **Presentation answer:** It keeps the dashboard focused on presentation and the API responsible for calling domain tools and returning results.
- **Technical detail:** The Streamlit client makes HTTP requests; UI imports no engine, graph or agent package.
- **Caution:** Separation alone does not provide security; the documented prototype has no authentication.
- **Project evidence:** [architecture](docs/architecture.md), [API client](src/risksignal/ui/api_client.py).

**Q13. What happens when I click “Investigate this system”?**

- **Presentation answer:** The dashboard sends an investigation request into the conversation; the API runs the assistant and returns its answer, tool log and warnings.
- **Technical detail:** The UI calls `POST /agent/chat` with the conversation so far; the API builds a registry over the tool context and runs the assistant, the same agent loop as `POST /agent/investigate` with a conversational prompt.
- **Caution:** A live model can take time; mock mode uses a deterministic script instead.
- **Project evidence:** [Assistant UI](src/risksignal/ui/views/assistant.py), [agent route](src/risksignal/api/routes_agent.py).

**Q14. Walk through the full request from browser to answer.**

- **Presentation answer:** Browser → Streamlit → FastAPI → investigator/LLM provider → read-only tools → Python results → final response and visible tool trace.
- **Technical detail:** Tool outputs are returned to the model during its bounded loop; API response includes final text, activities, warnings and provider metadata.
- **Caution:** The model’s internal reasoning is not exposed or logged; the trace shows tool activity, not a complete proof of reasoning.
- **Project evidence:** [architecture](docs/architecture.md), [investigator](src/risksignal/agent/investigator.py), [agent route](src/risksignal/api/routes_agent.py).

**Q15. How is reproducibility handled?**

- **Presentation answer:** Data generation and simulations accept fixed seeds; results also report their assumptions and provenance.
- **Technical detail:** Tool calls are deterministic for the same data, arguments and seed, and the UI displays simulation metadata.
- **Caution:** A live LLM’s wording and tool selection may vary; deterministic numeric tools do not make the entire live conversation bit-identical.
- **Project evidence:** [data generator](src/risksignal/data/generator.py), [simulation engine](src/risksignal/stochastic/simulation.py).

**Q16. Why use fixed random seeds?**

- **Presentation answer:** So a demo or test can reproduce the same generated dataset and simulation output.
- **Technical detail:** The default seed is 42; it is passed to NumPy’s generator and surfaced with simulation results.
- **Caution:** A fixed seed is for reproducibility, not evidence of robustness; sensitivity across seeds is still important.
- **Project evidence:** [simulation engine](src/risksignal/stochastic/simulation.py), [data generator](src/risksignal/data/generator.py).

**Q17. What tests did you create?**

- **Presentation answer:** Tests cover the generator and storage, graph, stochastic methods, tools, agent, API, UI and deployment entrypoints.
- **Technical detail:** The technical review records 556 passing tests at the review date, with additional checks of formulas, layer boundaries, tool safety and paired-scenario simulation.
- **Caution:** Report that as the documented review run, not as a test run performed today; tests verify implementation, not model validity.
- **Project evidence:** [test suite](tests/), [technical review](docs/technical_review.md).

**Q18. What would have to change for production deployment?**

- **Presentation answer:** Authentication and authorization, approved data access, security controls, operational monitoring, audit, governance and institutional integration.
- **Technical detail:** Replace synthetic data and assumptions, implement controls and independent validation, and deploy in an approved environment with an approved model provider.
- **Caution:** The current prototype explicitly lacks production security and is not suitable for confidential data.
- **Project evidence:** [limitations](docs/limitations.md), [institutional validation roadmap](docs/institutional_validation.md).

### CATEGORY 6: DATA AND VALIDATION

**Q1. What parts are artificial, and what parts are real?**

- **Presentation answer:** The software structure and executable implementation are real; every Atlas Bank record and all model values are synthetic or illustrative.
- **Technical detail:** The repository implements generation, data access, graph queries, simulation, tools, agent, API and UI. No bank’s actual records are included.
- **Caution:** Do not let a realistic-looking dashboard imply the underlying events are real.
- **Project evidence:** [README](README.md), [limitations](docs/limitations.md).

**Q2. How was Atlas Bank generated?**

- **Presentation answer:** A seeded generator creates fictional systems, processes, vendors, dependencies, controls, incidents and monthly KRIs.
- **Technical detail:** Relationships and the focal story are partly hand-authored; random components use seed 42 by default, and incident losses are drawn from Lognormal distributions.
- **Caution:** The focal system’s pattern is deliberately constructed, not discovered from data.
- **Project evidence:** [data generator](src/risksignal/data/generator.py), [demo script](docs/demo_script.md).

**Q3. How do you know the synthetic data are not misleading?**

- **Presentation answer:** We do not claim they are realistic; we label them synthetic and document how they were made and what they cannot validate.
- **Technical detail:** They test deterministic mechanics and software paths, but contain no planted KRI-to-future-incident signal and were generated with Lognormal losses.
- **Caution:** Reproducibility and schema checks do not establish representativeness.
- **Project evidence:** [limitations](docs/limitations.md), [research extensions](docs/research_extensions.md).

**Q4. Why are mixed KRIs better than making every indicator deteriorate?**

- **Presentation answer:** A mixed pattern avoids a too-neat “all signals agree” demonstration and lets the analyst discuss conflicting evidence.
- **Technical detail:** The generated focal history has both increases and decreases; this remains a constructed data pattern, not a measured property of real KRIs.
- **Caution:** Do not use the mixture as proof of realism or as a designed prediction challenge with known validity.
- **Project evidence:** [demo script](docs/demo_script.md), [data generator](src/risksignal/data/generator.py).

**Q5. How would you validate on real bank data?**

- **Presentation answer:** Agree the intended use and event definitions first, assess data quality, reproduce a simple baseline, then run governed out-of-sample comparisons.
- **Technical detail:** The roadmap calls for point-in-time data, domain alignment, model diagnostics, sensitivity, validation, agent evaluation and production-readiness gates.
- **Caution:** Validation cannot be reduced to fitting the current model to a larger dataset.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md).

**Q6. How would you perform backtesting?**

- **Presentation answer:** Train or estimate only on the past and evaluate against later observations, repeating that process over time.
- **Technical detail:** Use rolling-origin splits with a gap, preserve point-in-time feature availability, compare with simple baselines and report uncertainty.
- **Caution:** RiskSignal now includes one training-only synthetic temporal holdout diagnostic, not real-data backtesting or independent validation. A random split would risk leakage and misrepresent future use.
- **Project evidence:** [research extensions](docs/research_extensions.md), [limitations](docs/limitations.md).

**Q7. What metrics would you use?**

- **Presentation answer:** Match metrics to intended use: probabilistic accuracy and calibration for counts, tail diagnostics for losses, and usefulness/oversight for analyst support.
- **Technical detail:** For λ(t), the roadmap names out-of-sample log-likelihood or Poisson deviance, calibration and alert burden/lead time; for the agent, correctness, traceability, time and review burden.
- **Caution:** No single score establishes fitness for all purposes; specify use and decision criteria before testing.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q8. How would you evaluate calibration?**

- **Presentation answer:** Check whether predicted frequencies or losses agree with what subsequently occurs, with uncertainty and at relevant segments.
- **Technical detail:** For count forecasts, compare observed counts with predicted intensity bins and use time-ordered holdouts; for loss tails, assess exceedances and parameter stability.
- **Caution:** There are no calibrated predictions in the current project to evaluate.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q9. What is data leakage and how would you avoid it?**

- **Presentation answer:** Leakage occurs when a model uses information that would not have been available when its prediction was meant to be made.
- **Technical detail:** Use point-in-time KRI values and publication lags, time-ordered splits with a purge gap, and carefully treat narratives written after an event.
- **Caution:** The current project has no prediction task, so it has no train/test leakage evaluation.
- **Project evidence:** [research extensions](docs/research_extensions.md), [technical review](docs/technical_review.md).

**Q10. How would you handle sparse extreme losses?**

- **Presentation answer:** Be explicit that data may not identify the tail reliably; combine diagnostics, uncertainty and domain review before selecting a method.
- **Technical detail:** Evaluate pooled or segmented approaches, thresholds, exposure, censoring and tail models; quantify parameter uncertainty and avoid over-interpreting P99/ES99.
- **Caution:** This prototype does not have a validated tail model and its small synthetic samples cannot solve the problem.
- **Project evidence:** [limitations](docs/limitations.md), [institutional validation roadmap](docs/institutional_validation.md).

### CATEGORY 7: REGULATION AND GOVERNANCE

**Q1. How does this relate to Basel?**

- **Presentation answer:** It uses the Basel Operational Risk definition as domain context, but RiskSignal is not a Basel implementation.
- **Technical detail:** The validation roadmap notes that regulatory Operational Risk capital has moved toward a standardized, non-model-based framework; applicability must be confirmed with regulatory specialists.
- **Caution:** Do not present the prototype’s simulation as Basel capital or compliance evidence.
- **Project evidence:** [domain model](docs/domain_model.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q2. Is this a regulatory capital model?**

- **Presentation answer:** No. The repository explicitly makes no regulatory capital claim.
- **Technical detail:** Its P99 and Expected Shortfall come from an illustrative compound Poisson-Lognormal model on synthetic data, not a regulatory methodology.
- **Caution:** Never label its outputs “capital,” “required capital” or regulatory measures.
- **Project evidence:** [limitations](docs/limitations.md), [stochastic model](docs/stochastic_model.md).

**Q3. Why use frequency-severity Monte Carlo if Basel uses the Standardised Approach?**

- **Presentation answer:** To demonstrate transparent stochastic scenario mechanics and analytical evidence gathering, not to replace the regulatory approach.
- **Technical detail:** Frequency-severity simulation can be an internal research or scenario-analysis tool if the institution defines and governs that use; regulatory applicability is a separate question.
- **Caution:** Do not suggest this is an alternative Basel capital calculation.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md), [limitations](docs/limitations.md).

**Q4. What model governance would be required?**

- **Presentation answer:** A written intended use, documented data and assumptions, independent validation, change controls, monitoring and clear human accountability.
- **Technical detail:** The roadmap separates data/domain alignment, baseline reproduction, model development, validation, agent evaluation and production readiness.
- **Caution:** The prototype has not completed institutional model governance or independent validation.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md), [technical review](docs/technical_review.md).

**Q5. What are risks of sending internal data to an external LLM?**

- **Presentation answer:** Confidentiality, data residency, retention, provider access, contractual terms and unintended disclosure all need review.
- **Technical detail:** An institution must assess approved deployment, minimization/redaction, logging, access boundaries and vendor/model governance before any data flow.
- **Caution:** The current public demo uses synthetic data and a mock provider; the prototype is not approved for confidential records.
- **Project evidence:** [limitations](docs/limitations.md), [deployment guide](docs/deployment.md).

**Q6. How would you handle data confidentiality?**

- **Presentation answer:** Keep data in an institution-approved environment, enforce least privilege and do not send sensitive information to unapproved services.
- **Technical detail:** Add authentication, authorization, encryption, data classification, secrets management, audit and retention controls; none is currently implemented end-to-end.
- **Caution:** Do not describe local `.env` or a mock provider as a complete confidentiality control framework.
- **Project evidence:** [limitations](docs/limitations.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q7. Could the bank replace Anthropic with its approved internal model?**

- **Presentation answer:** The provider abstraction makes that an architectural possibility, subject to the bank’s model and infrastructure approval.
- **Technical detail:** Implement an adapter for the approved interface, then retest tool calling, output quality, security and auditability in the target environment.
- **Caution:** No internal model adapter or approval exists in this repository.
- **Project evidence:** [provider base](src/risksignal/agent/base.py), [Anthropic provider](src/risksignal/agent/anthropic_provider.py).

**Q8. What controls should exist around the agent itself?**

- **Presentation answer:** Least-privilege read-only tools, validated arguments, human review, traceable evidence, clear failure reporting and a controlled deployment.
- **Technical detail:** Add access control and data permissions, output evaluation, monitoring, versioning, change approval, incident response and safe abstention; current registry already constrains available tools but is not sufficient for production.
- **Caution:** A prompt is not a control by itself, and the numeric grounding check is only best-effort.
- **Project evidence:** [tool registry](src/risksignal/agent/tool_registry.py), [agent design](docs/agent_design.md), [limitations](docs/limitations.md).

### CATEGORY 8: FUTURE RESEARCH

**Q1. What would be your first research priority with real bank data?**

- **Presentation answer:** First establish intended use, access permissions, definitions and data quality with the institution; only then reproduce a transparent baseline.
- **Technical detail:** Build a point-in-time system-period panel and document loss, KRI, control and dependency semantics before model comparison.
- **Caution:** No real bank data are present; do not imply that any institution is a participant or data source.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md), [limitations](docs/limitations.md).

**Q2. What would you test first: Poisson vs Negative Binomial, severity tails, XGBoost vs TFM, or historical-case retrieval?**

- **Presentation answer:** First check data and intended use; for the quantitative baseline, diagnose Poisson fit and severity-tail adequacy before adding predictive complexity.
- **Technical detail:** The agent retrieval question is a separate, potentially earlier analyst-workflow experiment; compare XGBoost and TFMs only after a valid prediction target and splits exist.
- **Caution:** These are candidate research tracks, not results or a commitment to a particular winning method.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q3. How would you rank those research tracks?**

- **Presentation answer:** Data and baseline validation first; then over-dispersion/tail diagnostics; in parallel, a scoped agent usefulness study; predictive ML last, after target and leakage design.
- **Technical detail:** This order reduces the risk of tuning complex models on untrusted labels and allows the independent RQ5 agent study to proceed if suitable analyst tasks exist.
- **Caution:** Priorities depend on the agreed business use and data readiness.
- **Project evidence:** [research extensions](docs/research_extensions.md), [validation roadmap](docs/institutional_validation.md).

**Q4. What could you achieve in a three-to-six-month internship?**

- **Presentation answer:** A bounded, evidence-based study: define a use case, assess governed data, reproduce a baseline and evaluate one carefully chosen extension or agent workflow.
- **Technical detail:** Agree milestones and stop/go criteria early; deliver reproducible results, uncertainty analysis, documentation and an honest recommendation, including a negative result if warranted.
- **Caution:** Do not promise production deployment, model approval or predictive gains before seeing data and constraints.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md), [research extensions](docs/research_extensions.md).

**Q5. What result would convince you that the agent adds value?**

- **Presentation answer:** A controlled analyst study showing less time or effort while maintaining or improving evidence quality, traceability and oversight.
- **Technical detail:** Predefine representative tasks and scoring; compare against the current workflow, measure correction burden, uncertainty and task mix, and replicate the finding.
- **Caution:** The repository has no analyst-study results.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q6. What result would make you reject the approach?**

- **Presentation answer:** If it fails to save meaningful effort, worsens answer quality, creates unacceptable review burden or cannot meet data governance requirements, I would not deploy it.
- **Technical detail:** Set rejection thresholds before the evaluation and report performance by task type, including failure and abstention rates.
- **Caution:** “Reject” may mean reject this agent design or use case, not that all AI assistance is unhelpful.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q7. What is the most scientifically uncertain part of RiskSignal?**

- **Presentation answer:** Whether any of its model assumptions or signals describe real Operational Risk behaviour; synthetic data cannot answer that.
- **Technical detail:** Rate stationarity, over-dispersion, severity tails, parameter uncertainty and KRI relationships all need real, point-in-time data and out-of-sample evaluation.
- **Caution:** A technically correct implementation is not empirical support for those assumptions.
- **Project evidence:** [limitations](docs/limitations.md), [technical review](docs/technical_review.md).

**Q8. What is the biggest engineering limitation?**

- **Presentation answer:** It is a demo prototype without production security, institution-grade integration or operational controls.
- **Technical detail:** It lacks authentication and authorization, and the live LLM and Docker images were not exercised in development; deployment guides are not evidence of deployed service readiness.
- **Caution:** Do not imply the prototype can safely process confidential data.
- **Project evidence:** [limitations](docs/limitations.md), [deployment guide](docs/deployment.md).

**Q9. What is the biggest Operational Risk limitation?**

- **Presentation answer:** The dataset and parameterization are synthetic, with no real taxonomy alignment, calibration, validation or causal evidence.
- **Technical detail:** Controls and KRIs are evidence only; the model omits time variation, tail calibration, parameter uncertainty and cross-system dependence.
- **Caution:** Outputs are not forecasts, decisions or capital figures.
- **Project evidence:** [limitations](docs/limitations.md), [domain model](docs/domain_model.md).

### 10 hardest questions Sylvain could ask

Use these as technically rigorous answers. Start with the short answer, then go to the technical point; explicitly state the boundary.

**Q1. Your count model assumes Poisson arrivals. What evidence supports that?**

- **Strong answer:** None about real operational incidents. Poisson is a transparent baseline chosen to demonstrate the frequency-severity workflow. It imposes independent arrivals and mean = variance = λ. With real data I would inspect counts by system and time, exposure, trend and clustering, then compare Poisson with Negative Binomial and other justified alternatives using time-ordered evaluation.
- **Caution:** The synthetic process cannot validate that choice.
- **Project evidence:** [frequency model](src/risksignal/stochastic/frequency.py), [research extensions](docs/research_extensions.md), [limitations](docs/limitations.md).

**Q2. Explain exactly how your λ is estimated, including sparse systems.**

- **Strong answer:** For n events over T years, λ̂=n/T, with T calculated from inclusive date bounds divided by 365.25. At five or more system incidents, use the system rate; below that, the code falls back to total incidents divided by years and system count. The method and history are labelled in output.
- **Caution:** Five is an illustrative threshold, and pooled fallback assumes comparability that has not been established.
- **Project evidence:** [frequency estimator](src/risksignal/stochastic/frequency.py), [stochastic model](docs/stochastic_model.md).

**Q3. A P99 from 100,000 runs looks precise. What uncertainty remains?**

- **Strong answer:** Monte Carlo sampling error is only one component. The 99th percentile uses about 1,000 simulated years, but the fitted parameters come from small synthetic samples; parameter uncertainty can be much larger and is not propagated. Model misspecification and data quality are additional uncertainties.
- **Caution:** More runs reduce Monte Carlo error, not parameter or model uncertainty.
- **Project evidence:** [metrics](src/risksignal/stochastic/metrics.py), [limitations](docs/limitations.md), [technical review](docs/technical_review.md).

**Q4. Why Lognormal, and why should I trust P99 or ES99?**

- **Strong answer:** I would not ask you to trust those tail values as real-world estimates. Lognormal is a transparent illustrative choice and the synthetic losses were generated from Lognormal distributions. Tail outputs show the mechanics under assumptions; real-tail claims need alternative models, diagnostics, uncertainty and independent validation.
- **Caution:** Good fit on this generator is circular, not evidence of real-world tail validity.
- **Project evidence:** [severity estimator](src/risksignal/stochastic/severity.py), [limitations](docs/limitations.md).

**Q5. What is the distinction between P99 and ES99 in your code?**

- **Strong answer:** P99 is the empirical 99th percentile of annual simulated losses; ES99 is the average of the worst 1% of simulated-loss mass. The implementation gives fractional weight to a boundary observation where needed, so ES is at least the matching quantile.
- **Caution:** Neither is regulatory capital or a validated bank estimate here.
- **Project evidence:** [metrics implementation](src/risksignal/stochastic/metrics.py).

**Q6. Can you use KRIs to make λ dynamic today?**

- **Strong answer:** No. The system displays KRIs but does not feed them into the model. A future test would align system-period incident counts with point-in-time lagged KRIs, use exposure offsets and rolling-origin evaluation, and compare with simple rate and threshold baselines.
- **Caution:** The synthetic KRI series is independent of incidents, so it cannot demonstrate this relationship.
- **Project evidence:** [KRI tools](src/risksignal/tools/kri_tools.py), [research extensions](docs/research_extensions.md).

**Q7. Why isn’t the vendor graph reflected in the stress loss results?**

- **Strong answer:** The graph identifies shared structural exposure, but the scenario engine applies explicit numeric changes to one system’s λ, μ and σ. It does not infer causes or jointly simulate connected systems.
- **Technical detail:** Baseline and stress years are coupled using common random numbers via Poisson superposition/thinning to reduce comparison noise; that coupling does not introduce cross-system dependence.

- **Caution:** The vendor outage scenario’s numbers are illustrative assumptions, not graph-derived effects; common-vendor dependence is unmodelled.
- **Project evidence:** [scenario engine](src/risksignal/stochastic/scenario.py), [graph queries](src/risksignal/graph/queries.py).

**Q8. What exactly is validated by the tests and technical review?**

- **Strong answer:** They check that code implements the documented formulas and boundaries: parameter fitting, aggregation, metrics, graph/tool/API layering and agent behaviour. The review reports an independent numerical check and 556 passing tests at that time.
- **Caution:** It is explicitly not an independent model validation and says nothing about empirical fit or predictive performance.
- **Project evidence:** [technical review](docs/technical_review.md), [tests](tests/).

**Q9. How would you backtest without leakage and with rare events?**

- **Strong answer:** First fix the target, horizon, materiality and point-in-time availability. Then use rolling-origin splits with purge gaps, preserve KRI publication lags and assess event-level power before modelling. Report proper scoring, calibration, lead time, alert volume and uncertainty against simple baselines.
- **Caution:** A random split or accuracy alone is not credible evidence in a sparse event setting.
- **Project evidence:** [research protocol](docs/research_extensions.md), [validation roadmap](docs/institutional_validation.md).

**Q10. Your agent flags ungrounded numbers. Does that solve hallucination?**

- **Strong answer:** No. It is a best-effort numerical consistency check against values in tool inputs and outputs. It cannot establish whether a statement is semantically supported, whether a number is used in the right context, or whether a tool result itself is correct. The trace helps a reviewer check.
- **Caution:** Never say the agent “cannot hallucinate.”
- **Project evidence:** [number grounding](src/risksignal/agent/investigator.py), [agent design](docs/agent_design.md).

### 10 executive questions Edith could ask

**Q1. What practical problem could this solve for an Operational Risk team?**

- **Strong answer:** It could reduce the manual effort of assembling system-level evidence and make cross-system dependencies easier to inspect. This repository demonstrates that workflow, but does not yet prove analyst time saved or decision improvement.
- **Caution:** Position it as a testable workflow hypothesis, not an established business case.
- **Project evidence:** [project brief](docs/project_brief.md), [research extensions](docs/research_extensions.md).

**Q2. What is the business value beyond a dashboard?**

- **Strong answer:** The potential value is guided evidence gathering with a visible audit trail: the agent can select relevant read-only tools, while deterministic code owns the calculations. The value must be measured against analysts’ existing process.
- **Caution:** No measured productivity, loss avoidance or financial return is reported.
- **Project evidence:** [agent design](docs/agent_design.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q3. Why would this justify an internship?**

- **Strong answer:** It creates a bounded research agenda at the intersection of Operational Risk, quantitative validation and human workflow. An internship could test one agreed use case on approved data and produce reproducible evidence (including a negative result) rather than promise a finished product.
- **Caution:** The scope depends on access, governance approvals and analyst availability.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md), [research extensions](docs/research_extensions.md).

**Q4. What would you need from us before starting?**

- **Strong answer:** A sponsor and intended use, a domain expert, a governed data-access path, agreed event/KRI definitions and success criteria. I would begin with discovery and data quality, not assume a model is the first task.
- **Caution:** Do not ask for confidential data outside approved channels.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md).

**Q5. Is the system making a risk decision?**

- **Strong answer:** No. It retrieves evidence, runs explicitly labelled simulations and suggests questions for an analyst. It cannot change records or declare a system safe or unsafe.
- **Caution:** The agent’s natural-language output still needs human review.
- **Project evidence:** [agent prompt](src/risksignal/agent/prompts.py), [agent design](docs/agent_design.md).

**Q6. What are the biggest governance and confidentiality concerns?**

- **Strong answer:** The prototype lacks authentication, authorization and production security; external-provider use would require a formal data, vendor and model-governance assessment. The documented public demo uses synthetic data and a mock provider.
- **Caution:** It must not be connected to confidential information as-is.
- **Project evidence:** [limitations](docs/limitations.md), [deployment guide](docs/deployment.md).

**Q7. Why not just use an existing internal model or tool?**

- **Strong answer:** That may be the right choice. RiskSignal’s contribution is a prototype pattern for joining evidence retrieval, dependency context and deterministic calculations behind an agent interface. An institutional evaluation should compare it with existing workflows and reuse approved tools where appropriate.
- **Caution:** No head-to-head comparison with bank systems has been done.
- **Project evidence:** [architecture](docs/architecture.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q8. What would a successful three-to-six-month outcome look like?**

- **Strong answer:** A clear intended-use decision, a data-quality and baseline report, and one pre-agreed evaluation (either a quantitative model comparison or an analyst-task study) with uncertainty, limitations and a recommendation.
- **Caution:** Success need not mean a positive result; ruling out an unhelpful approach is useful.
- **Project evidence:** [institutional validation roadmap](docs/institutional_validation.md), [research extensions](docs/research_extensions.md).

**Q9. What would make you stop?**

- **Strong answer:** Inadequate data quality, unresolvable governance constraints, no measurable improvement over the current workflow or a drop in evidence quality/control would be valid stop criteria. I would define those before seeing test outcomes.
- **Caution:** Avoid implying sunk-cost commitment to AI or to the current model form.
- **Project evidence:** [research extensions](docs/research_extensions.md), [institutional validation roadmap](docs/institutional_validation.md).

**Q10. What is the honest one-sentence conclusion?**

- **Strong answer:** RiskSignal is a tested, synthetic-data prototype showing how an evidence-gathering agent can sit above deterministic Operational Risk tools; whether it improves real analysis remains an empirical and governance question.
- **Caution:** Keep “tested prototype” separate from “validated model” and “production-ready system.”
- **Project evidence:** [technical review](docs/technical_review.md), [limitations](docs/limitations.md).
