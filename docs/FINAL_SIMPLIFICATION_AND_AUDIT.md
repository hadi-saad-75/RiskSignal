# Final simplification and local audit

## Product objective

RiskSignal helps Operational Risk analysts connect relevant evidence and identify what should be investigated next.
Its two goals are AI-assisted investigation and up to three justified follow-up investigations. The analyst decides; Monte Carlo is an optional financial what-if.

## Problems and feature reduction

The previous interface had five destinations, overlapping evidence views, lengthy introductory material, multiple default charts and quantitative detail ahead of the investigation. The final reduction changes the workflow, not the underlying loss model.

| Existing feature | Decision | Reason / final location |
|---|---|---|
| Introduction page, portfolio sample and workflow cards | Remove from navigation | Purpose and synthetic-data notice now fit in the investigator header. |
| Risk Workbench Monitor | Consolidate | Monitoring is context within Risk Investigator, not a separate destination. |
| AI Investigator | Keep / simplify | Default page with one prominent investigation action. |
| System Explorer page and profile KPIs | Consolidate / hide | System details and evidence disclosures replace a second evidence dashboard. Inventory criticality remains a recorded classification. |
| Way Forward page and development pitch | Remove from navigation | Future work remains in documentation, not the live workflow. |
| Conversational development preview | Hide | Existing provider/API capabilities and tests remain; the unfinished preview is not a headline feature. |
| Four monitoring indicators | Simplify | At most three, with unusual or missing/stale evidence prioritised. No duplicate headline KPIs. |
| Long investigation response | Simplify | Summary first, at most three findings and three ordered, justified next questions. Complete response remains expandable. |
| All default KRI charts | Simplify / hide | One selected KRI and time window, inside evidence disclosure. Descriptive window results and monitoring methodology remain accessible. |
| Incident and control detail | Keep / hide | Short source tables; incident history can be changed to 3-60 months. Full control records remain inspectable. |
| Large dependency presentation | Simplify / hide | Direct/shared/indirect vendor and process tables first; dependency map only on request. |
| Mandatory investigation Monte Carlo | Remove | Default investigation uses evidence tools. Explicit financial-loss or stress requests retain simulation tools. |
| Scenario Analysis | Keep as optional page | Explicit run, three primary metrics: mean, P95 and Expected Shortfall 95%. |
| Distribution, median/P99/ES99 and model parameters | Hide | Expandable distribution and model details preserve all results and assumptions. |
| Duplicate AI evidence-draft action | Hide | Optional fingerprint-bound RCSA draft remains under Advanced checks, not beside the main action. |
| RCSA prompts and temporal diagnostics | Hide | Advanced supporting checks, not ratings or a separate product. |
| Reviewer notes and JSON export | Keep / hide | Available in supporting evidence; session-local until exported. |
| Oversized editorial header, repeated large notices and footer links | Remove / simplify | Short title, restrained captions, subtle separators and two navigation links. |
| Existing engines, tools, data, documentation and tests | Keep | No working service or test was deleted to reduce the interface. Legacy view modules remain unregistered. |

## Navigation, language and visual design

Only **Risk Investigator** (`/`, default) and **Scenario Analysis** (`/scenario-lab`) are registered.
Introduction, System Explorer and Way Forward leave primary navigation; the already-consolidated Monitor does not return.

Plain language replaces a technical pitch: “System context”, “Key Findings”, “Next Investigations” and “Supporting Evidence”.
Review dates do not establish control failure, statistical monitoring flags are not approved risk-limit breaches, and dependencies do not establish causes.

Inter sans-serif typography has Segoe UI/Arial fallbacks for local readability. White `#FFFFFF`, soft grey `#F5F7FA`, navy `#183153`, dark text `#172B45`, restrained blue `#2864A0` and borders `#DFE5EC` replace the previous institutional/serif presentation.
Charts use matching navy/blue/grey styling. There are no proprietary logos, brand assets or JPMorgan-inspired display fonts. Optional web-font loading is not required for readable fallback text.
The content is width-limited; typography, spacing and native disclosures establish hierarchy instead of decorative cards.

## Agent workflow and code changes

- Monitoring cues accompany the investigation request. The default mock script retrieves profile, incidents, monitoring, controls and dependencies; it does not run a simulation.
- Financial-loss questions add baseline simulation; explicit stress requests retain baseline/stress comparison. Existing deterministic tools do the calculations.
- The scripted follow-up order is control-review evidence, incident reports, then shared-supplier evidence where available. A supplier mentioned in incident narratives is preferred over alphabetical selection. This is a transparent review heuristic, not an estimated risk ranking.
- Prompts request two or three summary sentences, at most three findings and three justified next questions, with returned source IDs. No invented ratings, confidence scores or causal conclusions.
- The UI enforces display order and caps structured findings, including numbered bullets. Excess output stays in disclosure. Malformed responses are explicitly reported rather than displayed as an uncapped or fabricated summary.
- Tool errors and incomplete runs remain visible. Failed or blank new investigations clear previous findings; refreshing evidence clears the answer. Changing systems cannot show another system's answer.
- Expensive charts render only when requested. The scenario page no longer runs a simulation merely to display estimates. Failed scenario reruns clear old results; changed inputs trigger a stale-result warning.
- Workpapers are cached per system/session until explicit refresh, with their snapshot date visible. System lists have a session-local 60-second cache. Sidebar health is reused within a rerun; no shared cross-user cache was introduced.
- Unused imports and repeated display operations were reduced. UI-to-API separation remains intact. No model, agent framework or dependency was added in this final reduction.

## Mathematical checks

The complete suite checks incident-frequency estimation and observation windows, Poisson counts, Lognormal fitting/parameterisation, annual-loss aggregation, quantiles, Expected Shortfall, baseline/stress coupling, validation/memory guards and seeded reproducibility.
The final simplification does not change model equations, stochastic assumptions or synthetic records.

Actual localhost tool outputs for `PAYMENT_ENGINE_01`, seed 42 and 100,000 simulated years:

| Metric, synthetic monetary units | Baseline | Shared-vendor stress |
|---|---:|---:|
| P95 annual loss | 896,435 | 2,276,896 |
| Expected Shortfall 95% | 1,546,928 | 3,927,230 |

These match the existing tested reference values. Counts, individual losses and aggregate annual losses remain distinct; control status and KRIs do not automatically alter the loss parameters.

## Local functionality and verification

Owned validation services started successfully on `127.0.0.1:8017` (FastAPI, mock) and `127.0.0.1:8517` (Streamlit); both health endpoints responded. These temporary validation services were stopped after inspection. Existing services on ports 8000/8501 were not stopped or replaced.

Browser inspection covered both **1366 x 768** and **1920 x 1080**. The investigation button remained within the initial viewport (approximately y=664-666, height 42 pixels), three context metrics were present, and the main container had no horizontal overflow.
The local browser exercised system switching to `CORE_LEDGER_01` and back, investigation summaries/priorities, evidence links, incident/control tables, KRI history, dependency tables/map, review/export controls and scenario comparison/distribution. No Streamlit exception was observed.
Some integrated-browser pointer-stability and chained-action waits timed out; keyboard/DOM actions and subsequent snapshots verified the rendered panels. This is not a claim that every mouse interaction was exhaustively tested.

Single local request samples, including PowerShell overhead: systems 13 ms, workpaper 68 ms, default mock investigation 63 ms; a separate seven-tool stress investigation completed in 211 ms with no grounding warnings. These are observations, not performance guarantees or live-LLM timings. Startup duration was not benchmarked.

Automated checks cover unknown systems, invalid assumptions, API unavailability, missing optional model configuration, mock operation without a paid API, stale/failed runs, source disclosures, exact export evidence, secret-file exclusions and layer boundaries.

**Final command:** `.\.venv\Scripts\python.exe -m pytest -q --tb=short`

**Result: 706 passed in 59.23 seconds.** Changed navigation/output expectations were updated, coupled workflow defects were fixed, and final chart-unit assertions were verified. No tests were deleted; 15 regression cases were added.
`git diff --check` and compilation of the UI/agent packages also passed. Pylance confirmed the investigator-script signature is compatible with all eight resolved callers and found no syntax errors in the investigator/evidence views; a separate scenario-file Pylance request timed out, while compilation and executed tests passed.
No public URLs, hosting, Docker readiness or production scaling were evaluated.

## Remaining limitations

- Synthetic records and circular synthetic-distribution fitting are not real-bank calibration or predictive validation.
- The offline provider is deterministic scripting, not live LLM tool calling. Live Anthropic behavior, evidence-selection quality and latency remain unverified.
- Numeric matching is best effort, not proof that a figure is attached to the correct fact. Source-ID links lead to grouped supporting evidence, not immutable record permalinks.
- Workpapers are explicit-refresh session snapshots, not continuously updated feeds. Notes/fingerprints are not persistent case management, authenticated sign-off or an immutable audit trail.
- The loss model simulates a single system under explicit assumptions; it does not infer incident causes, jointly model supplier failures or predict exact future events.
- No authentication exists. Keep the prototype local and use only its synthetic demo records; basic checks are not a production security certification.

## Follow-up: introduction and database sections

Current navigation update: the user subsequently requested **Way Forward**. The four current pages are **Introduction**, **Risk Investigator** (default), **Scenario Analysis** and **Way Forward**. Database remains removed. The new roadmap covers approved real bank data, jurisdiction/use-case-specific regulatory and internal review, expert involvement, out-of-sample probabilistic loss-model assessment and a supervised live-LLM trial on one real analyst task. These are proposed steps, not current validation or compliance claims.

Final pre-commit verification of the current four-page version: **722 tests passed in 83.77 seconds**. The legacy future-work heading assertion was updated to the new real-task evaluation heading. Whitespace checks passed.

Latest update: the user requested removal of the Database section. It is no longer registered in navigation. Current pages are **Introduction**, **Risk Investigator** (default) and **Scenario Analysis**. Underlying synthetic records and read-only backend functionality remain unchanged. The following paragraphs record the earlier implementation history.

The user clarified that these must be standalone navigation pages, not disclosures within Risk Investigator. The current navigation is **Introduction**, **Risk Investigator** (default), **Database** and **Scenario Analysis**.
Introduction at `/introduction` covers current approaches, the need, goal and LLM idea. It is explanatory context, not a formal literature review or a claim about every institution.
Database at `/database` browses all seven raw synthetic source tables in a read-only, fixed-height grid, 100 records per page. Shared IDs and table meanings are explained. The API whitelists table names, binds pagination values, caps requests at 200 rows and preserves source values. These pages replace the previously embedded sections without duplicating their content or modifying records/models. The two-page reduction above records the earlier design, superseded by this explicit request.

Initial follow-up validation: **722 tests passed in 57.33 seconds**, including exact source rows for all seven tables, table switching, pagination, empty pages, invalid requests and unavailable data. Local browser inspection confirmed the four introduction headings and a 420-pixel database grid without a Streamlit exception. Database table switching and paging were verified with Streamlit AppTest; an integrated-browser dropdown action timed out, so browser-only paging was not fully verified.

After moving these sections to standalone navigation pages: **722 tests passed in 93.45 seconds**, including the four-page registration, visible introduction content and direct database rendering. `git diff --check` passed.

## Five-minute demonstration

1. **0:00-0:40:** Open Risk Investigator. State the purpose, synthetic-data limit and actual provider.
2. **0:40-1:10:** Select `PAYMENT_ENGINE_01`; notice failed deployment rate 10.51, while the other displayed indicators are within baseline.
3. **1:10-2:40:** Click **Investigate system**. Read the summary and two or three source-linked findings.
4. **2:40-3:50:** Expand C002 control evidence and a recent incident or shared Keystone supplier. Explain why the record justifies a question, not a causal verdict.
5. **3:50-4:40:** If useful, show the optional baseline/stress P95 comparison. Explain it as the financial consequence of assumptions, not a forecast.
6. **4:40-5:00:** Return to the ordered next investigations: request test/review evidence, incident follow-up and supplier contingency evidence. The analyst discusses action with the responsible people.

Launch commands: [README_PRESENTATION.md](README_PRESENTATION.md). Detailed rehearsal and tested numbers: [demo_script.md](demo_script.md).
