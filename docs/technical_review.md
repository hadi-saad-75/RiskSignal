# Technical Review

Internal review of the whole RiskSignal repository, covering the code, the quantitative model and the Operational Risk framing. Date of review: 2026-10-12.

> **What this is.** An internal code and model review of a research prototype, done by reading the code, running independent numerical checks (NumPy and SciPy), type-checking, measuring coverage, and fixing defects. **It is not an independent model validation.** Nothing in this document makes the synthetic data, the model parameters or the scenario multipliers valid for any real institution. See section 7.

---

## 1. Summary

**Overall.** The implemented mathematics is correct and the layering is sound: every formula the project documents was checked against an independent calculation, and the dependencies between layers match the architecture (and are enforced by tests). The review found **five defects**, all now fixed and covered by tests, and a list of remaining technical debt (section 5), none of which changes a result.

The most important finding was quantitative: **the stress comparison did not use common random numbers**, although the documentation said it did.

### Findings that were fixed

| # | Severity | Area | Finding | Fix | Guarded by |
|---|---|---|---|---|---|
| F1 | High | Simulation | Baseline and stress were simulated with the same *seed*, which does **not** couple them: different λ values consume the random stream differently, so the two runs were uncorrelated (measured correlation of annual losses: 0.000). The documentation claimed that differences "come from the assumptions, not from different random numbers". Consequence: for a mild scenario (λ ×1.01) the stressed P99 came out *lower* than the baseline for 9 of 40 seeds. | New `simulate_paired_annual_losses`: exact coupling by Poisson superposition (λ up) or thinning (λ down), re-using each incident's underlying normal draw for severity. Baseline stays bit-identical to a standalone run. | `tests/test_model_review.py` (pointwise dominance, bit-identity, marginal distribution by KS test, correlation, no sign flips) |
| F2 | Medium | Agent | The system prompt contained the literal `"about 896 thousand"`, which was the focal system's actual baseline P95 at the default seed. A hardcoded output in the prompt can prime a model to echo it. | Removed. | `test_system_prompt_has_no_example_values_the_model_could_echo` |
| F3 | Medium | Frequency | `estimate_lambda_from_incidents` counted every incident of the table regardless of date. Incidents outside the observation window silently inflated λ (reproduced: 10 incidents counted for a one-year window, 5 of them five years earlier). Not reachable through the tools today, but it is a public estimator. | Raises `ValueError` if any incident is dated outside the window. | `test_incidents_outside_the_window_are_rejected_not_silently_counted` and a boundary test |
| F4 | Medium | API | `/health` returned `ok` for a 0-byte, corrupt or empty database file, while every data endpoint returned 503. Docker Compose gates the dashboard on this health check. | `/health` now reads the system list; unreadable or empty means `degraded`. | `test_health_is_degraded_for_an_empty_or_unusable_database` |
| F5 | Medium | Documentation | Over-strong claims: "the agent calculates nothing itself" and "every number comes from Python code" (README, dashboard text, API description) describe an intention, not a guarantee. The "same seed" claim of F1. A "pure HTTP client" claim was fine, but `agent_tools.md` omitted the four tool-layer functions that exist only for the UI. | Reworded to "instructed to … and checked (best effort)"; scenario docs rewritten; the four UI-only functions documented. | n/a (text) |

### Tests added to make earlier claims permanent

Exact P95/P99/ES on a known sample of 100,000 distinct values, NumPy/SciPy Lognormal parameterisation, vectorised aggregation against a naive loop, the engine against an independent loop implementation (two-sample KS), prompt headings versus dashboard headings, and complete mapping of tool error types to HTTP statuses. 28 tests, all in `tests/test_model_review.py`.

### Test run at the end of the review

**556 tests, 556 passed, 0 skipped, 0 failed** (528 before the review; 28 added).

---

## 2. Architecture assessment

### What was checked and found sound

| Property | Evidence |
|---|---|
| Layering is one-directional (data → graph/stochastic → tools → agent → API → UI) | Tests parse the imports of every package: lower layers never import the agent, API or UI; the stochastic package imports no LLM, UI, tools, data or database code; the graph package imports no stochastic, agent, API or UI code. |
| Stochastic code is independent of the LLM | Same import tests; the engine runs from NumPy/pandas/Pydantic only. |
| The agent cannot reach data or calculate | The agent package imports no `sqlite3`, pandas, NumPy, data or graph modules (tested). Its only access is the tool registry. |
| Tools are read-only with no arbitrary SQL | A test parses every string literal in the tools package: all SQL is a fixed `SELECT` without interpolation or `;`; f-strings are never SQL; injection strings are treated as unknown system IDs. |
| API contains no business logic | The API imports no engine, graph, pandas or NumPy modules (tested); every endpoint response equals the corresponding tool output (tested). |
| UI separation | The dashboard imports no engine, graph, agent, tools, data, API, NumPy or SciPy code (tested). The Docker UI image installs only Streamlit, Plotly and httpx, and the dashboard ran correctly from that minimal environment against the API. |
| LLM provider is replaceable | `LLMProvider` is the only interface; only `anthropic_provider.py` imports `anthropic` (tested). The whole API and dashboard were run end to end on the mock provider. |
| Duplicate logic | The tool layer wraps rather than reimplements: spies confirm that simulation tools call the stochastic engine and the dependency tool calls the graph queries. |
| Data leakage | No module reads another layer's private state. There is no train/test notion because nothing is predicted. Parameters are estimated in sample from the same history the agent then reports; this is a descriptive model, and in-sample fit is not evidence of predictive validity. |

### Type safety

mypy (run once in a throwaway environment, not part of the repository) reports **19 findings in 6 files**. All are `str` versus `Literal[...]` mismatches (for example the generator's tuple-typed reference data, which Pydantic validates at runtime) and `Optional` narrowing that mypy cannot see through (`if None in (a, b)`: return). None is a runtime defect, none was changed. Type hints are used throughout and Pydantic validates all inputs and outputs at the boundaries, but **no type checker or linter is configured in the repository** (debt item 9).

### Test coverage

Measured before the review fixes with a temporary `coverage` run: every module has at least 84% line coverage (lowest: `ui/components.py` 84%, then `system_explorer.py` 93% and `generator.py` 93%); the engine, tool, agent and API modules are at 95% to 100%. Line coverage does not show whether the tests are *meaningful*, which is why the review also added behavioural checks (above). The suite runs offline in about 20 seconds.

### Remaining architectural observations

See section 5. The most notable: the observation window constants live in the generator module, and the tool layer imports them from there instead of reading them from the database.

---

## 3. Quantitative assessment

### 3.1 Verification results

| Requirement | How it was verified | Result |
|---|---|---|
| **λ is estimated correctly from observation duration** | Independent hand calculation from the database: the focal system has 19 incidents; the window 2021-10-01 to 2026-09-30 is 1,826 days counting both end dates = 4.9993 years; 19 / 4.9993 = 3.80052. | Engine value identical to the hand value. |
| **λ uses only incidents inside the window** | Reproduced a counterexample (see F3). | **Defect found and fixed.** |
| **Lognormal parameterisation for NumPy** | `Generator.lognormal(mean=μ, sigma=σ)` takes μ and σ of the *log* of the loss. Sample median and mean compared with exp(μ) and exp(μ + σ²/2) on 2,000,000 draws. | Correct. |
| **Lognormal parameterisation for SciPy** | `scipy.stats.lognorm(s=σ, scale=exp(μ))`: mean, median and 95th percentile equal the formulas (to 1e-12); a KS test of NumPy draws against the SciPy CDF gives p = 0.17; `scipy.stats.lognorm.fit(floc=0)` returns the same σ and μ as the engine's fit. | Correct. (The engine itself uses NumPy only; SciPy is used in tests as an independent reference.) |
| **Monte Carlo aggregation is correct** | (a) `aggregate_by_year` against a naive per-year loop on the same draws: maximum difference 4.7e-10. (b) The engine against an independently written loop implementation: two-sample KS p = 0.15. (c) Simulated mean 285,924 against the closed form λ·exp(μ+σ²/2) = 284,931 (0.35% apart, less than one standard error); simulated variance 2.012e11 against 2.027e11; P(L=0) = 0.0227 against e^(−λ) = 0.0224. | Correct. |
| **P95 and P99 are calculated correctly** | `numpy.quantile(..., method="inverted_cdf")` implements VaR_α = inf{x : F(x) ≥ α}. On the sample 1…100,000 it returns exactly 95,000 and 99,000, independent of input order. | Correct. |
| **Expected Shortfall uses the appropriate tail** | The estimator averages the worst M·(1−α) simulated years, giving a fractional weight to the boundary year (Acerbi-Tasche), so ES ≥ VaR even with ties and with many zero-loss years. On 1…100,000 it returns exactly 97,500.5 (ES95) and 99,500.5 (ES99); property tests cover awkward sample sizes. | Correct. |
| **All loss values are non-negative** | Severities are exp(·) > 0; annual losses are sums of positives or exactly 0 when N = 0; checked in tests and in the schemas (`ge=0`). | Correct. |
| **Deterministic seeds** | Same seed gives identical results in the engine, the scenario comparison, the tools and the API; the synthetic data generator gives byte-identical files across processes with different hash seeds. | Correct. |
| **Baseline and stress use comparable random handling** | Before the review: same seed, same generator algorithm, same number of simulations, but **uncorrelated** (see F1). After: common random numbers (below). | **Defect found and fixed.** |
| **No result is hardcoded** | Searched `src/` for the focal values and for numeric literals in prompts, tool descriptions and the mock provider. The only hits were the prompt example (F2) and docstring examples. The mock provider composes its summaries only from the tool results it receives. The scenario multipliers (1.8, +0.2, 1.1) are explicit, labelled assumptions, not results. | One hit fixed. |

### 3.2 Effect of the coupling fix

Measured over 40 seeds, 100,000 simulated years, parameters similar to the focal system's fit (λ = 3.8, μ = 10.1, σ = 1.5). "P99 change" is 100·(stress P99 / baseline P99 − 1).

| Scenario | Independent runs: mean ± SD of P99 change | Coupled runs: mean ± SD | Seeds (of 40) with stressed P99 below baseline: independent / coupled |
|---|---|---|---|
| λ × 1.01 (true change ≈ 1%) | not measured | not measured | 9 / 0 (0 is guaranteed by construction) |
| λ × 1.05 | +2.83 ± 1.04 points | +2.87 ± 0.52 points | 0 / 0 |
| λ × 1.8, μ +0.2, σ × 1.1 | +154.98 ± 4.21 points | +155.18 ± 2.78 points | 0 / 0 |

Both versions are unbiased; coupling roughly halves the noise for a frequency-only change and reduces it by a third for the predefined-like scenario (changing σ decouples the tails partly). Run time is unchanged (0.04 s for 100,000 years both ways). Even coupled, the predefined scenario's "+155%" is only known to about ±3 points at this simulation size.

### 3.3 Monte Carlo error of the baseline metrics

Relative standard deviation across 40 seeds, same parameters:

| Metric | 100,000 simulations | 10,000 simulations |
|---|---|---|
| Mean | 0.46% | 1.48% |
| Median | 0.49% | 1.18% |
| P95 | 0.60% | 2.18% |
| P99 | 1.25% | 4.48% |
| Expected Shortfall 95 | 1.05% | 3.61% |
| Expected Shortfall 99 | 2.00% | 7.33% |

To reproduce: loop `seed` over 0…39, call `compute_metrics(simulate_annual_losses(3.8, 10.1, 1.5, 100_000, seed))`, and take the standard deviation divided by the mean of each metric across seeds. These numbers are measurements taken on the review date and are not stored anywhere in the application.

### 3.4 Statistical caveats (properties of the approach, not defects)

1. **Parameter uncertainty is ignored and is the dominant error.** The focal severity fit uses 19 losses. The standard error of σ̂ is about σ/√(2n) = 1.478/√38 ≈ 0.24 (16%). For illustration, one standard error of σ moves the 99th percentile of a *single* Lognormal loss by a factor of exp(0.24 × 2.33) ≈ 1.7. That is tens of percent, against 1.25% of Monte Carlo error on P99. Simulating more years does not reduce it. The reported percentiles should be read as conditional on the point estimates.
2. **The MLE of σ is biased low.** The engine divides by *n* (maximum likelihood). The variance of the logs is underestimated by a factor (n−1)/n, which is 0.947 at n = 19. This is documented as maximum likelihood and is a deliberate, standard choice, but it is the optimistic direction for tails.
3. **The synthetic data satisfy the model by construction.** The generator draws incident counts from a Poisson process (the dispersion index of bank-wide monthly counts is 0.99) and losses from Lognormal distributions. A KS test of the fitted Lognormal gives p = 0.91 for the focal system (n = 19), 0.47 for its sibling (n = 16) and 0.94 bank-wide (n = 312). These good fits are **circular and prove nothing about real losses**; the p-values are also optimistic because the parameters were fitted on the same data. The system-level losses are a mixture of category-specific Lognormals with criticality scaling, which a single Lognormal approximates well here.
4. **Thresholds are arbitrary.** At least 5 incidents are required for a system-specific λ and at least 15 positive losses for a system-specific severity fit. They are labelled illustrative and every fallback is reported in the result, but no analysis supports these values.
5. **Poisson assumptions.** Constant rate, independent arrivals, no clustering, no seasonality, no over-dispersion, and severities independent of the count. Real operational incidents typically violate several of these; the prototype does not test them on real data.
6. **Lognormal tails.** No tail-specific modelling. A Lognormal can understate extreme losses; ES99 from a Lognormal is not a tail estimate in the extreme value sense.
7. **One system at a time.** The shared-vendor concentration is visible in the graph but not in the loss model: the two payment engines are simulated independently, so no aggregate loss across systems and no common-shock effect is modelled.
8. **Frequency and severity can come from different datasets** for the same system (for example λ from the system's own history and severity from bank-wide losses). Both sources are reported separately in every result.
9. **Controls and KRIs do not enter the model.** They are displayed as evidence only.

---

## 4. Agent assessment

### 4.1 Requirement checks

| Requirement | Assessment |
|---|---|
| **The LLM never calculates quantitative metrics itself** | *By design and by instruction, not by impossibility.* The agent has no calculation tool; the only numbers it receives come from tool results; the system prompt forbids arithmetic and tells it to quote tool values; and after each run, every number in the answer is matched against all tool inputs and outputs, with unmatched numbers listed in `ungrounded_numbers` and a warning. Tests show that an invented P95 and a tool value silently multiplied by 1.5 are both flagged. **A live model could still miscalculate or misquote, and the check is best effort** (4.2). Documents and the UI now say this. |
| **The tool layer is the authoritative source** | Yes. The agent has no other access to data or numbers. Tool results are passed to the model as JSON, unmodified except that bulky chart histograms are omitted. The full model-facing output of every tool call is returned in `tool_activity`. |
| **The agent clearly labels synthetic data** | Labelling does not depend on the model's compliance: the dashboard banner, the API description, the `disclaimer` field of every agent response, the `notice` field of every tool result and the dashboard footer are attached by code. The system prompt also instructs the model to say so, and the mock summary does. Whether a *live* model reliably adds the wording was **not observed**. |
| **Tool failures are handled** | Yes, at three levels: tools return typed `ToolError`s instead of raising; the registry turns unknown tools, missing or extra arguments and crashes into failed outcomes; the investigator returns provider failures and step limits in the result instead of raising. Failed calls are passed to the model flagged as errors and shown as ❌ in the log. All covered by tests, including a failure inside a batch of parallel calls. How a *live* model reacts to an error (the prompt tells it not to retry unchanged and not to guess a system) was **not observed**. |
| **The live provider can be replaced by the mock provider** | Yes. A single-method interface (`complete`), one provider file that imports `anthropic`, a deterministic mock used by all tests, the CLI (`--mock`), the API (`RISKSIGNAL_LLM_PROVIDER=mock`) and the dashboard. |
| **Tool traceability** | Each call records order, tool name, exact input, status, error type, start time, duration, a Python-written one-line summary and the output the model saw. Gaps: results are returned to the caller but not persisted; the conversation messages are not stored; default arguments that the model omitted are visible only inside the tool output. |

### 4.2 Limits of the numeric grounding check

It is a safety net, not proof. It does **not** catch:

- a real tool number attached to the wrong thing (for example P99 described as P95);
- whole numbers up to 20 without a unit suffix, identifiers and dates (deliberately ignored);
- wrong or invented qualitative claims (a made-up incident description or control name);
- numbers written in unusual formats (for example scientific notation);
- an invented figure that happens to fall within the rounding tolerance of a real one (a coarse "0.9 million" accepts anything within ±50,000 of a tool value).

### 4.3 What the tests do and do not show about the agent

The offline tests exercise the **harness**: tool selection plumbing, error handling, the loop, the provider interface, the grounding check, message conversion to the Anthropic format (with a stand-in client). They **do not** show how a real language model behaves: whether it follows the prompt, picks sensible tools, formats the sections, avoids verdicts, or resists instructions hidden in data. The mock provider is scripted, so its good answers say nothing about live quality.

### 4.4 Hallucination and misuse risks

| Risk | Mitigation present | Residual risk |
|---|---|---|
| Invented numbers | No-calculation instruction; numbers only from tools; post-hoc grounding check | Medium: undetected misattribution, small integers |
| Invented incidents, controls or vendors | Prompt prohibition; tools are the only source; failures reported | Medium: no automatic check of qualitative claims or identifiers |
| Verdicts ("safe", "high risk") and remediation advice | Prompt prohibition; read-only tools; answer ends in questions for a human | Medium: not checked in code |
| Over-claiming that simulation results are forecasts | Prompt, tool notices, UI labels, disclaimer | Low to medium |
| Prompt injection through free-text data (incident descriptions, vendor names) | None specific | Low *here* (synthetic data written by this project); **high with real data** |
| Writing data or running SQL | No write tool; fixed read-only SQL | Very low |
| User-supplied stress numbers reaching the agent | Custom scenario function is not registered; the scenario ID is an enum | Very low |
| Runaway loops and cost | 10-step limit; request size limits on the API | Low |
| Credential exposure | Key read from the environment; never logged or returned; `.env` git-ignored; test scans for key-shaped strings | Low |

---

## 5. Remaining technical debt

Ordered by importance. None changes any computed result.

| # | Priority | Item |
|---|---|---|
| 1 | High | **The live Anthropic path has never been run** against the real API (no key was available). The provider and loop are tested with a stand-in client only. There is no evaluation harness for real model behaviour (tool choice, formatting, refusal to give verdicts, handling of tool errors). The default model name is an assumption (`ANTHROPIC_MODEL` overrides it). |
| 2 | High | **The Docker images have never been built or run** (no engine was available). Their build steps and health check were emulated with plain Python. Run `docker compose up --build` once before relying on them. |
| 3 | Medium | **Parameter uncertainty is not propagated** (3.4). A parametric bootstrap or Bayesian treatment would show the dominant error. This is research scope, listed in the project's future work. |
| 4 | Medium | **Observation window constants are imported from the generator module** by the tool layer (`DATA_START`, `DATA_END`), not read from the database. A database generated for other dates would give silently wrong λ and "recent" windows. Storing the window in the database would fix it. |
| 5 | Medium | **Grounding check heuristics** (4.2) could be tightened (units, identifier cross-checks against tool outputs), at the price of more false alarms. |
| 6 | Medium | **Cached state is never invalidated**: the graph (per tool context) and the API's settings and context are cached for the process lifetime. Regenerating the database requires restarting the API. |
| 7 | Medium | **API has no authentication, rate limiting or concurrency control**; a client can request many 1,000,000-year simulations. Acceptable for localhost, which the Docker setup enforces by publishing on 127.0.0.1 only. |
| 8 | Low | **`DEFAULT_DATA_DIR` is derived from the package file location**, so a non-editable `pip install .` would look for data in the wrong place. The README prescribes the editable install. |
| 9 | Low | **No type checker or linter is configured** (mypy reports 19 literal and narrowing findings, none a defect). |
| 10 | Low | **Duplicated knowledge**: `_basis_and_assumptions` and `_basis_and_assumptions_from_model` in `simulation_tools.py` are near copies; the six answer headings are listed in the prompt, the dashboard parser and the mock provider (now consistency-tested); the dashboard repeats the API's input limits; `agent/tool_registry.py` imports `stochastic.scenario` only to list scenario IDs. |
| 11 | Low | **`get_kri_history` echoes the requested `months`** even when less history exists (120 requested, 60 observations returned). The observations themselves are correct. |
| 12 | Low | **Scenario Lab keeps the last result in session state** even after the inputs change; each result shows its own simulation count and seed. |
| 13 | Low | **SciPy is a declared runtime dependency but only the tests use it** (the engine uses NumPy). It could move to the dev extras and slim the API image. It is kept because the project brief names it and the tests use it as the independent reference. |
| 14 | Low | **The synthetic CSV files carry no in-file disclaimer**; the notice is in the README, the generator output and every application layer. |
| 15 | Low | **The category fallback for severity ends at all-category bank-wide losses**, which is inconsistent with a category-specific frequency. Only reachable when a category is requested and the data are thin. |

---

## 6. Prototype limitations

These apply to the whole project and are described further in [limitations.md](limitations.md).

- All data are synthetic (fictional Atlas Bank); some relationships are deliberately constructed to make the demonstration readable.
- Model parameters, thresholds and scenario multipliers are illustrative.
- No calibration to any institution, no validation, no backtesting, no sensitivity analysis, no governance.
- No claim of predictive validity; no regulatory capital claim; no data from any real bank.
- No production security: no authentication, access control, encryption or audit store.
- The AI agent supports a human analyst and makes no risk decisions.
- Controls, KRIs and cross-system dependencies do not enter the loss model.
- Unimplemented by design: Negative Binomial frequency, time-varying intensity, ML estimation from KRIs, extreme value theory, Hawkes processes, uncertain control effectiveness and graph neural networks.

---

## 7. What should NOT be interpreted as validated

Nothing in this prototype has been validated in the model-risk sense. In particular, **do not read any of the following as validated**:

1. **Any loss figure**: mean, median, P95, P99, Expected Shortfall, or the ranking or comparison of systems. They are outputs of an illustrative model fitted to synthetic data.
2. **The fitted parameters** λ, μ and σ, and the fallback thresholds that produced them.
3. **The adequacy of Poisson frequency or Lognormal severity** for real losses. The good statistical fits reported here are circular: the synthetic data were generated from these families.
4. **The stress scenario multipliers** (1.8, +0.2, 1.1) and the stressed results. They are chosen assumptions with no data or expert support, and they do not use the dependency graph.
5. **The constructed story of `PAYMENT_ENGINE_01`** (recent incidents, overdue control, worsening KRIs, shared vendor). It is built into the generator for the demonstration.
6. **Worsening KRIs or overdue controls as risk signals.** They are displayed as evidence only; nothing here shows that they predict incidents.
7. **The shared-vendor "related systems" as causation or contagion.** They show shared structural exposure only.
8. **The quality of the agent as a risk analyst**, the relevance of its suggested questions, or the factual accuracy of a live model's answers. The live model was not exercised.
9. **The numeric grounding check as proof** that an answer is right.
10. **The passing test suite as validation of the model.** The tests verify that the code does what the documentation states and that the mathematics is implemented correctly. They say nothing about whether the model describes reality.
11. **The Docker images**, which have not been built.

A real implementation would need institution-specific loss data, KRIs, controls and dependency maps; scenario design with subject matter experts; frequency, severity and tail calibration; validation and backtesting; model risk governance; and security and integration work. These are listed in [project_brief.md](project_brief.md) and [limitations.md](limitations.md) as the work that would have to be done with an actual Operational Risk team.
