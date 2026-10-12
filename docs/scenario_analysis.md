# Scenario Analysis

This document explains the stress scenario engine in RiskSignal. Each idea is explained in plain English first, then with equations.

> **Reminder.** The scenario numbers in this prototype are **illustrative assumptions** chosen to demonstrate mechanics. They are not empirically calibrated, not validated by experts, and have **no institutional validity**. The data are synthetic. See [limitations.md](limitations.md).

Code: [`src/risksignal/stochastic/scenario.py`](../src/risksignal/stochastic/scenario.py).

---

## 1. What is a scenario?

**Plain English.** A scenario is a "what if", written down as explicit numbers. The baseline model says "based on the synthetic history, this system has about *this many* incidents per year, costing about *this much* each". A scenario says "now suppose incidents happen more often, and each one costs more". The engine then plays out many imaginary years under both sets of assumptions and shows the two results side by side.

A scenario is not a forecast and not an estimate. It is a deliberately chosen set of assumptions whose consequences we want to see. Its value is that the assumptions are **explicit, inspectable and changeable**, so an analyst can explore and challenge them.

**Equations.** The baseline model has three parameters, estimated from synthetic history (or supplied by the user):

```
N ~ Poisson(lambda)           X ~ Lognormal(mu, sigma)           L = X_1 + ... + X_N
```

A scenario is three numbers applied to those parameters:

| Scenario field | Applied as | Plain meaning |
|---|---|---|
| `lambda_multiplier` (m_lambda) | `lambda_stress = m_lambda * lambda` | How many times as many incidents per year. |
| `severity_mu_shift` (delta) | `mu_stress = mu + delta` | Shift of the log-median loss. The median loss `exp(mu)` is multiplied by `exp(delta)`. |
| `severity_sigma_multiplier` (m_sigma) | `sigma_stress = m_sigma * sigma` | Wider spread of log losses, so a heavier right tail. |

Each scenario also has an ID, name, description and a list of `assumption_notes` that say in words what was assumed and what was *not*. The defaults (1, 0, 1) change nothing.

Everything else is unchanged: the same model, the same number of simulations, and the **same random seed** for baseline and stress. Using the same seed means a scenario that changes nothing reproduces the baseline exactly, and differences between runs come from the assumptions, not from different random numbers.

## 2. What the engine returns

For one system and one scenario, a `ScenarioComparison` holds:

- **baseline parameters** and **stress parameters** `(lambda, mu, sigma)`, plus how they changed,
- **baseline metrics** and **stress metrics**: mean, median, P95, P99, Expected Shortfall 95 and 99,
- **absolute differences**: `stress - baseline` for every metric,
- **percentage differences**: `100 * (stress - baseline) / baseline` for every metric,
- the baseline's provenance (was lambda estimated from the system's own history, a bank-wide fallback, or a user override; which losses the severity fit used),
- the closed-form mean for both runs as a sanity check, the seed, the number of simulations, optional histograms, and a disclaimer.

Percentages are given only where they are mathematically meaningful. If a baseline metric is zero the percentage is `None`, since a change from zero has no percentage. `mu` has no percentage change because it lives in log space and can be zero or negative; its effect is multiplicative on losses (`exp(delta)`), which is reported through the absolute shift.

The baseline fields are never modified by the scenario. A baseline run through the scenario engine has the same parameters and metrics as a plain baseline simulation with the same seed.

### How the three levers interact

Because losses are Lognormal, the effect of a scenario on the *average* annual loss has a closed form:

```
E[L_stress] / E[L_baseline] = m_lambda * exp( delta + sigma^2 * (m_sigma^2 - 1) / 2 )
```

Two things follow. The `sigma` multiplier matters more when the baseline `sigma` is already large, because it enters through `sigma^2`. And tail measures such as P99 and Expected Shortfall 99 react to the heavier tail more strongly than the median does. Neither is a finding about the real world; both are properties of the Lognormal model.

## 3. Predefined demonstration scenario: `SHARED_VENDOR_OUTAGE`

An illustrative stress for a year in which an external vendor used by the system suffers outages. Intended for the demo on `PAYMENT_ENGINE_01`, which shares a vendor with `PAYMENT_ENGINE_02`.

| Parameter | Value | Meaning |
|---|---|---|
| `lambda_multiplier` | 1.8 | 1.8 times as many incidents per year. |
| `severity_mu_shift` | +0.20 | Median incident loss multiplied by `exp(0.20)`, about 1.22. |
| `severity_sigma_multiplier` | 1.10 | Spread of log losses 10% wider. |

What this scenario does **not** do:

- The values are not derived from data, not calibrated, and not produced or suggested by an LLM.
- It does **not** derive causal relationships. It does not read the dependency graph, does not know that a vendor is shared, and does not test whether an outage would produce these numbers. The user chooses the system to apply it to.
- It simulates one system at a time. A real vendor outage would hit every system using that vendor *at the same time*. That dependence between systems is not modelled.

## 4. User-supplied scenarios

An analyst can supply the three numbers directly, for example a frequency multiplier of 1.5 and a sigma multiplier of 1.2, with `make_user_scenario(lambda_multiplier=1.5, severity_sigma_multiplier=1.2)`. User scenarios are labelled `user_supplied`. Free-text scenario generation is deliberately not supported: turning a sentence into numbers is a judgement that belongs to a person, not to a model.

The numbers are checked against guard rails (for example, multipliers must be positive and `lambda_multiplier` at most 100). These bounds protect against typos and numerical overflow. They are **not** statements about what is realistic.

## 5. Why scenario assumptions require expert judgement

Choosing "1.8" is a claim about the world: how often a vendor fails, how long it lasts, how it propagates into incidents at the bank, and how that changes the loss per incident. History rarely contains enough comparable events to read these numbers off the data, because severe vendor events are rare by nature. Judgement is needed to decide:

- which events are plausible, severe but credible, and relevant to this institution,
- how a vendor event turns into frequency and severity changes on each affected system,
- how controls, redundancy, contracts and recovery arrangements change the picture,
- which systems fail together,
- when an assumption is too aggressive, too mild, or double counts something already in the baseline.

These questions are answered by people with knowledge of the technology estate, the vendors, the controls and past events: Operational Risk, technology, vendor management and business owners.

## 6. Why the synthetic multipliers are not institutionally valid

- The data are synthetic. Atlas Bank is fictional and its incidents were generated by a program.
- The multipliers were chosen by the prototype's author. Nothing links them to any real vendor, event or loss history.
- A model that is internally consistent is not therefore correct. The code can apply 1.8 faithfully while 1.8 has no real-world meaning.
- The Lognormal severity model is itself illustrative, and the synthetic losses were drawn from Lognormal distributions on purpose.
- No validation, backtesting or governance has been applied.

The scenario outputs therefore demonstrate **how** an analyst could explore assumptions, not **what** the assumptions should be.

## 7. How this could be calibrated in a future internship with Operational Risk specialists

None of the following is implemented. It is the work this prototype is meant to make easier to discuss.

1. **Design scenarios with subject matter experts.** Run structured workshops with Operational Risk, technology resilience and vendor management to define a small set of plausible, severe but credible scenarios, and write down the narrative before any number.
2. **Translate narratives into parameters using evidence.** Use the institution's internal loss data, near misses and incident records for similar events, external loss data for vendor and technology events, vendor service-level reports, and past outage durations to anchor frequency and severity changes.
3. **Elicit uncertain numbers in a structured way.** Use documented expert elicitation (ranges and quantiles instead of single values, with challenge from several experts) so each multiplier comes with a plausible range and a rationale.
4. **Run sensitivity analysis.** Vary each lever across its range to see which assumptions drive the result, and show decision makers that sensitivity instead of a single stress number.
5. **Model the shared vendor properly.** Connect scenarios to the real dependency map so that a vendor event affects all dependent systems together, with dependence between them. This turns a per-system stress into a joint scenario and reveals concentration risk.
6. **Reflect controls and recovery.** Link scenario severity to the effectiveness of controls, failover arrangements and recovery times, using real control testing evidence.
7. **Review the model form.** Test whether Poisson and Lognormal are adequate under stress, and consider alternatives for clustering and extreme tails (listed as future research, not built).
8. **Validate and govern.** Independent challenge, backtesting against historical events where possible, documentation of limitations, approval, change control and periodic review under the institution's model risk governance.
9. **Respect confidentiality and security.** Use approved data access and approved tooling, and keep scenario design and results within the institution's information controls.

## 8. Not implemented

Free-text or LLM-generated scenarios, automatic derivation of scenario numbers, joint multi-system scenarios, scenario probabilities, and any connection between scenarios and the dependency graph. See [project_brief.md](project_brief.md) and [limitations.md](limitations.md).
