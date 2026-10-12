# Stochastic Model (V1)

This document explains the loss model in RiskSignal. Each section gives a plain English explanation first, then the equations.

> **Reminder.** The data are synthetic and every parameter is illustrative. The model demonstrates mechanics. It is not calibrated, validated or predictive, and its outputs are not capital figures. See [limitations.md](limitations.md).

Code: [`src/risksignal/stochastic/`](../src/risksignal/stochastic). The engine uses only numpy, pandas and pydantic. It never calls an LLM.

---

## 1. The big picture

**Plain English.** To ask "how much could technology incidents cost Atlas Bank in a year?", we need two ingredients: *how many* incidents happen, and *how costly* each one is. We describe each ingredient with a probability distribution fitted to the synthetic history. Then a computer plays out many imaginary years and records the total cost of each. The spread of those totals is the answer.

**Equations.** For one simulated year,

```
N ~ Poisson(lambda)                       number of incidents
X_1, ..., X_N ~ Lognormal(mu, sigma)      loss of each incident, independent
L = X_1 + X_2 + ... + X_N                 annual aggregate loss  (L = 0 if N = 0)
```

This is called a **frequency-severity** model; with Poisson frequency it is a **compound Poisson** model.

## 2. Frequency: how many incidents?

**Plain English.** `lambda` is the average number of incidents per year. Some years have fewer, some more. The Poisson distribution describes counts of events that happen independently at a steady average rate. We estimate `lambda` for a system by counting its historical incidents and dividing by the number of years observed. If a system has too few incidents for that to be trustworthy, the code says so and uses the bank-wide average per system instead. A user can also type in their own `lambda` to explore "what if" cases; the result is then labelled as a user-supplied assumption.

**Equations.**

```
N ~ Poisson(lambda),   P(N = k) = exp(-lambda) * lambda^k / k!,   E[N] = Var[N] = lambda

lambda_hat = n / T          n = incidents observed, T = years observed = days / 365.25
```

`lambda_hat = n / T` is the maximum likelihood estimate for a Poisson rate. The window `T` counts both end dates, so a window from 1 Oct 2021 to 30 Sep 2026 is 5.00 years. The estimate is only a rate if every counted incident happened inside that window, so the code raises an error if the incident table contains dates outside it, instead of silently inflating `lambda`.

Method labels in the output:

| `frequency_estimation_method` | Meaning |
|---|---|
| `system_history` | Estimated from this system's own incidents (at least 5 by default). |
| `bank_wide_per_system_average` | Estimated fallback: total incidents / years / number of systems. |
| `user_override` | User-supplied assumption. The historical rate is still shown for comparison. |

## 3. Severity: how costly is one incident?

**Plain English.** Most incidents are cheap and a few are very expensive. A loss cannot be negative, and the occasional very large loss stretches the distribution to the right ("right skew"). The Lognormal distribution has exactly these features, so it is a natural *illustrative* choice. It is not claimed to be correct for real bank losses. In this prototype the synthetic losses were generated from Lognormal distributions on purpose, so a good fit says nothing about reality.

The parameters live in **log space**. If you take the natural logarithm of every loss, you get roughly bell-shaped numbers. `mu` is the average of those logarithms and `sigma` is their standard deviation. Therefore:

- `exp(mu)` is the **median** loss, not the mean.
- A larger `sigma` means a heavier right tail, and the mean sits further above the median.
- `mu` and `sigma` are not the mean and standard deviation of the loss itself.

**Equations.**

```
X ~ Lognormal(mu, sigma)   <=>   ln X ~ Normal(mu, sigma^2),   X > 0

median(X) = exp(mu)
E[X]      = exp(mu + sigma^2 / 2)
E[X^2]    = exp(2*mu + 2*sigma^2)

mu_hat    = (1/n) * sum( ln x_i )
sigma_hat = sqrt( (1/n) * sum( (ln x_i - mu_hat)^2 ) )     (maximum likelihood)
```

Only strictly positive losses can be used, because `ln x` is undefined for `x <= 0`.

### Which losses are used (never switched silently)

The fit uses the most specific dataset that has at least 15 positive losses (an illustrative threshold, not a guarantee of stability):

1. **`system`**: the selected system's own losses (and category, if one was requested).
2. **`category`**: bank-wide losses of the requested category, only if a category was requested.
3. **`bank_wide`**: all bank-wide positive losses.

The result records `severity_data_source`, how many losses were used, and a note for every more specific level that was skipped and why. If even the bank-wide data are insufficient, the code raises an error instead of guessing.

Be aware that a fit based on 15 to 20 losses has large uncertainty (the standard error of `sigma` is roughly `sigma / sqrt(2n)`, about 16% for `n = 20`), and high percentiles are very sensitive to `sigma`. Parameter uncertainty is not propagated in V1.

## 4. Monte Carlo simulation

**Plain English.** The distribution of the yearly total has no simple formula, so we simulate it. For each imaginary year the computer draws the number of incidents, then draws a cost for each incident, then adds them up. After 100,000 imaginary years we have 100,000 possible annual losses and can ask how often they were small, medium or very large. The same random seed always reproduces the same simulation.

**Equations.** For `j = 1, ..., M` simulated years:

```
N_j ~ Poisson(lambda)
L_j = sum_{i=1}^{N_j} X_{j,i},   X_{j,i} i.i.d. Lognormal(mu, sigma), independent of N_j
```

The code draws all counts at once, then all severities at once, then adds severities within each year (`numpy.bincount`). Random draws always happen in the same order, so a seed fully determines the result.

**Sanity check (closed form).** For a compound Poisson model,

```
E[L]   = lambda * E[X]   = lambda * exp(mu + sigma^2 / 2)
Var[L] = lambda * E[X^2] = lambda * exp(2*mu + 2*sigma^2)
```

Each result includes `analytic_mean_annual_loss`, computed from this formula, next to the simulated mean. A large gap would signal a bug or too few simulations. The tests compare them within Monte Carlo standard error (`sqrt(Var[L] / M)`).

## 5. Risk metrics

**Plain English.** After simulating, we have a long list of annual losses.

- **Mean**: the average year.
- **Median**: the typical year; half of years are better and half worse.
- **P95 / P99** (95th and 99th percentile, also called Value-at-Risk): the loss exceeded in only about 1 year in 20 / 1 year in 100.
- **Expected Shortfall 95 (ES95)**: if P95 is the threshold exceeded in the worst 5% of simulated years, ES95 is the **average loss within those worst 5% of years**. It says how bad a bad year is once the P95 line is crossed. ES99 does the same for the worst 1%. Because it averages over the tail, ES is always at least as large as the matching percentile.

**Equations.** For level `alpha` (0.95 or 0.99):

```
VaR_alpha = inf { x : P(L <= x) >= alpha }
ES_alpha  = E[ L | L >= VaR_alpha ]
```

Estimators used on `M` sorted simulated losses:

- `VaR_alpha` is the empirical inverse CDF (`numpy.quantile(..., method="inverted_cdf")`), which matches the definition above exactly.
- `ES_alpha` averages the largest `M * (1 - alpha)` losses, giving a fractional weight to the boundary year if that number is not whole (Acerbi-Tasche form). This stays correct when many years have identical losses, such as zero, and guarantees `ES >= VaR`.

**Monte Carlo noise.** The 99% level rests on only 1% of the simulated years (1,000 of 100,000), so P99 and ES99 are noisier than the mean. Re-running with another seed shows how much they move. Measured in the technical review for focal-like parameters over 40 seeds, the relative standard deviation across seeds was about 0.5% for the mean, 0.6% for P95, 1.3% for P99, 1.1% for ES95 and 2.0% for ES99 at 100,000 simulations, and roughly 2.4 to 3.7 times larger at 10,000 (about the square root of 10 is expected). This noise is separate from, and much smaller than, the uncertainty from having only a few dozen synthetic incidents to estimate parameters.

## 6. How outputs are labelled

Every `SimulationResult` keeps the five kinds of number apart:

| Kind | Fields |
|---|---|
| Historical synthetic observations | `observed_incident_count`, `observation_years`, `severity_n_losses` |
| Estimated parameters | `lambda_used` (when method is not `user_override`), `severity_mu`, `severity_sigma` |
| User-supplied assumptions | `lambda_used` when `frequency_estimation_method == "user_override"` |
| Stress scenario assumptions | `scenario_*`, `stress_parameters` and `stress_metrics` in a scenario comparison. See [scenario_analysis.md](scenario_analysis.md). |
| Simulation outputs | `mean_annual_loss`, `median_annual_loss`, `p95`, `p99`, `expected_shortfall_95`, `expected_shortfall_99`, `histogram` |

The 100,000 simulated losses are not returned. A result carries the summary metrics and an optional 50-bin histogram over `[0, P99]`, plus a count of years above that range so nothing is hidden.

## 7. Assumptions and limitations of this model

- Incidents are independent and arrive at a constant average rate (Poisson). Real incidents cluster, vary over time and are usually over-dispersed.
- Severities are independent, identically distributed, and independent of the count.
- Lognormal tails may badly understate extreme losses. No tail-specific modelling is done.
- Parameters are treated as known; estimation uncertainty is ignored.
- Controls and KRIs do not affect the model in V1. They are shown as evidence only.
- Systems are simulated one at a time. No dependence between systems or through shared vendors is modelled.
- The default observation window should be given explicitly. If omitted, the first and last incident dates are used, which slightly shortens the window and raises `lambda`.

## 8. Not implemented (future research)

These need real data and domain expertise, and are deliberately left out of V1: Negative Binomial frequency, time-varying intensity `lambda(t)`, ML estimation of `lambda` from KRIs, Extreme Value Theory and Generalized Pareto tails, Hawkes processes, Beta-distributed control effectiveness, Graph Neural Networks, and propagation of parameter uncertainty. See [limitations.md](limitations.md) and [project_brief.md](project_brief.md).
