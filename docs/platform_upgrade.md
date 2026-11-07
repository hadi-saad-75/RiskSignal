# RiskSignal: audit, gap analysis and implementation

Assessment and implementation: 6 November 2026. Industry evidence is in the [research report](industry_research.md) and [34-role evidence register](research/job_evidence.csv).

## Follow-up UI redesign

The original top-level Assistant and Risk workbench pages have since been consolidated into
**Risk Investigator**. The selected system's compact monitoring snapshot now leads directly
to the investigation request, and the same monitoring, RCSA, diagnostic and review/export
capabilities remain available in expandable supporting sections. See the [five-minute demo
script](demo_script.md) for the current route.

## 1. Audit before changes

The original application was already a substantive **technology operational-risk investigation prototype**, not merely a generic chatbot.

### Verified architecture and workflows

- Python package with separate data, graph, stochastic, tool, agent, API and Streamlit layers. The UI accesses the backend only through its HTTP client.
- Pydantic row/result schemas, cross-table validation, seeded generator, readable CSVs and SQLite storage.
- Default database inspected: **20 systems, 10 processes, 8 vendors, 40 controls, 312 incidents and 5,880 monthly KRI observations**, spanning 1 October 2021 to 30 September 2026. All are fictional Atlas Bank data. Counts are database observations, not industry statistics.
- NetworkX dependencies link systems, processes, vendors and controls. Shared exposure is explicitly distinguished from causation.
- Compound Poisson/Lognormal annual-loss simulation, explicit pooling on small samples, seeds, tail metrics, paired common-random-number stress comparisons and user-specified scenario assumptions.
- Read-only tool-calling agent, Anthropic provider interface, deterministic mock, structured errors, activity logs and best-effort unmatched-number checks.
- Streamlit Introduction, System Explorer, Scenario Analysis, Risk Investigator and Way forward pages. A conversational API exists, but the main investigator page focuses on a structured investigation.
- Local Python, Docker and separate API/UI deployment surfaces. Existing documentation correctly warns that live Anthropic and Docker operation were not independently exercised.
- **Baseline before editing: 650 offline tests passed.**

### Strengths against employer needs

The existing incident/KRI/control evidence, graph, quantitative mechanics and tool traces already demonstrate relevant skills for J10/J19/J21/J23/J25/J27. Synthetic-data and non-capital disclaimers are a strength, not something to remove for a more impressive demonstration.

### Weaknesses and boundaries

1. KRIs were descriptive charts/window averages, without an explicit exception-review policy or missing/stale-data state.
2. Controls had review dates/status but no test samples, effectiveness evidence, owners or remediation lifecycle. This is not a full RCSA or continuous-control-testing system.
3. Simulation mechanics had tests, but users could not inspect an explicit historical training/holdout diagnostic in the UI.
4. Investigation evidence was useful, but not organised into a reproducible reviewer workpaper with an explicit human-review-note export.
5. Numeric matching is not semantic fact checking: an answer can use a correct number with the wrong entity, cause, context or conclusion.
6. Synthetic narratives and losses are constructed. There is no credible supervised future-loss target or real model-performance evidence. Training a classifier on templated descriptions would not demonstrate real-world accuracy.
7. There is no approved document corpus, legal applicability engine, production authentication, durable case management or independently validated model inventory.
8. Several documentation/preview views overlap. They were retained because replacing or deleting working presentation material would add risk without solving the most valuable gaps.

## 2. Employer-to-capability gap analysis

| Requirement and evidence | Before | Targeted change | What remains missing |
|---|---|---|---|
| Accurate risk/control data, AI-supported review/challenge: J25/J27 | Incident, control and KRI tools existed separately | Draft RCSA evidence workpaper with linked records and explicit questions | Actual control tests, owner attestations, risk/control mapping and approved RCSA scoring |
| Monitoring and early investigation: J10/J16/J25 | Charts and descriptive comparisons | Past-only robust monitoring; missing/stale/gapped/insufficient/not-applicable states; flag workload | Approved appetite limits, operational labels, seasonality calibration and alert routing |
| Model evaluation and effective challenge: J19/J23 | Reproducible simulation and technical tests | Historical temporal holdout; pooling visibility; count dispersion/reference interval and severity-tail exceedances | Independent validation, repeated out-of-time evaluation, real data and parameter uncertainty |
| Committee reporting and traceability: J16/J25/J28 | Agent summaries and tool logs | Evidence fingerprint, structured JSON download, source-linked questions and session-local human notes | Authenticated reviewers, immutable logs, retention and managed report distribution |
| AI-native risk workflows: J21/J31/J34 | Bounded read-only assistant | Three new tools available to live and offline conversational providers; workbench draft button | Evaluation with a live model and real analyst questions |
| Resilience and third parties: J10/J25 and ECB DORA source | Shared-vendor/system graph and scenario assumptions | Existing graph reused in resilience review questions | Important business services, impact tolerances, tested recovery evidence and reporting rules |
| AI governance: J13/J16/J18/J32 | Read-only agent and caveats | Versioned methods, explicit source/draft boundaries and temporal evidence | Governed model/use-case inventory, roles, policy lifecycle and specialist sign-off |
| Document intelligence: J23/J31 | No retrieval corpus | Deliberately not improvised | Approved corpus, access filtering, citations, retrieval evaluation and injection testing |

## 3. What changed

### A. Risk workbench

Added a top-level **Risk workbench** page at `/risk-workbench`, also linked from Introduction. Existing pages, styling, dataset, models, scenarios and deployment entrypoints remain.

Workflow:

1. Select an existing system.
2. Inspect early-warning signals and calculation history.
3. Review control records and source-linked RCSA questions.
4. Examine the quantitative model's historical holdout.
5. Optionally request a draft evidence summary from the existing conversational API.
6. Record human evidence-gap/next-step notes.
7. Download the evidence and notes as JSON.

Evidence is cached per system in the browser's Streamlit session, not globally. **Refresh evidence** explicitly queries the backend again; failure does not display a success-shaped replacement. Notes are tied to the evidence fingerprint. They are lost when the session is lost unless downloaded. No user note updates an incident/control, attests effectiveness, approves a risk or closes an action.

During development source reloads, a session's API client wrapper is refreshed to the current class while retaining its configured HTTP transport. This prevents pre-upgrade sessions from failing on newly added methods without clearing their evidence or review notes.

### B. Explainable KRI monitoring

Implementation: [monitoring tools](../src/risksignal/tools/monitoring_tools.py).

- For each monthly observation, take up to 12 **earlier calendar months**, with at least 6 contiguous observations.
- Compute median and median absolute deviation (MAD).
- Score = `(current - prior_median) / (1.4826 * prior_MAD)`.
- A one-sided score **strictly above 3.5** is an unusual-increase review signal. The constants are transparent **illustrative policy choices**, not employer-prescribed or statistically calibrated appetite limits.
- A zero MAD yields **no numeric z-score**. An increase above a flat baseline has its own signal type, acknowledging that discrete/count data can have many zeros.
- Missing, stale, gapped and insufficient history are explicit. No interpolation or invented baseline is used.
- For the existing Atlas generator only, an absent vendor-incident KRI with no direct vendor dependency is **not applicable**, not a data-quality failure. This follows the generator's existing applicability rule and is explained in the result.
- The last twelve months' scored/flagged counts and flag rate describe review workload. **They are not precision, recall, anomaly-detection accuracy, a probability of loss or a forecast.**

The complete API calculation history and source identifiers are available for inspection/export. No predictive ML label or synthetic performance score was manufactured.

### C. Temporal model diagnostics

Implementation: [statistical diagnostics](../src/risksignal/stochastic/diagnostics.py), with a thin [tool adapter](../src/risksignal/tools/validation_tools.py).

- Reserve the final twelve calendar months as holdout: training includes the cutoff date, holdout excludes it.
- Reuse `build_baseline_model` on training data only, including **training-only bank-wide pooling** where the existing sample rules require it.
- Use full training-month counts, including months with zero incidents, for the descriptive variance/mean ratio. Partial boundary months are excluded from this monthly statistic.
- Report observed holdout count, fitted expected count adjusted for actual days/365.25 and a conditional fitted-Poisson 95% count reference interval.
- Compare positive holdout severities with the **training** individual-loss P95. It is not annual-loss P95.
- Expose training/holdout sample sizes, severity pool, fitted parameters and limitations. Insufficient data produce an explicit `not_estimable` status and reason.

The existing Monte Carlo/stress paths and parameters were **not changed**. A single synthetic historical split is an educational diagnostic, not independent validation, statistical acceptance, confidence in future losses or regulatory-capital calibration. Parameter uncertainty, dependence, rare tails and the existing absence of a zero-loss severity mixture remain limitations.

### D. RCSA preparation and traceable reporting

Implementation: [workpaper tools](../src/risksignal/tools/workpaper_tools.py).

- Reuses existing system, incident, control and dependency functions alongside the new monitoring/diagnostic functions.
- Questions explicitly ask for owners, design/operating-effectiveness evidence, approved methodology, root causes, remediation and resilience evidence. No arbitrary inherent/residual rating is calculated.
- Due/overdue reviews generate follow-up questions, **not** control-failure findings.
- Missing/stale/gapped/insufficient KRI data trigger questions rather than being presented as reassuring.
- Workpapers have explicit draft status, method versions and a reproducible SHA-256 content fingerprint. Nested results distinguish observations from modelled diagnostics; the overall pack is labelled `mixed_evidence`.
- The hash excludes only its own field and includes the structured evidence/questions/limitations. It is **not** a digital signature, immutable log, authenticated reviewer identity or regulatory attestation.
- The JSON download separates immutable-by-convention source evidence from session-local timestamped human review notes, with an overall `draft_not_approved` status.

The local demo assumes a static dataset while tools gather evidence. Separate reads are not a transactional production snapshot. Deploying a real editable risk register requires stronger storage and consistency guarantees.

### E. Existing AI reused

Both investigation and conversational registries gain:

- `get_kri_monitoring`
- `get_model_diagnostics`
- `get_risk_workpaper`

The original seven investigation tools and four additional conversational portfolio tools remain. There are now ten investigation tools and fourteen conversational tools. No autonomous write/approval action or new agent framework was introduced.

The offline conversational provider recognises monitoring, diagnostics and RCSA requests and executes the real functions. Its output is explicitly labelled **scripted local draft**, not presented as a live LLM.

The workbench accepts a draft only after a completed run whose tool activity contains the **same workpaper fingerprint** as the displayed snapshot. Missing/mismatched evidence or interrupted runs are rejected visibly. This checks source-snapshot identity, not semantic correctness of every sentence. Detailed walk-forward histories are omitted only from model-facing tool views; latest calculations, source references and summary statistics remain, while full histories remain in the API/export. No additional external service or credential is needed for deterministic workflows.

### F. APIs and dependencies

New read-only endpoints:

```text
GET /systems/{system_id}/monitoring
GET /systems/{system_id}/model-diagnostics
GET /systems/{system_id}/workpaper
```

They use existing dependency injection, typed errors, validation and API-client patterns. Unknown systems return the existing 404 error shape; missing databases return 503. The deployed thin UI still imports no backend engines.

**No new dependency, database schema, generator, loss model or scenario assumption was required.** The Streamlit minimum in package/root requirements and the UI Dockerfile is aligned to **1.65**, the already-installed and Community Cloud-pinned version, because the new accessible dataframes use its `alt` parameter. This prevents an older allowed install from failing on a newly used API; it is not a framework migration. No proprietary data, new credentials or downloaded model weights were introduced.

## 4. Testing evidence

Environment: repository `.venv`, Python 3.13, installed Streamlit 1.65.0. No package installation was required.

| Check | Result |
|---|---|
| Original complete offline suite before edits | **650 passed** |
| Final complete offline suite after implementation | **690 passed**, including **40 added workbench cases** |
| Workbench and UI targeted suite | **85 passed** at the intermediate checkpoint; subsequent full suite includes final applicability coverage |
| Final workbench, UI, demo, deployment, package-import and Cloud regression check | **187 passed** after the final documentation/UI refinements and Streamlit minimum-version alignment |
| Follow-up stale-session client regression and workbench/UI suite | **87 passed**, including a test that first reproduced the reported missing-`workpaper` error using a pre-upgrade client class |
| New tool results for every existing system | All 20 systems produce serializable workpapers with matching content fingerprints |
| Pylance diagnostics | No reported diagnostics for new monitoring, workpaper schema/adapter, workpaper, statistical-diagnostic and UI modules checked |
| Python syntax check | Statistical diagnostic module passed Pylance syntax validation |

Commands used:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests\test_workbench.py tests\test_ui.py
.\.venv\Scripts\python.exe -m pytest tests\test_workbench.py tests\test_ui.py tests\test_demo_script.py tests\test_deployment.py tests\test_package_imports.py tests\test_render_and_cloud.py -q
```

The new tests verify the **exact** threshold and baseline calculations, zero-MAD handling, twelve-month history cap, duplicate-month/non-finite rejection, gaps, no future-data leakage, missing/stale/not-applicable states, exact training-model reuse, train-only pooling, future/holdout mutation invariance, insufficient data, all source references, digest reproducibility/change detection, typed failures, API responses, real-tool mock AI calls, all four UI tabs, system changes, human-note validation, **exact downloaded JSON**, failed refresh behaviour, and rejection of missing/mismatched/incomplete AI evidence.

Some original tests intentionally enumerated seven tools/fourteen endpoints. Their expected inventories were expanded to cover the additive APIs/tools; existing workflow assertions were retained. An intermediate architecture test caught numerical imports in a tool adapter; the statistical computation was moved into the existing stochastic layer, preserving the original separation.

Streamlit interaction was validated with first-party `AppTest` against the real FastAPI app in-process, without paid APIs or a server. This proves widget/API behaviour, not browser CSS rendering. Live Anthropic quality, latency, cost and adversarial robustness were **not** evaluated, and no claim is made about Docker runtime, real-data performance, regulatory compliance or production deployment.

A subsequent running-browser smoke check after an approved dashboard restart confirmed the workbench loads for `PAYMENT_ENGINE_01` and the reported `CASH_FORECAST_01` system, including an evidence refresh without the missing-method exception. This is not a comprehensive visual/accessibility audit. Restarting was necessary to clear the existing process's old imported modules; the client-wrapper migration protects session state when updated modules are loaded.

## 5. Interview demonstration

The current five-minute route is **Introduction -> Risk Investigator -> supporting evidence**:

1. Select `PAYMENT_ENGINE_01` and state the synthetic-data boundary.
2. Read the compact monitoring snapshot, noting that past-only signals are review prompts, not forecasts or approved appetite breaches.
3. Run **Investigate system** and present the findings before opening evidence.
4. Expand one tool result and the controls/dependencies section to show the source and a practical next step.
5. Disclose whether the active provider is a live LLM or the deterministic scripted mock. Expand quantitative results only if useful.

Strong framing: “I combined operational-risk evidence, quantitative model challenge and constrained generative-AI orchestration, with explicit provenance and human ownership.” Do not claim real-bank adoption, saved analyst hours, predictive accuracy or compliance.

## 6. Ranked roadmap

| Rank | Enhancement | Business value | Complexity | Hiring relevance / prerequisites |
|---|---|---|---|---|
| 1 | Governed risk/control/issue records, owners and real test evidence | Very high | Medium-high | J10/J25/J27. Agree taxonomy, permissions and methodology with risk users before adding effectiveness scores. |
| 2 | Authentication, role separation, durable case/reviewer audit and approved data handling | Essential before a real pilot | High | J13/J16/J18. Current local/export-only prototype must not receive confidential data. |
| 3 | Live-LLM evaluation set: source fidelity, abstention, wrong-entity attribution, adversarial records and useful drafts | High | Medium | J19/J21/J23. Use approved provider/data, labelled expectations, latency/cost budgets and analyst review. |
| 4 | Approved KRI limits, data contracts, alert review/routing and workload/precision evaluation | High | Medium | J10/J16/J25. Requires point-in-time operational labels; calibrate seasonality and multiple testing. |
| 5 | Continuous control tests with explicit populations and exception evidence | High | Medium-high | J27. Define actual controls/tests and sampling; do not treat review metadata as test outcomes. |
| 6 | Approved policy/document retrieval with document/version/page citations and access filtering | High | Medium-high | J23/J31. Evaluate retrieval recall, citation fidelity and injection resistance; never fabricate regulatory coverage. |
| 7 | Service/third-party resilience mapping, impact tolerances and exercise evidence | High | High | J10/J25 plus DORA context. Needs verified services/contracts/dependencies and specialist legal mapping. |
| 8 | Governed AI/model inventory and use-case intake with explicit human gates | High | Medium | J13/J16/J18/J32. Keep regulatory classification with qualified reviewers. |
| 9 | Quantitative challenger models, repeated temporal evaluation and parameter uncertainty | Conditional high | High | J07/J19/J23/J33. Requires sufficient representative data; compare negative-binomial/tail choices before complex ML. |
| 10 | NLP incident triage and proposed taxonomy labels with abstention | Medium-high | Medium | J23/J31. Requires independently labelled, de-identified incident narratives and a reviewer workflow. |
| 11 | Multi-agent/agentic orchestration | Unproven incremental value | High | J11/J23/J31. Benchmark against the existing single-agent system before adding orchestration or autonomy. |

Business priority does not override release gates: production access/privacy controls and approved data treatment must precede any institutional pilot.
