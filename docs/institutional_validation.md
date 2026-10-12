# Institutional Validation Roadmap

What would have to change if an Operational Risk team at a large global bank wanted to evaluate RiskSignal seriously.

> **Status of this document.** It is a roadmap. It describes work that has **not** been done and **claims no results**. Where it says a method "could" or "may" help, that is a hypothesis to be tested on real data, not a finding. The prototype itself uses synthetic data and illustrative parameters, and nothing in it has been validated (see [technical_review.md](technical_review.md), section 7). The research questions that follow from this roadmap are in [research_extensions.md](research_extensions.md).

---

## 1. Positioning

RiskSignal is intentionally a **proof of concept**. It demonstrates:

- **architecture**: layered data, graph, model, tool, agent, API and dashboard, with strict one-way dependencies;
- **quantitative reasoning**: a transparent frequency-severity model, Monte Carlo simulation, tail metrics and verified mathematics;
- **agent orchestration**: an investigation agent that can only act through deterministic, read-only, traceable tools;
- **scenario mechanics**: explicit stress assumptions applied to a baseline with coupled random numbers;
- **software engineering**: reproducible, tested, documented, containerised.

It cannot answer the questions that matter most for a bank. Those need **real data, Operational Risk expertise and institutional context**, which no synthetic dataset can provide. That is not a weakness of the prototype; it is what defines the natural next research phase. The rest of this document is that phase, organised by area.

---

## 2. Start with the intended use

Validation effort depends on what decision the model supports. The first task with the institution is to fix the **intended use** in writing, because it determines the required rigour, the acceptable error and the governance tier. Examples:

| Intended use | What it implies |
|---|---|
| Investigation support for analysts (the use the prototype is built around) | The agent and tools matter most; quantitative outputs are context, not decisions. Lighter model governance, strong evidence traceability. |
| Scenario analysis and stress testing | Scenario design with experts, sensitivity and uncertainty reporting, clear separation of assumptions from estimates. |
| Early warning and monitoring | Predictive validation (lead time, false alarms, calibration), alert workflow design, operational ownership. |
| Management information on loss exposure | Calibration quality, stability, benchmarking, documented limitations. |
| Regulatory or economic capital | The strictest tier: full model risk governance, independent validation, supervisory expectations. Note that the regulatory framework for operational risk capital has moved toward standardised, non-model-based approaches, so which uses remain relevant for an internal stochastic model must be confirmed with the institution's regulatory specialists for each jurisdiction. |

The prototype makes **no regulatory capital claim** and should not be used for any of the above in its current form.

---

## 3. What carries over and what must be replaced

| Carries over (pattern or code) | Must be replaced or rebuilt |
|---|---|
| The layered architecture and the one-way dependency rules | All data (the synthetic Atlas Bank) and its constructed demonstration story |
| The deterministic, typed, read-only tool layer and its error model | Every parameter: λ, μ, σ, the fallback thresholds (5 incidents, 15 losses), scenario multipliers |
| Provenance labelling (observed, estimated, assumed, stressed, simulated) | The invented incident categories and severity labels (the severity label thresholds 25,000 / 250,000 / 2,500,000 are illustrative) |
| Seeded, reproducible simulation, exact tail estimators and the tests that guard them | The model form: Poisson and Lognormal are starting points, not conclusions |
| Coupled baseline versus stress comparison | The scenario catalogue, which must come from experts |
| The grounding check, the activity log, the mock-provider test harness | The agent's prompt and evaluation, which must be tested against the institution's own tasks |
| Docker packaging, API and dashboard structure | Authentication, authorisation, logging, deployment and integration (section 11) |

---

## 4. Roadmap at a glance

Phases are ordered by dependency, not by duration. Each ends in a **gate**: a decision, made with the institution, about whether to continue and in what form. Durations are deliberately not given, because they depend on data access and organisation.

| Phase | Content | Gate (decision) |
|---|---|---|
| 0. Scoping | Intended use, stakeholders, data access route, governance tier, success criteria written down in advance | Is there a use case worth the effort, and is data access feasible? |
| 1. Data | Mapping, extraction, quality assessment, bias assessment (section 5) | Is the data good enough to model? Which questions can it support? |
| 2. Domain alignment | Taxonomy, incident definition, materiality, scenario catalogue, control framework (section 6) | Do the model entities mean what the business means? |
| 3. Baseline reproduction | Re-estimate the simple frequency-severity model on real data, with proper diagnostics (section 7) | Does a simple, transparent baseline survive contact with real data? |
| 4. Model development | Overdispersion, time variation, truncation, tails, dependence, scenarios, control uncertainty (section 7) | Which extensions are supported by evidence, not just by fashion? |
| 5. Validation | Backtesting, out-of-sample tests, sensitivity, stability, benchmarking, documentation (section 8) | Is the model fit for the agreed intended use, and what are its limits? |
| 6. Research | Predictive and AI questions on a validated data foundation (section 9, [research_extensions.md](research_extensions.md)) | Did the pre-registered comparison show value over the baselines? |
| 7. Agent evaluation | Time saving, quality, hallucination, traceability, oversight (section 10) | Does the agent help analysts without reducing quality or control? |
| 8. Production readiness | Security, governance, integration (section 11) | Can it run in the institution's approved environment? |

Phases 6 and 7 are research. A negative result there is a valid and useful outcome.

---

## 5. Data

### 5.1 Mapping from the prototype to real sources

The prototype has seven tables. Each corresponds to something real that is far messier.

| Prototype entity and fields | Real counterpart | Questions to resolve |
|---|---|---|
| **Incidents** (`incident_id`, `date`, `system_id`, `category`, `description`, `financial_loss`, `severity`) | The operational loss event database, plus IT incident and problem management records, plus finance ledger postings | Which system of record is authoritative? How are event, loss entry and incident related (one event, many loss entries, many incidents, one root cause)? Which date is `date`: occurrence, discovery, reporting or accounting? One system per incident, or many? Is there a root-cause field, or only free text? |
| **Financial losses** (`financial_loss`, one number, no currency) | Loss amounts by component | Gross or net of recoveries and insurance? Direct costs, remediation, customer compensation, fines, write-offs, and are lost revenue and opportunity costs excluded? Currency, inflation and exchange-rate treatment? Time development: is a loss still being updated months after the event? Are zero-loss events and near misses recorded? |
| **KRIs** (`date`, `system_id`, `kri_name`, `value`; five indicators; monthly) | The institution's KRI library and its metric repositories | Definition, numerator and denominator, owner, frequency, thresholds and history of changes to the definition. Is the KRI measured independently of incidents, or partly derived from them (a vendor incident count would be)? When is each value actually available (publication lag)? |
| **Controls** (`control_id`, `name`, `control_type`, `system_id`, `last_review_date`, `review_status`) | The control inventory in the governance, risk and control tool, with test results and issue records | Design versus operating effectiveness ratings, test dates and results, control owners, mapping of controls to risks, processes and systems (many to many in reality, one system per control in the prototype), key versus non-key controls, compensating controls. The prototype's review status is derived only from a review date and an annual cycle; real status comes from the testing programme. |
| **Systems** (`system_id`, `name`, `criticality`, `primary_process_id`) | The configuration management database and application inventory | Granularity (application, service, component), ownership, lifecycle, criticality tiers and who assigns them, completeness and staleness of the CMDB. |
| **Business processes** (`process_id`, `name`) | The process inventory and business service catalogue, including important business services and their impact tolerances where the institution defines them | Process-to-system mapping granularity, many-to-many relations, mapping owners and refresh cycle. |
| **Vendors and dependencies** (`dependencies`: `SUPPORTS`, `DEPENDS_ON`) | The third-party risk management inventory, contracts, architecture and data-flow documentation, cloud and network topology | Verified, current dependencies including subcontractors (fourth parties), shared cloud regions and shared network providers. Dependencies change over time, so the graph needs history. Criticality and substitutability of each dependency, none of which the prototype models. |

### 5.2 Assessing missing data

- **What is absent altogether**: no near-miss database, no control test results, no KRI history for newer systems, no vendor outage history, no free-text narratives.
- **What is absent selectively**: small losses below a collection threshold, events never reported, systems with no incidents (genuinely safe, or not monitored?).
- **Handling**: document every gap and its likely direction of bias before modelling; do not impute silently; where imputation is unavoidable, report sensitivity of results to it. A model that estimates λ from "systems with at least 5 incidents" (as the prototype does) must first know *why* other systems have few.

### 5.3 Assessing data quality

Assess each source against explicit dimensions, with measurable checks and owners:

| Dimension | Example checks |
|---|---|
| Completeness | Share of incidents with a loss amount, a system, a date, a root cause; share of systems with KRIs |
| Accuracy | Reconciliation of losses to the finance ledger; sampling of records against source documents |
| Timeliness | Lag between occurrence, recording and loss finalisation; KRI publication lag |
| Consistency | Same event described consistently across systems; taxonomy used the same way by all teams |
| Uniqueness | Duplicate events; one event split across several records |
| Validity | Dates in range, amounts positive and in the right currency, valid identifiers |
| Lineage | Where each field comes from, who changed it, and when (needed for audit and for the leakage controls below) |

### 5.4 Historical observation bias

Real loss and incident histories are not random samples of what could happen. Each bias below would distort the prototype's estimators if ignored.

| Bias | Effect | What to do |
|---|---|---|
| **Collection threshold (left truncation)**: events below a threshold are not recorded | Fitting a Lognormal to recorded losses as if they were complete biases the body and, through it, the aggregate. The prototype performs no truncation adjustment. | Truncated or shifted likelihoods; document thresholds and their history, which often changed over time |
| **Under-reporting** and reporting culture | Frequency understated, especially for small, embarrassing or human-error events | Compare sources (IT tickets versus loss database); examine counts around policy or culture changes |
| **Changing reporting practice or definitions** | Spurious trends in λ; breaks in the series | Identify structural breaks; model them rather than averaging across them |
| **Right censoring and loss development** | Recent events have incomplete losses | Use development factors or exclude immature periods |
| **Survivorship**: decommissioned systems and merged entities drop out | Historical risk of today's estate is misestimated | Keep the history of the estate, not only its current state |
| **Controls and mitigation shape what is observed** | Observed frequency reflects past control quality, not exposure | Do not treat history as exposure without modelling control change |
| **Rare, severe events are absent from short histories** | Tails are extrapolated from almost nothing | Scenario analysis, external data, expert judgement (section 7) |
| **Look-ahead and label leakage** in any predictive work | Overstated predictive performance | Use only information available at prediction time, with time-ordered splits (section 9) |
| **Selection of KRIs after the fact** | KRIs that look good were chosen because they fit history | Fix the KRI set before testing, or test out of sample |

---

## 6. Domain expertise

Operational Risk professionals must define what the data mean. Software cannot decide this.

- **Taxonomy.** Align with the institution's Operational Risk taxonomy and, where relevant, the Basel event-type categories (internal fraud, external fraud, employment practices and workplace safety, clients, products and business practices, damage to physical assets, business disruption and system failures, execution, delivery and process management). The prototype's five categories (technology failure, process failure, third-party failure, human error, cyber event) are invented for the demonstration and **do not correspond to any institutional taxonomy**. Real events often fall in several categories or have several causes.
- **What constitutes an incident.** Operational incident, loss event, near miss, control breach, issue and resilience event are different things with different owners and data sources. Decide which the model counts, and keep the definition stable.
- **Materiality thresholds.** What is recorded, what is escalated, what enters the model. These thresholds also determine the truncation point in section 5.4.
- **Relevant risk scenarios.** A catalogue of plausible, severe, institution-specific scenarios (for example failure of a critical payment vendor, a failed major release, a cyber event affecting a shared platform), written as narratives first and quantified second, with experts from risk, technology, vendor management and the business.
- **Existing controls and risk processes.** How risk and control self-assessments, key risk indicator governance, issue management, loss data collection and scenario workshops work today. A tool that duplicates or contradicts these will not be adopted. Learn the process before proposing to change it.
- **Language and meaning.** Terms such as "critical system", "overdue control" and "shared vendor" have precise institutional definitions that the prototype only approximates.

Suggested forum: a small working group of Operational Risk analysts, a technology risk owner, a vendor-risk owner and a model-risk contact, meeting on a fixed schedule, with decisions and open questions recorded.

---

## 7. Stochastic modelling

For every topic the same discipline applies: **state the question, diagnose on real data, change the model only if the diagnostics justify it, and keep the simpler model as a benchmark.**

| Topic | Question | What the prototype does | Approach on real data | Diagnostics |
|---|---|---|---|---|
| **Poisson frequency** | Is a Poisson count adequate? | Constant rate λ per system, estimated as count divided by years; independent arrivals | Compare observed count distribution with Poisson at several granularities (system, business line, month, quarter) | Dispersion index, goodness-of-fit and likelihood-ratio tests, rate stability across sub-periods |
| **Overdispersion** | Is the variance larger than the mean? | Not tested (the synthetic data are Poisson by construction) | Negative Binomial (a Gamma-mixed Poisson) and other mixtures; zero-inflated variants if justified | Compare information criteria and out-of-sample log-likelihood, not only in-sample fit |
| **Frequency through time** | Does the rate change (trend, seasonality, regime shifts, release cycles)? | None | Non-homogeneous Poisson with a time-varying intensity; change-point analysis; covariates (see [research_extensions.md](research_extensions.md), question 1) | Trend and change-point tests; rolling re-estimation; residual analysis |
| **Severity calibration** | Which severity family fits, and with what parameters, for which segment? | One Lognormal per system or fallback; maximum likelihood; no truncation; thresholds of 15 losses | Candidate families (Lognormal, Weibull, Gamma-type, log-based heavy-tailed families); truncated likelihood for the collection threshold; segmentation by event type | QQ plots, Anderson-Darling-type tests that weight tails, comparison of fitted and empirical large quantiles |
| **Heavy tails** | Is the tail heavier than the body family implies? | A single Lognormal for the whole distribution | Inspect tail behaviour with mean-excess and stability plots | Mean residual life plot, Hill-type tail-index plots, threshold sensitivity |
| **Extreme Value Theory** | Can the tail beyond a threshold be modelled by a Generalized Pareto distribution? | Not implemented | Peaks over threshold with a Generalized Pareto tail, spliced to a body; pooling across comparable units to get enough tail observations | Threshold stability of the shape parameter, confidence intervals on it, sensitivity of Expected Shortfall to it. If the shape is at or above 1 the mean is infinite, and at or above 1/2 the variance is, with direct consequences for tail metrics. |
| **Dependence between event categories** | Do categories, systems and vendors fail together? | Each system simulated alone; no dependence | Common-shock or common-factor frequency models; correlated intensities; copulas for severities or aggregate losses by category | Empirical dependence between counts and between large losses across categories and time; sensitivity of aggregate tail metrics to the dependence assumption |
| **Stress scenarios** | What are plausible severe scenarios and what parameters do they imply? | Three explicit illustrative numbers (λ multiplier, μ shift, σ multiplier) | Structured expert elicitation (ranges and quantiles with challenge, several experts, recorded rationale) translated into parameter changes or into explicit scenario losses; link to the real dependency map for shared vendor events | Sensitivity of results to each elicited input; reasonableness checks against internal and external events |
| **Control effectiveness** | How uncertain is the benefit of a control, and how should that uncertainty enter the model? | Controls are displayed only; they do not change λ or severity | Represent a control's effect as a reduction in frequency or severity with an uncertain factor. A Beta distribution is conceptually natural for a proportion bounded between 0 and 1 (for example the share of events a control prevents), elicited as a mean and a concentration. Whether it is appropriate depends on what "effectiveness" is defined to mean, on evidence from control testing, and on dependence between controls. | Compare with simpler treatments (a fixed factor, scenario cases); examine how much the aggregate result depends on the effectiveness distribution |
| **Parameter uncertainty** | How much of the reported tail is due to estimation error? | Ignored (parameters treated as known); the technical review argues that this is the dominant error for the focal system | Parametric or non-parametric bootstrap, or a Bayesian treatment with informative priors from experts or consortium data | Intervals on every reported metric; the decomposition of total variability into sampling error, parameter uncertainty and model uncertainty |

Further modelling decisions that need institutional input: aggregation across systems and business units (and the assumption on diversification), the treatment of insurance and recoveries, the modelling horizon, and whether the model is for expected annual loss, tail measures or scenario narrative. The use of Hawkes processes for clustering is a research topic and is discussed in section 9.

---

## 8. Validation

Validating the **software** (does it implement the stated mathematics correctly?) is largely done in the prototype: see the tests and [technical_review.md](technical_review.md). Validating the **model** (does it describe reality well enough for its use?) is what remains, and it needs real data.

| Activity | What it answers | Limits to expect |
|---|---|---|
| **Backtesting** | Did realised frequency, individual losses and (where possible) annual aggregates fall where the model said they would? | Annual aggregate backtests have very little power. At the 99% level, ten annual observations give 0.1 expected exceedances. Backtest the components instead (counts per period, severities against the fitted distribution, probability integral transforms) and report power honestly. |
| **Out-of-sample testing** | Does the model perform on data it was not fitted on? | Needs time-ordered splits (fit on the past, test on the future), and enough events in the test period. Rolling-origin evaluation uses data more efficiently. |
| **Sensitivity analysis** | Which inputs and assumptions drive the results? | One-at-a-time and global methods over distribution family, threshold, window length, truncation, dependence, scenario inputs. Report as ranges, not single numbers. |
| **Parameter uncertainty** | How wide is the plausible range of each reported metric? | Bootstrap or posterior intervals (section 7). |
| **Stability analysis** | Do estimates and conclusions move when the window, the data cut or the method changes slightly? | Rolling re-estimation; compare tail parameters across windows; unstable tails argue against precise tail statements. |
| **Benchmarking** | Is the model better than simple and independent alternatives? | Challenger models (the simple prototype baseline, empirical bootstrap of historical losses), consortium or external loss data where licensed, expert judgement, peer practice. |
| **Model governance** | Is the model inventoried, tiered, independently validated, monitored and change-controlled? | Follow the institution's model risk policy and applicable supervisory expectations (for example the US SR 11-7 guidance and equivalent frameworks elsewhere, such as the PRA's model risk management principles). |
| **Documentation** | Can an independent party understand, reproduce and challenge the model? | Model development document, data lineage, assumptions and limitations register, validation report, ongoing monitoring plan, use restrictions. The prototype's documentation shows the intended style (plain language first, then equations). |

Principles: independent validators who did not build the model; pre-defined acceptance criteria; findings recorded with owners and deadlines; a limitations register that travels with every output.

---

## 9. AI and machine learning research

This section **describes** research directions. **No results are claimed**, and the prototype contains no predictive model: its KRIs are displayed as evidence and are not used for estimation. The formal questions, with data requirements and evaluation designs, are in [research_extensions.md](research_extensions.md).

| Direction | Description |
|---|---|
| **Time-varying intensity λ(t) from KRIs** | Estimate the incident rate as a function of current and recent KRI values (and other signals), instead of a constant. Compare with the constant-rate baseline and with seasonal and trend baselines. |
| **Model comparison** | Compare a transparent baseline (Poisson or logistic regression), gradient boosting (for example XGBoost) and tabular foundation models (for example TabPFN) under identical data, features, splits and metrics, with tuned baselines, on genuine Operational Risk data. |
| **NLP signals from incident narratives** | Extract structured signals (root cause, affected component, vendor mentions, recurrence, control failure references) from free text, and test whether they add predictive or explanatory value. |
| **Dependency information** | Test whether features from the verified dependency graph (shared vendors, upstream incidents, concentration) improve early identification of concentrated or propagating risk. |
| **Event clustering** | Test whether events cluster beyond what a time-varying Poisson or a Negative Binomial explains, for example with Hawkes (self-exciting) processes, being careful not to mistake a shared external cause for self-excitation. |
| **Advanced graph methods** | Only after simple network features have been evaluated: graph embeddings or graph neural networks, which need labelled propagation examples that are scarce and which are harder to explain and govern. |

**Evaluation measures** (to be defined precisely, and agreed with the institution before any model is run):

- **Lead time**: how many days or weeks before an incident an alert was raised, and how that distribution compares with baselines.
- **False alarm rate**: alerts per system per period that were not followed by an incident, and their cost in analyst effort.
- **Precision and recall** at the alert threshold, and at a threshold set by analyst capacity (for example the top-k systems per month).
- **Calibration**: whether a predicted probability or expected count matches what is observed (calibration curves, proper scoring rules such as the log score or Brier score).
- **Comparison with baselines**: always including the constant-rate model, "last period's count", and a simple KRI threshold rule.

**Methodological safeguards:** time-ordered splits with a gap between training and test periods; features restricted to information available at prediction time; fixed analysis plan written before looking at test results; control for multiple comparisons when many models and features are tried; uncertainty intervals on every metric; honest treatment of the small number of events typical in this domain.

---

## 10. Agent validation

The prototype shows that an evidence-grounded agent can be built and audited. Whether it **helps** is an empirical question about real analysts and real tasks, and it has not been investigated. The live model has not even been run against the real API in development.

| What to evaluate | Possible design | Measures |
|---|---|---|
| **Does it save analyst time?** | Within-subject comparison on matched investigation tasks: manual process versus agent-assisted, order randomised, realistic data access | Time to a completed investigation; time to first useful finding; analyst effort and perceived workload |
| **Are the suggested questions useful?** | Blinded rating of questions by experienced analysts against a rubric, compared with questions written by analysts without the tool | Relevance, specificity, novelty, actionability; share of questions an analyst would actually pursue |
| **Hallucination rate** | Decompose each answer into atomic claims and label each as supported by a tool output, unsupported, wrongly attributed or contradicted; repeat across many tasks and several runs | Rate of each type with confidence intervals; separate rates for numbers, entities, relations and verdict-like statements; the precision and recall of the built-in grounding check as a detector |
| **Evidence traceability** | Ask an independent reviewer to reconstruct each claim from the logs only | Share of claims traceable to a specific tool call; replayability of every call |
| **Appropriate tool selection** | A set of tasks with expected tool sets, from narrow questions to full investigations | Missing tool calls, unnecessary calls, repeated calls, recovery after tool errors |
| **Human oversight** | Define the review and sign-off step; observe how analysts use the output | Rate of analyst corrections; automation bias (do analysts accept wrong statements?); override and escalation behaviour |
| **Auditability** | Review of retained records by internal audit or model risk | Completeness of logs (question, model version, prompt version, tool calls and results, answer, reviewer), integrity, retention, access control |
| **Robustness** | Planted issues (an overdue control, a shared vendor), adversarial and injected text in data fields, requests for verdicts, repeated runs, model version changes | Detection of planted issues; refusals of out-of-scope requests; stability across runs and versions; a regression suite re-run on every model or prompt change |
| **Quality without loss of control** | Pre-specify a non-inferiority margin for investigation quality | Quality scores of agent-assisted versus manual work; missed findings; incidents of unsupported claims reaching a final document |

Acceptance thresholds must be set with the institution **before** the evaluation, not inferred afterwards. A failed hallucination or oversight criterion should block production use regardless of the time saved.

---

## 11. Security and production

A production implementation would need everything the prototype deliberately omits.

| Area | Required |
|---|---|
| **Identity and access management** | Integration with the institution's single sign-on and multi-factor authentication; service identities for system-to-system access |
| **Permissions** | Role- and attribute-based access aligned with data classification and need-to-know (loss data, legal matters and some incidents are highly restricted); per-user entitlements enforced inside the tool layer so that the agent cannot see what the user cannot |
| **Data confidentiality** | Data minimisation; classification and handling rules; encryption in transit and at rest; no use of real data outside approved environments; controls on what leaves the institution |
| **Audit logging** | Immutable, centralised records of who asked what, which tools ran with which inputs and outputs, which model and prompt versions were used, and what was returned; retention per policy |
| **Model governance** | Inventory entries for the loss model **and** for the AI components; versioned prompts, tools and models; change control; ongoing monitoring; periodic revalidation |
| **Secure LLM deployment** | Only approved models and endpoints; contractual and technical assurance about data retention and training use; private or in-region deployment as required; defences against prompt injection from free-text data; output controls; rate limits; secrets management. The prototype's call to a public API with synthetic data is acceptable only because the data are synthetic. |
| **Approved infrastructure** | Hosting in the institution's approved platforms; hardened images and dependency and vulnerability management; resilience, backup and recovery; monitoring and support model |
| **Integration** | Read-only integration with the loss database, risk and control tool, configuration management database, third-party risk system and incident tooling through supported interfaces; reconciliation to systems of record; handling of refresh and staleness (the prototype caches its graph and context for the process lifetime) |
| **Operational** | Capacity and cost controls for simulations and model calls; service levels; user training; a process for reporting and handling incorrect outputs |

The prototype's current gaps in this area are listed in [technical_review.md](technical_review.md), section 5 (no authentication or rate limiting, process-lifetime caches, localhost-only publishing in the Docker setup).

---

## 12. Conclusion

RiskSignal is a proof of concept, built to be inspected. It shows how an investigation agent can be constrained to deterministic tools, how a transparent frequency-severity model and coupled stress comparison can be implemented and checked, and how a prototype can be made reproducible, tested and honest about what it is.

The most valuable questions are the ones it cannot answer: whether the model forms fit real losses, whether KRIs and dependency information give earlier warning, whether narratives carry usable signal, whether the agent saves time without lowering quality. Each needs **real data, Operational Risk expertise and institutional context**. The gaps are not hidden flaws; they mark where a collaboration with an Operational Risk team begins, and the phases above are one way to organise it.
