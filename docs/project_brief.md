# RiskSignal — Project Brief

> **Canonical reference for all development steps.**
> If you are a future session with no memory of earlier conversations, read this file in full before writing or changing anything. It defines what RiskSignal is, what it is **not**, and what should and should not be built.
> If a task conflicts with this brief, stop and ask rather than silently deviating.

---

## 1. Project purpose

**RiskSignal** is a compact but technically serious **research prototype**: an *agentic Operational Risk investigation and stochastic scenario tool* for **technology-related Operational Risk**.

*Operational Risk* means the risk of financial loss or operational disruption caused by failures in people, processes, technology systems or external events. Typical technology-related examples: software outages, failed deployments, vendor failures, human errors, cyber incidents and control failures.

RiskSignal combines:

- synthetic Operational Risk data,
- a simple dependency graph,
- classical stochastic Operational Risk modelling (frequency–severity),
- Monte Carlo simulation,
- an AI investigation agent,
- a REST API,
- a simple dashboard.

Its purpose is to **demonstrate capability** — quantitative modelling, applied mathematics, AI and software engineering — to an Operational Risk team. It is a portfolio / conversation-opening artefact, not a production system and not a product.

The prototype should be able to support questions such as:

- "Investigate PAYMENT_ENGINE_01."
- "What incidents recently affected this system?"
- "What business processes depend on it?"
- "Which external vendors does it depend on?"
- "Which other systems share those vendors?"
- "What controls protect the system?"
- "What could the annual financial loss distribution look like under the current modelling assumptions?"
- "What happens under a stressed vendor outage scenario?"
- "What questions should an Operational Risk analyst investigate?"

---

## 2. Target audience

The author is a recent Master 2 graduate (Applied Mathematics, Artificial Intelligence and Data Science) who previously passed the recruitment process for an Operational Risk Management role at a major global bank but could not join for a university-related reason. The prototype is meant to **reconnect with that Operational Risk team** by showing what the author could contribute, and may later support a discussion about an internship or research-oriented project.

Expected reviewers:

1. **Senior Operational Risk professionals** — they care about clarity, relevance to real Op Risk practice, honesty about limits and sensible governance.
2. **A technically and quantitatively oriented Operational Risk professional** with experience in Monte Carlo simulation, Poisson processes, loss distributions and tail risk — they will scrutinise the mathematics.

Consequence for every design decision: **mathematical correctness, intellectual honesty and explainability matter more than flashy AI.**

---

## 3. Operational Risk problem being addressed

Technology Operational Risk is analysed today with a mix of incident records, key risk indicators (KRIs), control inventories, dependency knowledge (systems, processes, vendors) and scenario analysis. Analysts face recurring difficulties:

- evidence is scattered across incidents, KRIs, controls and dependency maps;
- hidden **concentration** (e.g. several systems relying on the same vendor) is easy to miss;
- translating incident history into an *annual loss distribution* requires a transparent stochastic model;
- scenario / stress analysis needs to be reproducible and clearly separated from baseline assumptions;
- it is hard to know which questions to ask next.

RiskSignal demonstrates a workflow that **assembles the evidence, runs transparent classical models and suggests investigation questions for a human analyst** — without pretending to replace the analyst or the institution's models.

---

## 4. Final demo objective

The strongest demonstration (the "money shot"):

1. The user selects **`PAYMENT_ENGINE_01`** in the dashboard.
2. The user clicks **"Investigate"**.
3. The agent, by calling deterministic Python tools:
   - retrieves the system profile,
   - retrieves recent incidents,
   - retrieves KRIs,
   - retrieves controls,
   - queries technology and vendor dependencies,
   - identifies connected systems (e.g. systems sharing a vendor),
   - runs a **baseline** stochastic simulation,
   - optionally runs a **predefined stress scenario** (e.g. vendor outage),
   - produces an **evidence-based investigation summary**.

Conceptual shape of the output (illustrative only — **never hardcode these facts or numbers**; every one must be computed from the synthetic dataset and the simulation engine):

```
Observed evidence:
  Three recent incidents. Two involved deployment failures.
  One relevant control has an overdue review.
  PAYMENT_ENGINE_01 shares Vendor V04 with PAYMENT_ENGINE_02.

Model assumptions:
  Annual incident frequency is estimated from synthetic historical observations.
  Loss severity uses an illustrative Lognormal model.

Simulation results:
  Baseline P95 annual loss = <value returned by Python simulation>
  Vendor outage stress P95  = <value returned by Python simulation>

Suggested investigation questions:
  Has deployment governance deteriorated?
  Should the overdue control be retested?
  Does the shared vendor create concentration risk?
  Does PAYMENT_ENGINE_02 have similar exposure?
```

The demo has to be understandable in a few minutes by a non-technical senior risk professional, and defensible under questioning by a quantitative one.

---

## 5. System architecture

```
Synthetic Atlas Bank data
        ↓
SQLite
        ↓
Dependency graph (NetworkX)
        ↓
Stochastic risk engine
        ↓
Python tool layer
        ↓
AI investigation agent
        ↓
FastAPI backend
        ↓
Streamlit frontend
```

Layer responsibilities:

| Layer | Responsibility |
|---|---|
| Synthetic data | Deterministically generated fictional Atlas Bank dataset (seeded). |
| SQLite | Single-file storage of systems, processes, vendors, controls, incidents, KRIs and relationships. |
| Dependency graph | NetworkX graph built from SQLite; answers dependency / shared-vendor / process-impact queries. |
| Stochastic risk engine | Parameter estimation, frequency–severity Monte Carlo, risk metrics, stress scenarios. Pure Python/numpy/scipy; **no LLM dependency**. |
| Python tool layer | Small, typed, deterministic functions exposed to the agent (retrieve data, query graph, run simulation). Read-only. |
| AI investigation agent | Simple direct tool-calling loop behind a small LLM-provider interface. Orchestrates tools and writes the summary. |
| FastAPI backend | Thin REST layer over business logic. |
| Streamlit frontend | Simple dashboard; minimal UI logic. |

Boundaries that must hold:

- **Business logic is independent of the UI.** Streamlit and FastAPI only call into the core.
- **Stochastic calculations are independent of the LLM.** The risk engine must be importable and testable with no LLM and no network.
- **The rest of the software does not depend directly on Anthropic.** The LLM provider sits behind a small interface; a **mock LLM** implementation is provided for automated tests.
- No microservices; one repository, one Python package, one SQLite file.

---

## 6. Mathematical core

> Each concept is explained in plain language first, then formally.

### 6.1 Frequency — how many incidents in a year?

**Plain language:** In any given year we do not know exactly how many incidents will occur. We model the count as a random number whose average is λ (the expected number of incidents per year). A Poisson model assumes incidents arrive independently and at a steady average rate.

**Formal:** `N ~ Poisson(λ)`, where `N` is the number of incidents in one simulated year and `λ > 0` is the expected annual number of incidents. `E[N] = Var[N] = λ`.

### 6.2 Severity — how costly is each incident?

**Plain language:** Most incidents are small, a few are very expensive. The Lognormal distribution captures this: it is always positive and has a long right tail.

**Formal:** `X_i ~ Lognormal(μ, σ)`, i.e. `ln X_i ~ Normal(μ, σ²)`, independent and identically distributed, independent of `N`. `X_i` is the financial loss of incident `i`. `E[X] = exp(μ + σ²/2)`.

### 6.3 Annual aggregate loss

**Plain language:** The loss in a year is the sum of the losses of all incidents that happen that year (zero if none happen).

**Formal:** `L = Σ_{i=1}^{N} X_i`, with `L = 0` when `N = 0`. This is a *compound Poisson* distribution. Analytically, `E[L] = λ · E[X]`, which is useful as a **sanity check** on the simulation.

### 6.4 Monte Carlo simulation

**Plain language:** The distribution of `L` has no simple closed form, so we "live through" many hypothetical years on the computer: for each simulated year draw `N`, draw `N` severities, add them up. Repeating this e.g. 100,000 times gives an empirical picture of the annual loss distribution.

**Formal:** Generate `L^(1), …, L^(M)` i.i.d. from the model and use the empirical distribution to estimate risk measures. All simulation functions **must accept a random seed** and be deterministic given that seed (e.g. `numpy.random.default_rng(seed)`).

### 6.5 Risk measures to report

| Measure | Plain language | Formal |
|---|---|---|
| Mean annual loss | The average yearly loss across simulated years. | `E[L]` |
| Median annual loss | The "typical" year: half of years are better, half worse. | 50th percentile of `L` |
| 95th percentile (P95 / VaR 95%) | A loss level exceeded in about 1 year in 20. | `VaR_0.95 = inf{x : P(L ≤ x) ≥ 0.95}` |
| 99th percentile (P99 / VaR 99%) | A loss level exceeded in about 1 year in 100. | `VaR_0.99` |
| Expected Shortfall 95% (ES95) | The average loss in the worst 5% of years — says *how bad* things are once the P95 line is crossed. | `ES_α = E[L | L ≥ VaR_α]` |
| Expected Shortfall 99% (ES99) | The average loss in the worst 1% of years. | as above with `α = 0.99` |

Note for implementers: be explicit and consistent about the empirical ES estimator (mean of simulated losses at or above the empirical quantile), and state it in docs and docstrings. Tail estimates at 99% are noisy for small simulation counts; document the Monte Carlo standard error / number of simulations where relevant.

### 6.6 Provenance of numbers (a required code-level distinction)

The code and outputs must clearly distinguish five categories, and never blur them:

1. **Historical synthetic observations** — incidents, losses, KRIs in the generated dataset.
2. **Estimated parameters** — λ, μ, σ derived from those observations by a documented estimator.
3. **User-supplied assumptions** — parameters overridden by the user.
4. **Stress scenario assumptions** — predefined, explicitly labelled adjustments (e.g. vendor outage multipliers on frequency/severity).
5. **Simulation outputs** — metrics computed by the Monte Carlo engine.

Every result object should carry enough metadata (parameter source, seed, number of simulations, scenario name) so a reader can tell which category each number belongs to.

---

## 7. Agent role

RiskSignal's AI agent is the **visible centerpiece** of the demo, but it is an **investigation assistant, not an autonomous risk manager**.

The agent **may**:

- retrieve information (via tools),
- query dependencies (via tools),
- run simulations (via tools),
- compare scenarios,
- summarise evidence,
- suggest questions for human investigation.

The agent **may NOT**:

- modify risk records,
- make final risk decisions,
- claim a system is objectively safe or unsafe,
- invent incidents,
- invent controls,
- invent simulation outputs (or any other numbers),
- perform autonomous remediation.

Implementation approach: a **simple direct tool-calling loop** (no LangChain unless there is a compelling reason). The LLM is accessed through a small provider interface (Anthropic API for the live agent; mock implementation for tests).

When relevant, agent answers are structured in four sections:

1. **Observed evidence**
2. **Model assumptions**
3. **Simulation results**
4. **Suggested investigation questions**

---

## 8. Synthetic data philosophy

- The institution is the fictional **Atlas Bank**. Nothing represents a real bank, real incidents, real vendors or real losses.
- Data exist **only** to demonstrate software architecture, agent orchestration, quantitative modelling mechanics, dependency analysis and scenario analysis.
- Data must **never** be used to claim meaningful predictive accuracy or to draw conclusions about any real institution.
- Small and understandable, not large. Approximate target size:
  - ~20 systems,
  - ~10 business processes,
  - 8 vendors,
  - ~40 controls,
  - ~300 incidents,
  - 5 years of monthly KRI observations.
- Do **not** generate thousands of unnecessary entities. Scale is irrelevant; legibility is the point.
- A **payments ecosystem** is the focal case. The focal system is `PAYMENT_ENGINE_01`. The data must contain meaningful, discoverable relationships, including:
  - two payment systems sharing the same vendor (e.g. `PAYMENT_ENGINE_01` and `PAYMENT_ENGINE_02` sharing a vendor such as `V04`),
  - controls associated with those systems (including at least one with an overdue review),
  - several historical incidents for the focal system, including recurring causes (e.g. deployment failures),
  - KRIs that change over time (e.g. a deteriorating trend).
- Generation must be **deterministic** (fixed seed) so the demo, tests and docs are reproducible.
- Synthetic data may be *constructed to tell a story* for the demo; the documentation must say so openly. Findings are properties of the constructed dataset, not discoveries about the world.

---

## 9. Scientific limitations

These must be stated honestly in the README, UI and agent output wherever relevant.

- Synthetic data ⇒ **no empirical validity**. Results illustrate mechanics only.
- Model parameters (λ, μ, σ, stress multipliers) are **illustrative**.
- Poisson assumes independent arrivals at constant rate: no clustering, no time variation, no dependence between incidents or between systems. Real incidents cluster and are over-dispersed.
- Lognormal severity may badly understate extreme tails; no tail-specific modelling is done.
- Severities are assumed i.i.d. and independent of frequency.
- Parameter uncertainty is not propagated (parameters are treated as known once estimated/assumed).
- Small samples (hundreds of synthetic incidents, tens per system) make estimates unstable; 99%-level and ES99 numbers are especially noisy.
- Controls are not modelled quantitatively in the base simulation (no control-effectiveness model).
- No validation, backtesting, calibration to real loss data, or model-risk governance has been performed.
- Stress scenarios are simple, predefined assumption changes, not expert-designed scenarios.
- KRIs are displayed as evidence; they are **not** used for prediction in V1.
- LLM output can be fluent but wrong; the design mitigates this by forbidding the LLM from producing numbers and requiring tool-sourced evidence, but human review remains essential.

**Nothing in this prototype predicts real JPMorgan (or any real bank's) Operational Risk.**

---

## 10. Features intentionally excluded from V1

Do **not** build these, and do not add unrequested features:

- Predictive ML of any kind; ML estimation of λ from KRIs.
- XGBoost, Tabular Foundation Models (e.g. TabPFN), Graph Neural Networks.
- Negative Binomial frequency models; time-varying intensity λ(t); Hawkes processes.
- Extreme Value Theory / Generalized Pareto tail modelling.
- Beta-distributed uncertain control effectiveness.
- PostgreSQL or any server database; vector databases; graph databases (Neo4j etc.).
- LangChain or heavy agent frameworks (unless a compelling reason is demonstrated and agreed).
- Authentication / authorisation.
- Cloud-specific infrastructure or deployment tooling.
- Real-time streaming.
- Microservices.
- An elaborate UI.
- Any write-capable agent tool (the agent is read-only).
- Anything else not requested for the final demonstration. If a feature does not strengthen the demo, do not implement it.

---

## 11. Future research directions

Documented only — **not implemented** in the prototype. All require better data and domain expertise.

- **Negative Binomial frequency** — to capture over-dispersion (variance > mean) that Poisson cannot.
- **Time-varying intensity λ(t)** — non-homogeneous Poisson processes reflecting changing conditions.
- **ML estimation of λ from KRIs** (e.g. gradient boosting such as XGBoost; tabular foundation models such as TabPFN) — linking leading indicators to incident frequency.
- **Extreme Value Theory / Generalized Pareto** tail modelling — principled treatment of rare, extreme losses beyond a threshold.
- **Hawkes (self-exciting) processes** — incident clustering, where one incident raises the short-term probability of others.
- **Beta distributions for uncertain control effectiveness** — propagating uncertainty about how well controls work.
- **Graph Neural Networks** — learning risk propagation over the dependency graph.
- Parameter-uncertainty propagation, dependence/copula structures between systems or vendors, richer scenario design.

**Central open research question (intentionally NOT answered by this prototype):**

> *Can modern AI and machine learning improve early identification of deteriorating Operational Risk conditions when combined with classical frequency–severity modelling?*

RiskSignal provides a transparent classical baseline and an evidence-gathering workflow within which such a question could be studied properly — with real data and an Operational Risk team.

---

## 12. Institutional work requiring real bank data and expertise

These are deliberately missing and represent the genuine R&D that could only be done with an actual Operational Risk team:

- institution-specific **loss data** (internal, plus external/consortium data where appropriate),
- actual **KRIs** and their thresholds,
- actual **control** inventories, testing results and effectiveness evidence,
- actual **technology dependency** maps (systems, vendors, processes, critical services),
- the institution's **Operational Risk taxonomy** (event types, risk categories),
- **scenario design** with subject matter experts,
- **frequency calibration**,
- **severity calibration**,
- **tail modelling**,
- model **validation** and **backtesting**,
- **model risk governance** (documentation, independent validation, change control),
- **security and integration** with existing systems (access control, data classification, auditability, approved LLM usage).

---

## 13. Technology stack

| Area | Choice |
|---|---|
| Language | Python 3.12 |
| Data | pandas, numpy, scipy |
| Validation / schemas | pydantic |
| Graph | NetworkX |
| Storage | SQLite (standard library `sqlite3`) |
| Backend | FastAPI |
| Frontend | Streamlit (Plotly where useful) |
| LLM | Anthropic API for the live agent, behind a small provider interface; mock LLM for tests |
| Testing | pytest |

No other major dependencies should be introduced without a clear reason.

---

## 14. Software engineering principles

- Simple, readable Python; **type hints** everywhere; docstrings where useful; **small functions**.
- Avoid unnecessary abstractions. Direct tool calling and a simple agent loop.
- **Business logic independent of the UI.** **Stochastic code independent of the LLM.**
- The LLM must never be the source of a quantitative value if a Python function can compute it.
- **All simulation functions support deterministic random seeds.**
- Isolate the LLM provider behind a small interface; provide a mock for tests; automated tests must run offline with no API key.
- Choose the simplest technically correct solution. No premature optimisation.
- Pydantic models for structured results (tool outputs, simulation results, API payloads).
- Documentation explains advanced mathematical concepts **in beginner-friendly language first, then the mathematical definition**.
- Tests for: simulation determinism under fixed seed, agreement with analytic `E[L] = λ·E[X]` within Monte Carlo tolerance, risk-metric ordering (`median ≤ P95 ≤ P99`, `P95 ≤ ES95`, `P99 ≤ ES99`), graph queries, tool outputs, and agent behaviour via the mock LLM.
- **Development workflow, for each task:** (1) inspect existing code before modifying; (2) implement only the requested step; (3) preserve compatibility with previous steps; (4) run relevant tests; (5) fix failures; (6) summarise files created/modified; (7) explain important mathematical or software concepts simply; (8) state assumptions; (9) **stop** — do not continue to future stages automatically.

---

## 15. Agent safety and traceability rules

1. **Read-only.** Agent tools may retrieve, query and simulate. No tool may write to or modify risk records (incidents, controls, KRIs, dependencies).
2. **No invented facts.** Incidents, controls, vendors, dependencies and numbers must come from tool outputs. If a tool returns nothing, say so; do not fill gaps.
3. **No LLM-generated numbers.** Every quantity (counts, dates, losses, percentiles, parameters) must be traceable to a tool result. The LLM may *cite* numbers returned by tools; it must not compute, estimate or round-trip them creatively.
4. **No verdicts.** The agent never declares a system objectively safe/unsafe or makes a final risk decision or remediation call. It frames findings as evidence and as questions for a human analyst.
5. **Provenance labelling.** Outputs separate observed evidence, model assumptions, simulation results and suggested investigation questions, and indicate whether parameters are estimated, user-supplied or stress-scenario assumptions.
6. **Traceability.** Every agent run records the sequence of tool calls (name, arguments, result summary) so a reviewer can audit how each statement was supported. The API/UI should be able to display this trace.
7. **Reproducibility.** Simulations in an agent run use explicit seeds and report seed, number of simulations and scenario name.
8. **Honest scope statement.** Agent output carries (or the UI shows) the reminder that data are synthetic and parameters illustrative.
9. **No autonomous remediation or side effects** of any kind.
10. **Testable offline.** Agent logic must be exercised in tests via the mock LLM, including a check that the final answer's numbers appear in tool outputs where feasible.

---

## 16. Definition of success for this prototype

The prototype is successful if:

1. **The demo works end to end:** selecting `PAYMENT_ENGINE_01` and clicking "Investigate" yields an evidence-based, four-section summary, with all facts and numbers computed from the synthetic dataset and the simulation engine — nothing hardcoded.
2. **The mathematics is correct and verifiable:** the compound Poisson–Lognormal simulation is seeded, reproducible, agrees with analytic checks, and reports mean, median, P95, P99, ES95, ES99 with clearly stated estimators.
3. **Provenance is always clear:** a reviewer can tell what is observed, estimated, assumed, stressed or simulated.
4. **The agent is trustworthy by design:** it is read-only, tool-grounded, traceable, makes no verdicts and invents nothing.
5. **Limitations are stated openly,** and the missing institutional elements are presented as the natural next research steps rather than hidden.
6. **The code is clean and small:** readable, typed, tested, layered so that business logic is independent of UI and LLM, and swappable at the LLM boundary.
7. **A quantitative Op Risk reviewer would find it credible,** and a senior Op Risk reviewer would find it clear and relevant — and both would come away with concrete ideas for what could be researched together with real data.

Success is **not** measured by predictive accuracy, scale, UI polish, or the number of AI techniques used.
