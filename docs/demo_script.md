# Demo Script

A short live technical demonstration of RiskSignal for senior Operational Risk professionals, built around `PAYMENT_ENGINE_01`.

> **Read this first.** Everything on screen is **synthetic** (a fictional "Atlas Bank") and every model parameter is **illustrative**. The `PAYMENT_ENGINE_01` story is **constructed** by the data generator so that the demonstration is readable. Nothing here is a finding about a real institution, a forecast, or a validated model. Say so early and plainly; it is the point of the project, not an apology (see [limitations.md](limitations.md) and [technical_review.md](technical_review.md), section 7).

**Length:** about 13 minutes in full; about 7 minutes if you skip the steps marked *(optional)*. Timings below are suggestions.

---

## Part 1. Before you start

### 1.1 Setup (do this well before the audience arrives)

**Local (tested):**

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1                 # macOS / Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m risksignal.data.generator        # writes data/synthetic/ (seed 42, identical every time)
pytest                                     # optional: confirm everything passes
```

Terminal 1, the API. Pick **one** of the two lines:

```bash
uvicorn risksignal.api.main:app                                        # live agent (needs ANTHROPIC_API_KEY in .env or the environment)
RISKSIGNAL_LLM_PROVIDER=mock uvicorn risksignal.api.main:app           # offline scripted agent, no key
# PowerShell:  $env:RISKSIGNAL_LLM_PROVIDER="mock"; uvicorn risksignal.api.main:app
```

Terminal 2, the dashboard (the flag hides Streamlit's "Deploy" button):

```bash
streamlit run src/risksignal/ui/app.py --client.toolbarMode viewer
```

Open `http://localhost:8501`. **With Docker:** `docker compose up --build` (set `RISKSIGNAL_LLM_PROVIDER=mock` first for the offline agent). The Docker images have not been built in development, so rehearse that route before relying on it.

### 1.2 Live model or offline mock: decide, and be honest about it

- **Live:** the sidebar shows `AI provider: anthropic (ready)`. Wording differs on every run, and the first run in front of an audience is a risk. **Run it once beforehand.** The live path has not been exercised in development (no API key was available), so check that it works with your key and model name (`ANTHROPIC_MODEL` if needed). Expect a wait of several seconds while it calls the model repeatedly.
- **Offline mock:** the sidebar shows `AI provider: mock (ready)`. The "agent" is then a **deterministic script**, not a language model. It requests the same tools and writes the summary from the tool results. The tool trace, the structure and the numbers are real; the choice of tools and the wording are scripted. **Say this out loud** if you use it: *"This is the offline provider, so the language model is replaced by a script. The live version calls Anthropic; everything else you will see is identical."*
- **Do not** present mock output as an AI result.

### 1.3 Browser and screen

Pre-open four tabs, in this order: `/` (Overview), `/system-explorer`, `/scenario-lab`, `/ai-investigator`. Opening a page URL directly is fine (the browser console shows harmless 404 messages for Streamlit assets). Keep `docs/institutional_validation.md` and `docs/limitations.md` open in your editor or on GitHub for steps 9 and 10. Zoom the browser so the back row can read the numbers. Refreshing a tab resets its state.

On the **System Explorer** page, before you present the KRIs, set *Months of history* to **24**: click the slider and press the right-arrow key 12 times (it starts at 12).

### 1.4 Reference values for the default data (check your screen against these)

With the default data (seed 42) and default simulation settings (100,000 simulated years, seed 42) the screen should show the values below. They were read from the application and are **checked by an automated test** (`tests/test_demo_script.py`), so they cannot silently go stale. If your screen differs, trust the screen, find out why (data regenerated with another seed? different settings?) and do not quote this table.

| Item | Value on screen |
|---|---|
| `PAYMENT_ENGINE_01` incidents in the last 12 months | 5 (2 mention deployment, 2 are Keystone Payment Rails V04 events, 1 human error) |
| Controls | 4, of which 1 overdue: C002 Pre-Release Regression Testing; 1 due: C004 Vendor Performance Review |
| Shared vendor | V04 Keystone Payment Rails, also used by `PAYMENT_ENGINE_02` (V02 Vertex Messaging Networks is also shared with `MESSAGING_HUB_01` and `CLEARING_INTERFACE_01`) |
| KRI change, last 24 months vs the 24 before | failed deployment rate +84.7%, control exceptions +47.1%, system downtime +15.3%, near misses -5.4%, vendor incidents +22.2% |
| KRI change, last 12 months vs the 12 before | failed deployment rate +14.1%, control exceptions +0.0%, system downtime +50.5%, near misses +18.8%, vendor incidents +350.0% (from a very low base) |
| Estimated model | λ = 3.80 incidents per year (19 incidents over 5.00 years), μ = 10.114, σ = 1.478 (fitted to 19 losses) |
| Baseline annual loss | mean 278,433; median 163,846; P95 896,435; P99 1,856,257; Expected Shortfall 95% 1,546,928; Expected Shortfall 99% 2,900,104 |
| `SHARED_VENDOR_OUTAGE` stress | P95 2,276,896 (+154.0% vs baseline); Expected Shortfall 95% 3,927,230 |

### 1.5 What the data do and do not show: know this before anyone asks

- The **story is constructed** by the generator (recent incidents, an overdue control, drifting KRIs, a shared vendor). That the overdue control is *regression testing* and two incidents mention *deployments* is part of the construction, not a discovery. The generator also gives other systems overdue controls and drifting KRIs, so `PAYMENT_ENGINE_01` is not unique.
- The **KRI picture is mixed, not a clean deterioration.** Over 24 months the failed deployment rate roughly doubles and control exceptions rise; over the latest 12 months control exceptions are flat, near misses are drifting down, the latest single month's downtime is low, and the latest single month's deployment failure rate is a spike. Quote window averages, not single points, and say what is flat.
- `PAYMENT_ENGINE_02` **does have recent incidents of its own** (5 in 12 months, 3 of them Keystone V04 events), and V04 hit both systems on the same day. Do not say "PE02 has had no incidents". The point is that the *shared exposure* is visible in the structure, which a system-by-system view would not show.
- The synthetic losses were **generated from Lognormal distributions**, so the Lognormal fit looks good by construction.
- **KRIs and controls do not enter the loss model.** They are evidence on screen only. The model uses incident counts and loss amounts.
- The stress result (+154%) is the **arithmetic of the assumptions**: 1.8 times the incident rate, median incident loss ×exp(0.2) ≈ 1.22, 10% wider spread. It is not a finding.

### 1.6 Language

| Say | Avoid |
|---|---|
| "illustrative", "under these assumptions", "outputs of a model" | "predicts", "forecast", "the risk is" |
| "shared exposure", "a question for an analyst" | "will fail together", "contagion", "root cause" |
| "the agent gathers evidence; a person decides" | "the AI decided", "the AI found the risk" |
| "checked against the tool outputs, best effort" | "the AI cannot hallucinate", "validated" |
| "this is what a real team would have to calibrate" | any claim about a real bank's data, its models, or any named institution's use of this |

---

## Part 2. The demonstration

### Step 1. The problem (under one minute)

**Screen:** Overview tab. Point at the banner.

**Say (about 45 seconds):**
> "Operational Risk information is fragmented. Incidents live in one place, controls in another, key risk indicators in a third, and the map of which systems depend on which vendors in a fourth. An analyst investigating one system has to assemble all of that by hand, and the connections between systems are the easiest thing to miss. RiskSignal is a research prototype on a fictional bank, built to show how that evidence could be brought together, modelled transparently, and summarised by an assistant that is not allowed to invent anything. Everything you will see is synthetic, as the banner says."

**Show:** the counts (20 systems, 10 processes, 8 vendors, 40 controls, 312 incidents) and the recent-incidents table. No scores, nothing predicted.

### Step 2. Open `PAYMENT_ENGINE_01`: observed data (about 2 minutes)

**Screen:** System Explorer, system `PAYMENT_ENGINE_01`. Label: *"Observed synthetic data: nothing on this page is modelled or predicted."*

1. **Profile tab:** critical system, International Payments.
2. **Incidents tab** (12 months): 5 incidents. Read the descriptions: two deployment-related, two Keystone Payment Rails events, one manual configuration error. Note the keyword caveat under the table (the data have no cause field; "deployment" is a text match).
3. **KRIs tab:** set the window to **24 months** now (slider, right arrow ×12). Use the table under the charts, not a single point: failed deployment rate +84.7%, control exceptions +47.1% against the previous 24 months. **Also say what does not move:** near misses are slightly down; over the last 12 months control exceptions are flat. "Higher is less favourable for these indicators, and it is descriptive only: nothing is projected."
4. **Controls tab:** C002 Pre-Release Regression Testing is overdue (420 days since its last review); C004 Vendor Performance Review is due. **Say:** "An overdue review is a reason to ask a question, not proof the control failed."

> Watch-out: do not link C002 to the deployment incidents as cause and effect. You may say "an analyst would want to ask whether they are related".

### Step 3. Dependencies: why `PAYMENT_ENGINE_02` deserves a look (about 1.5 minutes)

**Screen:** the *Dependencies and related systems* tab; the shared-exposure map.

**Say:**
> "The map reads left to right: this system, its vendors and processes, then other systems sharing them. Keystone Payment Rails, V04, is also used by `PAYMENT_ENGINE_02`. A system-by-system view would not link the two. In the data, a Keystone service degradation hit both systems on the same day, 24 November 2025. That is a **shared exposure**: a reason to look at the second system, not evidence that one failure causes the other."

Mention in passing that the system also shares V02 with two other systems and a business process with several more, and that the table below lists every relationship with its reason. Point out *Vendors reached only indirectly*. The graph is built from the database tables, with NetworkX, and the queries return structured results.

> Watch-out: the vendor outage that hits both systems is **not** modelled jointly. The loss model simulates each system alone. Say so if asked (see the questions).

### Step 4. Scenario Lab: the model, in plain words (about 1.5 minutes)

**Screen:** Scenario Lab, `PAYMENT_ENGINE_01`. Show *Estimated baseline model* (λ 3.80, μ 10.114, σ 1.478) and open "What do λ, μ and σ mean?".

**Say (plain first):**
- **Poisson frequency:** "We do not know how many incidents next year brings. We model the count as random with an average of about 3.8 a year, which is 19 incidents over five years."
- **Lognormal severity:** "Most incidents are cheap and a few are very expensive. The Lognormal captures that shape: always positive, long right tail. Its two numbers are fitted to this system's 19 losses."
- **Monte Carlo:** "We play out 100,000 imaginary years: draw the number of incidents, draw a cost for each, add them up. The spread of those totals is the picture."
- **P95:** "The annual loss that this model says is exceeded in about one year in twenty."
- **Expected Shortfall 95:** "Take the worst five percent of those imaginary years and average them. It tells you how bad a bad year is once you are past the P95 line."

**Add immediately:** "These parameters come from 19 data points, so they are very uncertain, and the synthetic losses were generated from Lognormals, so the fit proves nothing about reality. Treat all numbers as illustrative."

### Step 5. Run the baseline (about 1 minute)

**Do:** leave the defaults (100,000 simulations, seed 42) and click **Run baseline and stress simulation**. The page shows both runs together; for now talk only about the **baseline** column and the blue distribution.

**Say:** "Mean about 278 thousand, but median about 164 thousand: the mean sits above the median because of the long tail. P95 is about 896 thousand, Expected Shortfall 95% about 1.5 million. The seed makes it reproducible: same seed, same numbers, every time." *(Read the numbers off the screen; they match the table in 1.4.)*

*(Optional)* Open **Advanced assumptions**, tick "Use my own numbers instead of the predefined scenario", set **both multipliers to 1.0** (they start at 1.5 and 1.2) and run: the stress then equals the baseline exactly, a sanity check that the machinery adds nothing by itself.

### Step 6. Run the shared-vendor stress scenario (about 1.5 minutes)

**Screen:** the same results, now the red *stress* column and the distribution overlay. Show the assumptions table above the button: λ ×1.8, μ +0.2, σ ×1.1, and open "Notes on this scenario's assumptions".

**Say:**
> "This is an illustrative scenario: a year in which the shared vendor misbehaves. I assumed 1.8 times as many incidents, each somewhat more costly, with a heavier tail. P95 goes from about 896 thousand to about 2.28 million, plus 154 percent. **That is the arithmetic of my assumptions, not a finding and not a forecast.** The multipliers are not calibrated to anything. In real use they would come from expert workshops, and that is exactly what a real team would add. Note also that both runs are simulated from the same underlying random numbers, year by year, so the difference comes from the assumptions rather than from sampling luck. And this scenario does not use the dependency graph: it is applied to one system alone."

**If someone asks about precision:** the Monte Carlo error of these percentages is of the order of a few percentage points at 100,000 years ([technical_review.md](technical_review.md), section 3).

### Step 7. The Assistant (about 2 minutes)

**Screen:** the Assistant (the landing page). `PAYMENT_ENGINE_01` is selected under "Full investigation of".

**Say:** "This is an early version of the assistant I would like to build with a real team. You can ask it anything, but it decides which deterministic tools to call; it cannot read the database or calculate anything itself, and it cannot change any records."

**Do:** type "Which systems should I look at first?" and show the comparison table, then "And are its controls up to date?" after asking about one system, to show that it keeps the context. *(If you are using the offline provider, say so now.)*

**Do:** click **Investigate this system** for the full report, then walk through its numbered sections:

1. **Observed evidence:** "all of this came from tool calls on the synthetic data."
2. **Model assumptions:** where λ, μ, σ came from.
3. **Simulation results:** "the same baseline numbers you just saw in the Scenario Lab: same tool, same seed." (True when the agent uses the default settings, as the offline provider always does; a live model could choose others, and its tool log would show it.)
4. **Connected exposures:** the shared vendors.
5. **Suggested investigation questions:** "questions for an analyst, for example *should control C002 be retested?*, *does the shared vendor create concentration risk?*, *does `PAYMENT_ENGINE_02` have similar exposure?* It does not decide anything." (The wording of a live model's questions will differ.)
6. **Limitations.**

*(Optional)* Tick the stress checkbox and run again to add the `SHARED_VENDOR_OUTAGE` comparison; the agent can only choose predefined scenarios, never invent numbers.

### Step 8. Evidence: how it stays honest (about 1.5 minutes)

**Screen:** under the report, **Simulation metadata** and the **Evidence** drawer.

**Say:**
> "Every step is recorded: which tool, with what input, whether it worked, how long it took. These log lines are written by code, not by the model. Open one: here is the exact input to the simulation tool and the exact output the agent received. The model never sees a database or a calculator; every number in the answer should be traceable to one of these outputs. Below, the simulation metadata is read straight from the tool output, not from the model's text. And after each run the application scans the answer for numbers that match no tool output and flags them: a figure with no match in any tool output would raise a warning here."

**Be exact about the limits:** the check is **best effort**. It will not catch a real number attached to the wrong thing, small whole numbers, or invented qualitative claims; the harness has been tested with a mock model, and **live model behaviour has not been evaluated** (agent validation is a research item, see step 10).

### Step 9. Limitations (about 1 minute)

**Screen:** the banner, the answer's *Limitations* section, then `docs/limitations.md` (or the "What should NOT be interpreted as validated" section of `technical_review.md`).

**Say:**
> "Three things. The data are synthetic, and the story was built into them. The parameters are illustrative: estimated from 19 incidents, with no allowance for estimation uncertainty, which in reality dominates the Monte Carlo noise. And I make no claim of predictive validity: nothing here has been backtested, calibrated, or validated, no regulatory capital claim, no data from any real bank. Passing tests mean the code implements the stated mathematics, not that the model describes reality. I did an internal technical review and found real defects, including that my own stress comparison was not coupled the way I had claimed; those are fixed and documented, along with what remains."

### Step 10. What only a real team could do (about 1 minute)

**Screen:** `docs/institutional_validation.md` (the *Roadmap at a glance* table), then `docs/research_extensions.md` (the five questions).

**Say:**
> "The most valuable questions are the ones this prototype cannot answer, and they need real data, Operational Risk expertise, and institutional context. Does a Poisson frequency fit real incident counts, or is there overdispersion? What does the real loss tail look like, and does it need extreme value theory? Do KRIs give earlier warning of deteriorating conditions, and does that beat simple baselines? Does dependency information improve identification of concentrated or propagating risk? Can an evidence-grounded agent save analyst time without lowering quality or control? I have written each as a research question with the data it needs and how it would be evaluated, with no results claimed. That is not a weakness of the prototype; it is what defines the next phase, and a realistic first step would be a data foundation, a baseline on real data, and one pre-registered pilot question."

---

## Part 3. Likely technical questions

Answers are deliberately short and do not pretend the research questions are solved.

**Why Poisson?**
It is the standard baseline for loss-event counts: one parameter, easy to estimate (incidents divided by years) and to explain. Here it is a starting point, not a conclusion. The synthetic data are Poisson by construction, so the fit says nothing about real incidents.

**What if the variance exceeds the mean?**
Then Poisson understates how variable annual counts are, and therefore the tail of annual loss. That overdispersion is common in practice. The standard remedies are a Negative Binomial (a Poisson with a random rate) or a time-varying rate. The prototype does not test for it; on real data the first step would be a dispersion test at several granularities and comparing the models out of sample.

**Why Lognormal?**
It is positive, right-skewed, has two interpretable parameters and is easy to fit and simulate. It is a transparent illustration, not a claim about real losses. Also, the synthetic losses were generated from Lognormals, so a good fit is circular.

**What about heavy tails?**
A Lognormal can understate the extreme tail of real operational losses. So P99 and Expected Shortfall 99 here are not tail estimates in an extreme value sense. They are what this illustrative model implies, and they would need dedicated tail modelling on real data.

**Why not EVT?**
Extreme value methods need enough tail observations to fit a Generalized Pareto tail above a threshold and to judge its stability. One system has 19 losses, so there is nothing to fit; pooling data or external loss data would be required. Without real data it would add false precision. It is listed as a model-development step in [institutional_validation.md](institutional_validation.md).

**Why not Hawkes processes?**
They model clustering where one incident raises the short-term chance of another. Identifying that needs real timestamped data, and care to separate self-excitation from a common cause such as a vendor outage. The synthetic data are Poisson by design, so a Hawkes model could only find an artefact. It is a research item, not an implemented feature.

**Why not TabPFN, XGBoost or any predictive model?**
The prototype is deliberately not predictive: the synthetic KRIs have no planted link to future incidents, so any score would measure the generator, not the world. Whether tabular foundation models beat statistical and gradient boosting baselines on genuine Operational Risk data is an open question, written up as a research question ([research_extensions.md](research_extensions.md)), not answered.

**Why synthetic data?**
Real loss data are confidential, institution-specific and not available to me. Synthetic data let the architecture, the modelling mechanics, the dependency reasoning and the agent controls be shown and tested without any confidentiality issue. The price is that no conclusion about reality can be drawn, and I have tried to label that at every layer.

**Why an LLM agent at all?**
Because deciding which evidence to gather, organising it, and drafting questions for an analyst is where a language model can help, while all numbers stay in deterministic code. The same tools and models work without the agent through the API and the other pages. Whether the agent actually saves time without lowering quality is **not established**; it is an evaluation question with a proposed design ([research_extensions.md](research_extensions.md), question 5).

**What prevents hallucinated numbers?**
Layers, none of them a guarantee. The agent has no calculation or database access; all numbers come from tool outputs; the prompt forbids arithmetic and invention; after each run the application flags numbers in the answer that match no tool output; every call is logged and replayable; a human reviews the result. The weak spots are real: a true number attached to the wrong metric, small integers and invented qualitative claims are not caught, and live model behaviour has not been evaluated.

**Why NetworkX?**
The graph is small (20 systems, 8 vendors), read-only and in memory; the queries are shortest paths and set intersections. NetworkX keeps it readable. At institutional scale the choice would depend on size and update patterns (a graph database, or relational recursive queries). The query functions form the interface, so the engine behind them could change.

**How would this scale?**
Not tested beyond this dataset, so I can only say what I would look at. Simulation is vectorised and fast (100,000 simulated years take tens of milliseconds on a laptop, measured in review) and per system independent. The graph and data would move to the institution's stores through read-only integrations. The agent adds cost and latency per question and needs per-user permissions inside the tool layer. The API has no authentication or rate limits today. The real work at scale is data quality and governance, not computation.

**How could real KRIs affect λ?**
Let the log of the incident rate depend on KRIs observed *before* the period: `log λ(s,t) = α(s) + f(KRIs at t−h)`, and compare out of sample with the constant-rate baseline, seasonal baselines and simple KRI threshold rules, using proper scoring rules, calibration, lead time and false alarm rate. Care is needed with KRIs that are derived from incidents and with publication lags. Whether this improves early warning is an open question, formulated as research question 1; the prototype does not show it.

**How would you validate this model?**
First fix the intended use. Then data mapping and quality checks, then a baseline on real data with dispersion, truncation and tail diagnostics, then backtesting of the components, out-of-sample tests, sensitivity and stability analysis, parameter uncertainty, benchmarking against alternatives, and independent validation under the institution's model risk governance. Backtests of annual aggregates have very little power (ten years give about 0.1 expected exceedances at 99%), so the components matter more. The full list is in [institutional_validation.md](institutional_validation.md), section 8.

**Extra questions to be ready for**

- *Why 1.8, 0.2, 1.1?* They are placeholders with no empirical basis; real values would come from structured expert elicitation and evidence.
- *Can I trust P99 from 19 incidents?* No. Parameter uncertainty is far larger than the Monte Carlo error (about 1% to 2% at 100,000 years); simulating more years does not fix it.
- *Does the stress include the effect on `PAYMENT_ENGINE_02`?* No. Systems are simulated one at a time; a joint common-shock model is a research item.
- *Do controls reduce the loss in the model?* No. Controls and KRIs are shown as evidence only.
- *Is this a capital model?* No. No regulatory capital claim, and nothing here follows any regulatory methodology.
- *What did you actually test about the agent?* The harness: tool calls, error handling, the loop, the provider interface, the number check, using a mock model. Not how a real model behaves or whether it helps analysts.
- *Does it use any data from a real bank?* No.

---

## Part 4. If something goes wrong

| Symptom | Fix |
|---|---|
| Red message "Cannot reach the RiskSignal API" | The API is not running. Start `uvicorn risksignal.api.main:app` (terminal 1) and refresh. |
| "Database: missing" in the sidebar, or the API reports `degraded` | Run `python -m risksignal.data.generator`, then restart the API. |
| The Assistant says the language-model provider is not configured | No `ANTHROPIC_API_KEY`. Either set it and restart the API, or restart the API with `RISKSIGNAL_LLM_PROVIDER=mock` and say so. The other pages never need a key. |
| The live agent is slow or fails | Fall back to the offline provider, or show a run you did beforehand. From a terminal: `python -m risksignal.agent.investigator --mock "Investigate PAYMENT_ENGINE_01."` prints the tool activity and answer. |
| The live agent shows a warning about numbers it could not match | Do not hide it. That is the check working; open the tool details and show whether the number is a rounding of a tool value or a real discrepancy. |
| Port 8000 or 8501 already in use | Start on another port (`--port 8001`, `--server.port 8502`) and set `RISKSIGNAL_API_URL` for the dashboard. |
| The numbers differ from section 1.4 | The data were regenerated with another seed, or settings changed. Re-run the generator with the default seed, or quote the screen rather than this script. |
| Streamlit page looks stale | Refresh the tab. |
