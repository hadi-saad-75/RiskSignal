# Research Extensions

Five research questions that the RiskSignal prototype is built to make precise, but deliberately does **not** answer.

> **No results are claimed in this document.** Every statement of the form "X may improve Y" is a hypothesis. The prototype uses synthetic data, contains **no predictive model** and no hidden prediction label (KRIs are displayed only), so it provides no evidence about any of these questions. Answering them requires genuine Operational Risk data, Operational Risk expertise and institutional context. The surrounding work (data, taxonomy, baseline modelling, validation, security) is laid out in [institutional_validation.md](institutional_validation.md).

---

## 0. The central question, and how it is split

The project's central open question is:

> *Can modern AI and machine learning improve early identification of deteriorating Operational Risk conditions when combined with classical frequency-severity modelling?*

It is too broad to test as stated. It splits into five questions, each with its own data, design and criteria:

| # | Question (short) | Depends on |
|---|---|---|
| RQ1 | Can KRIs and operational signals estimate a time-varying incident intensity λ(t), and does that improve early identification of deteriorating conditions? | Data foundation, baseline model |
| RQ2 | Can tabular foundation models improve early-warning performance over statistical and gradient boosting approaches? | The dataset and evaluation protocol from RQ1 |
| RQ3 | Can system and vendor dependency information improve identification of concentrated or propagating risk? | Verified dependency data; the dataset from RQ1 |
| RQ4 | Can NLP extraction from incident narratives produce useful quantitative signals? | Incident narratives; the dataset from RQ1 |
| RQ5 | Can an evidence-grounded agent reduce investigation time without reducing analytical quality or control? | The tool layer; real analysts and tasks |

RQ1 is the foundation: it defines the data panel, the target, the baselines and the validation protocol that RQ2, RQ3 and RQ4 reuse. RQ5 is largely independent of the others.

---

## 1. Principles that apply to every question

1. **Baselines first.** Every comparison includes the simplest credible alternatives: a constant-rate model per system, the system's recent trailing rate, a seasonal or trend model, and a simple KRI threshold rule. A complex method must beat these, after tuning them as carefully as itself.
2. **Time-ordered evaluation.** Fit on the past, evaluate on the future, with a gap between the two. Rolling-origin evaluation to use scarce data efficiently. Random shuffling of observations is not acceptable.
3. **No look-ahead.** Features use only information that would have been available at prediction time (including the publication lag of each KRI, and the values *as originally published*, not as later restated). Free-text narratives written after the event must be treated with particular care.
4. **A written analysis plan before looking at test data.** Targets, features, models, tuning budget, metrics, comparison tests and decision criteria are fixed in advance. Everything else is labelled exploratory.
5. **Uncertainty everywhere.** Confidence or credible intervals on every metric; resampling blocks of time and clustering by system, since observations are not independent.
6. **Power before effort.** Operational Risk events are few. Estimate by simulation, before any modelling, how large an improvement could be detected with the available number of events. If the study cannot detect a useful effect, say so and redesign.
7. **Multiple comparisons.** Count every model, feature set and horizon tried; adjust or report accordingly.
8. **Negative results are results.** "No improvement over the baseline at this granularity" is a legitimate and useful finding. Success and failure criteria are stated up front.
9. **Reproducibility and governance.** Seeded, versioned, logged; data access, confidentiality and model risk rules respected from the start.
10. **Use-oriented metrics.** A statistical gain matters only if it changes what an analyst can do with limited capacity. Include alert volume, lead time and review burden.

### What synthetic data can and cannot do here

Synthetic data **cannot** answer any of the five questions: they are statements about real organisations. They **can** be used, with a known data-generating process, to test code and pipelines, to check leakage controls, to confirm that an estimator recovers a planted effect, and to run the power simulations in principle 6. The RiskSignal data are not suitable for that purpose as they stand, because by design they contain no planted signal linking KRIs to future incidents.

---

## 2. RQ1: KRIs and operational signals for a time-varying intensity λ(t)

> **Can current KRIs and operational signals be used to estimate a time-varying incident intensity λ(t), and does this improve early identification of deteriorating Operational Risk conditions?**

### Why it matters

The prototype's frequency model assumes a constant rate per system, estimated from history. In practice conditions change: release cycles, staffing, vendor performance, backlogs and control lapses all vary. If leading indicators carry information about the near-future incident rate, an analyst could focus attention before losses arrive, which is what KRIs are meant to do but are rarely tested for. If they carry none, that is also worth knowing, because KRI monitoring costs effort.

### Formulation

For system *s* and period *t* (for example a month), let N(s,t) be the number of incidents and e(s,t) the exposure (for example days in the period). A simple family of models is

N(s,t) ~ Poisson( e(s,t) · λ(s,t) ),  log λ(s,t) = α(s) + f( x(s,t−h) ),

where x holds KRIs and other signals observed at least *h* periods before, α(s) is a system effect (fixed, or random with shrinkage), and *f* ranges from linear to flexible. Negative Binomial variants handle over-dispersion. The constant-rate baseline is f = 0.

Two target definitions should be evaluated, because they answer different questions:

- **Count forecasting**: the distribution of next-period incident counts (and, as a second stage, losses).
- **Deterioration onset**: a binary event such as "the system enters an elevated-incident period over the next *h* months", where *elevated* is defined together with analysts (for example relative to a system's own trailing baseline, or by materiality).

### Data required

- A **system-period panel** of incidents (dates, systems, materiality, losses where available) over several years, with the definitions of section 6 of the validation roadmap fixed.
- **KRIs and operational signals** at the same granularity, stored **point in time**: as published, with publication dates. Candidates, to be chosen with experts and fixed in advance: failed-change and deployment rates, downtime, backlog of overdue patches or control actions, control exceptions, near-miss counts, vendor service-level breaches, capacity measures, staffing and change-volume indicators.
- **Control information**: test results, overdue reviews.
- **Metadata**: criticality, technology stack, ownership, planned changes.
- Care with **circular KRIs**: some real KRIs are computed from incident data (a vendor incident count would be), so their relation to future incidents may reflect recording processes rather than leading information. (In the prototype the synthetic KRI values are generated independently of the incident table, which is another reason they cannot support this question.)

### Evaluation

- **Protocol**: rolling-origin evaluation with a purge gap; nested tuning inside each training window.
- **Probabilistic accuracy**: out-of-sample log-likelihood or Poisson deviance (proper scoring rules), compared across models with a time-block bootstrap or a Diebold-Mariano-type test with appropriate dependence adjustment, clustered by system.
- **Calibration**: predicted versus observed counts across predicted-intensity bins; calibration slope and intercept.
- **Early identification** (for the onset target): ROC and precision-recall curves, precision and recall at a threshold set by analyst capacity (top-*k* systems per month), **lead time** distribution (time between the alert and the first qualifying incident), and **false alarm rate** (alerts per system-year not followed by a qualifying incident).
- **Ablations**: which signals matter; performance by criticality tier and by technology family; stability across periods.
- **Decision criteria written in advance**, for example a minimum improvement over the best baseline that exceeds its uncertainty and that practitioners agree would change their workload.

### Risks and open issues

Few events per system, non-stationarity (changes in KRI definitions or in recording practice), reverse causality (incidents trigger remediation that moves KRIs), selection of KRIs after the fact, and the difficulty of defining "deteriorating" in a way the business recognises.

### What the prototype does and does not provide

It provides the constant-rate baseline, deterministic simulation and provenance labelling. It does not contain a time-varying model, a panel of leading indicators with a real relation to incidents, or any evaluation of early warning.

---

## 3. RQ2: tabular foundation models for early warning

> **Can tabular foundation models improve early-warning performance relative to established statistical and gradient boosting approaches on genuine Operational Risk data?**

### Why it matters

Operational Risk panels are small, noisy, heterogeneous and have few events. Flexible machine learning methods can overfit in this regime; regularised statistical models are the usual defence. Tabular foundation models, such as TabPFN, are pretrained models that, as described by their developers, make predictions on a new small tabular dataset by in-context learning, without training a new model for each dataset. Whether that helps on this kind of data is **untested here** and is an empirical question. A rigorous answer, positive or negative, is useful to practitioners deciding where to invest.

### Hypotheses

- **H0**: after fair tuning of all methods, no tabular foundation model improves out-of-sample early-warning performance over the best of: a regularised Poisson or logistic model, and gradient boosting.
- **H1**: such a model improves performance, particularly with few training observations.

### Data required

The same system-period panel, target definitions and signals as RQ1, with enough history to vary the training window length. Ideally several event types and prediction horizons, to see whether any difference is systematic.

### Design

- **Competitors**: a transparent GLM (Poisson, Negative Binomial or logistic) with regularisation; gradient boosting (for example XGBoost) with a Poisson or logistic objective; optionally random forests; one or more tabular foundation models; and the RQ1 baselines.
- **Fairness**: identical features, identical time-ordered splits, an equal tuning budget per method, and multiple random seeds. Baselines are tuned seriously, not left at defaults. Post-hoc calibration applied identically to all.
- **Data efficiency**: performance as a function of training window length, to test the claim that foundation models help most with little data.
- **Practicalities to check for the specific model version**: limits on the number of rows and features, handling of count targets (which may require treating them as classification or binning), inference cost, determinism and version stability, licence and the ability to run entirely inside the institution's environment (confidential data must not be sent to an external service).

### Evaluation

The same metrics and tests as RQ1: proper scoring rules, calibration, precision and recall at capacity, lead time and false alarm rate, with uncertainty intervals and comparison tests that respect time dependence. Add **operational criteria**: compute time, reproducibility across runs and versions, and **explainability** to model validators (what can be said about why a system was flagged), since an opaque improvement may not be acceptable under model governance.

### Risks and open issues

Gains may be within noise given few events; results may not transfer across institutions or periods; tuning budget differences can create spurious winners; foundation model versions change; governance of externally pretrained models in a regulated setting is unsettled.

### What the prototype provides

Nothing predictive. It provides the discipline (seeded, reproducible evaluation) that a fair comparison needs.

---

## 4. RQ3: dependency information for concentrated or propagating risk

> **Can system and vendor dependency information improve identification of concentrated or propagating Operational Risk?**

### Why it matters

The prototype's motivating example: two payment systems share a vendor; one has incidents and the other does not, yet an analyst may still want to examine the second. Single-system analysis misses this. If dependency structure carries information about where incidents will cluster or spread, it could direct reviews and shape scenario design; if it does not, the effort of maintaining a verified dependency map has a different justification. Note that the prototype only *displays* structural overlap and simulates each system independently, so it demonstrates the reasoning, not its value.

### Sub-questions

1. **Concentration**: do structural concentration measures (for example the share of critical services depending on a vendor, or a concentration index across vendors) relate to the clustering of realised events and losses?
2. **Propagation**: after an incident at a vendor or upstream system, is the incident rate of its dependents higher than that of comparable non-dependents, and how fast does it decay?
3. **Early warning**: do graph-derived features add predictive value over system-level features (RQ1)?
4. **Aggregate loss**: does a model with common shocks through shared vendors give better-calibrated aggregate tail estimates than systems modelled independently?

### Data required

- A **verified, time-stamped dependency graph**: systems, business services, vendors and fourth parties, shared infrastructure, with snapshot history because the graph changes.
- **Vendor event records**: internal incidents attributed to vendors, vendor status notices and outages, with **root-cause attribution**, which is often missing or inconsistent.
- Dependency attributes: criticality, substitutability and recovery arrangements.
- The panel from RQ1, so that graph features can be compared with system-level features.

### Design and evaluation

- **Descriptive tests with proper nulls**: compare dependent versus non-dependent systems on incident co-occurrence, using permutation nulls that preserve each system's marginal rate and timing, and **graph-shuffled controls** (randomly rewired edges) to test whether the real structure matters at all.
- **Network-augmented models**: add features such as lagged incidents at neighbours or at shared vendors, and concentration measures, to the RQ1 models; evaluate **lift** in out-of-sample scores and in precision at capacity for "which dependents to review after an upstream or vendor event", including lead time and false alarms.
- **Point process models** with graph-restricted excitation (multivariate Hawkes or similar) against unrestricted and no-interaction versions; compare out-of-sample.
- **Aggregate loss**: a common-shock frequency model or copula for aggregate losses, compared against independence by backtesting the components and by sensitivity of tail metrics.
- **Graph noise sensitivity**: deliberately corrupt edges in simulation to estimate how much the value of the approach depends on map quality. Real dependency maps are incomplete and partly wrong.
- Advanced graph learning (for example graph neural networks) is considered only after simple network features have been evaluated, because propagation labels are scarce and such models are harder to explain and govern.

### Risks and open issues

Confounding by shared drivers not in the graph (a common change window, a shared network), vendor attribution noise, incomplete maps, rare events, and the temptation to read correlation as propagation. Hawkes-type self-excitation can arise from an unmodelled common cause.

### What the prototype provides

The graph structure, shared-vendor queries and the displayed "shared exposure" map. It does not provide time-stamped dependencies, edge attributes, propagation or common-shock models.

---

## 5. RQ4: NLP extraction from incident narratives

> **Can NLP extraction from incident narratives produce useful quantitative signals?**

### Why it matters

Much of what is known about an incident sits in free text: tickets, post-incident reviews, loss event descriptions. Structured fields are coarse, inconsistent and filled in late. If reliable signals can be extracted (root cause, affected component, vendor involvement, recurrence, control failure, human factors), they could improve classification, trend detection and early warning, and could reduce manual coding effort. If extraction is unreliable or adds nothing beyond the structured fields, the cost and the risk are not justified.

### Sub-questions

1. **Validity**: how well does extraction agree with careful human coding?
2. **Value**: do the extracted signals add out-of-sample predictive or explanatory power beyond structured fields (for example for loss severity class, recurrence within *h* days, escalation, or the RQ1 targets)?
3. **Timing**: are the narratives available early enough to be useful, or written long after the event?
4. **Stability**: do results hold across model versions, wording styles and teams?

### Data required

- A corpus of **real incident narratives** with identifiers, timestamps (creation and later edits) and linked structured outcomes (losses, duration, recurrence).
- A **human-labelled sample** produced with a written codebook, double annotation and measured inter-annotator agreement, which also gives the ceiling for any automatic method.
- Handling for **sensitive content**: names, client details, security-sensitive technical details. Processing must happen in an approved environment.

The prototype's incident descriptions are templated synthetic sentences, and its "deployment" flag is a simple keyword match. They cannot support this research.

### Design and evaluation

- **Methods compared**: keyword and rule baselines; classical text features with linear models; embedding-based classifiers; and large language model extraction into a fixed schema, with each extracted label accompanied by the **evidence span** that supports it.
- **Extraction quality**: precision, recall and F1 against the gold labels per field, agreement statistics, calibration of any confidence scores, and **evidence validity** (does the cited span actually support the label? This is the claim-level hallucination measure of RQ5 applied to extraction).
- **Downstream value**: with time-ordered splits, compare models using structured fields only against structured fields plus extracted signals, using the same proper scoring rules and capacity-based metrics as RQ1. Include an ablation by signal type.
- **Aggregation into quantitative signals**: for example the monthly count of incidents per root-cause class, share involving change or a vendor, or recurrence flags, which can then enter RQ1 models.
- **Leakage control**: narratives written after resolution contain outcome information; restrict to text available at the prediction time or analyse separately.

### Risks and open issues

Label noise, hindsight bias in narratives, confidentiality, changing writing practices, drift when tooling changes, and the need to keep a language model's extraction auditable.

---

## 6. RQ5: an evidence-grounded investigation agent

> **Can an evidence-grounded agent reduce investigation time without reducing analytical quality or control?**

### Why it matters

An investigation gathers incidents, KRIs, controls and dependencies from several systems and turns them into questions to pursue. This is repetitive. The prototype shows how an agent can be restricted to deterministic tools, with every number traceable and a log of every call. Whether such an agent actually saves time **and** keeps quality and control is an empirical question about humans using it. A tool that saves time but occasionally invents a control or lulls analysts into trusting it would be worse than none.

### Hypotheses

- **H1**: agent-assisted investigations take less time than the existing process.
- **H2**: their quality is **non-inferior** to the existing process by a margin set in advance.
- **H3**: the rate of unsupported or false claims, and the rate at which analysts fail to catch them, stay below thresholds set in advance.

### Data and setting

- Real investigation tasks, with a **gold standard**: findings established by past reviews, or **planted issues** (for example an overdue control, a shared vendor, a deteriorating KRI, a misleading incident description) added to a controlled environment.
- A pool of analysts with different experience; the actual institutional tools and data access; a rubric for quality developed with senior practitioners.
- A deployment inside the institution's approved environment (see section 11 of the validation roadmap), so that real data can be used.

### Design

- **Randomised crossover**: each analyst performs matched tasks both with and without the agent, with order and task assignment randomised; blinded graders score the outputs.
- **Primary endpoints**: time to completion; quality score (completeness against known findings, accuracy, usefulness of suggested questions), tested for non-inferiority.
- **Secondary endpoints**: claim-level **hallucination rate** by type (fabricated entities, wrong numbers, wrong attribution, unsupported inferences, verdict-like statements) with intervals; **evidence traceability** (share of claims an independent reviewer can trace to a tool call); **tool selection** quality against expected tool sets; **robustness** (injected instructions in data fields, requests for verdicts, repeated runs, model version changes); **automation bias** (seeded errors in agent output to see whether analysts catch them); detection performance of the built-in numeric grounding check; cost and latency.
- **Analysis**: mixed-effects models with random effects for analyst and task, effect sizes with intervals, sample size from a pilot-based power calculation, pre-registered plan.

### Risks and open issues

Learning and novelty effects, representativeness of tasks, analyst heterogeneity, drift in the underlying model (a regression suite must be rerun on every change), evaluation of individuals (the study should assess the tool, not rank analysts), and confidentiality of the data sent to any language model.

### What the prototype provides

The tool layer, the activity log, the grounding check and a mock-provider test harness. It provides **no evidence about live model behaviour or about any effect on analysts**: the live path has not been exercised against the real API, and no study has been run.

---

## 7. Supporting methodological questions

These are narrower and mostly belong to the model-development phase in [institutional_validation.md](institutional_validation.md), section 7. They feed the questions above or can be studied alongside them.

| Topic | Question | Where it connects |
|---|---|---|
| Over-dispersion | Is a Negative Binomial (or a mixture) a better description of incident counts than a Poisson, and does the answer depend on granularity? | Baseline for RQ1 |
| Heavy tails and EVT | Does a Generalized Pareto tail above a well-chosen threshold improve tail calibration, and how stable is its shape parameter? | Severity side of every aggregate-loss result |
| Event clustering | Is clustering explained by a time-varying intensity, by common causes (RQ3), or by self-excitation (Hawkes)? | RQ1, RQ3 |
| Control effectiveness | How should uncertainty about a control's effect be represented, and is a bounded distribution such as a Beta appropriate for the way effectiveness is defined? | Scenario analysis and any control-adjusted model |
| Parameter uncertainty | How much of the uncertainty in reported tail metrics comes from limited data? | All quantitative outputs |

---

## 8. Sequencing and a feasible first project

The five questions are ordered by dependency, not by attractiveness.

1. **Foundation (before any question)**: agree the intended use, taxonomy, incident definition and materiality; map and assess the data; reproduce a transparent frequency-severity baseline on real data with proper diagnostics. This stage is useful even if nothing else follows.
2. **RQ1** as the first research question, because it fixes the panel, the targets, the baselines and the evaluation protocol.
3. **RQ2, RQ3 and RQ4** as extensions on that foundation. They can be done in parallel by separate people, provided they share the protocol, so that results are comparable.
4. **RQ5** can start as soon as there are real investigation tasks and approved infrastructure, because it depends on the tools and not on RQ1 to RQ4.

For a **small, internship-scale collaboration** a reasonable scope is: the foundation stage, the baseline reproduction, and a pre-registered pilot of **one** question (most naturally RQ1 on a restricted set of systems), with an explicit power assessment and an honest report of whatever it finds. If data cannot leave the institution, the work can be done inside it; if only aggregates can be shared, the prototype's code is a starting point for the pipeline and tests (never for conclusions).

---

## 9. What this document is not

It is not a claim that any of the five questions has a positive answer, nor a promise that the effort will pay off. Several answers may well be "no, not with the data available". Its purpose is to state the questions precisely enough that real data and real expertise can settle them.
