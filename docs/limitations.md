# Limitations

RiskSignal is a **research prototype**. This document states plainly what it is not. These limitations apply to every part of the project.

## What this prototype does not claim

1. **The dataset is synthetic.** Atlas Bank is fictional. All systems, vendors, controls, incidents, losses and KRIs are generated. Some relationships are deliberately constructed to make the demonstration readable, so findings are properties of the constructed data, not discoveries about the real world.
2. **The model is illustrative.** The Poisson frequency and Lognormal severity parameters, and any stress scenario multipliers, are chosen or estimated only to demonstrate the mechanics.
3. **There is no claim of predictive validity.** The prototype has not been validated or backtested and must not be used to forecast losses.
4. **There is no institution-specific calibration.** Nothing is fitted to a real institution's loss history, controls or technology landscape.
5. **There is no regulatory capital claim.** Outputs such as P99 or Expected Shortfall are not capital figures and do not follow any regulatory methodology.
6. **There is no JPMorgan data.** No data, taxonomy, process or model from JPMorgan or any other real bank is used or implied.
7. **There is no production security.** There is no authentication, access control, encryption, audit logging or data classification. The software is not suitable for confidential data.
8. **The AI makes no final Operational Risk decision.** The agent gathers evidence, runs predefined tools, and suggests questions. It never declares a system safe or unsafe, never decides on remediation, and never modifies records.

## Modelling limitations

- **Poisson frequency** assumes incidents are independent and arrive at a constant average rate. Real incidents cluster, vary over time, and are often over-dispersed (variance larger than the mean).
- **Severity is drawn from a Lognormal by construction.** The synthetic generator itself samples incident losses from Lognormal distributions, so a Lognormal fit to this data is circular. A good fit is not evidence that real losses are Lognormal.
- **Lognormal severity** may understate extreme losses. No dedicated tail modelling is performed.
- **Independence.** Severities are assumed independent of each other and of the number of incidents. No dependence between systems or vendors is modelled in the baseline.
- **Parameter uncertainty is ignored.** Estimated parameters are treated as known, although small samples make them uncertain. This uncertainty is much larger than the Monte Carlo error (tens of percent against 1% to 2% for P99 and ES99 at 100,000 simulations; see [technical_review.md](technical_review.md)), and simulating more years does not reduce it.
- **Small samples.** A few hundred synthetic incidents spread over about twenty systems give unstable estimates. P99 and Expected Shortfall at 99% are especially noisy.
- **Controls** are recorded as evidence. Their effect on frequency or severity is not modelled.
- **KRIs** are displayed as evidence. They are not used to predict incidents.
- **Stress scenarios** are simple predefined assumption changes, not scenarios designed with subject matter experts. Baseline and stress are simulated from common random numbers, which reduces but does not remove sampling noise in the reported differences.
- **No part of the prototype has been validated.** Passing tests show the code implements the stated mathematics, not that the model describes any real institution. See [technical_review.md](technical_review.md), section 7.

## AI limitations

- A language model can write fluent text that is wrong. The design reduces this risk by forbidding the model from producing numbers and requiring that facts come from tool results, but human review remains essential.
- Answers depend on the quality of tool outputs and the provided data, which are synthetic.

## Future work requiring institutional expertise and data

These items are intentionally absent. They are the work that could only be done properly with a real Operational Risk team:

- institution-specific internal and external **loss data**,
- actual **KRIs** and thresholds,
- actual **control** inventories, testing results and effectiveness evidence,
- actual **technology and vendor dependency** maps,
- the institution's **Operational Risk taxonomy**,
- **scenario design** with subject matter experts,
- **frequency calibration** and **severity calibration**,
- **tail modelling**,
- model **validation** and **backtesting**,
- **model risk governance** (documentation, independent validation, change control),
- **security and integration** with existing systems, including approved use of LLMs.

These are organised into phases in [institutional_validation.md](institutional_validation.md).

## Possible research directions (not implemented)

These need better data and domain expertise before they are meaningful. They are formulated as research questions, with data requirements and evaluation designs but no results, in [research_extensions.md](research_extensions.md):

- Negative Binomial frequency models,
- time-varying intensity `lambda(t)`,
- ML estimation of `lambda` from KRIs (for example XGBoost or tabular foundation models such as TabPFN),
- Extreme Value Theory and Generalized Pareto tail modelling,
- Hawkes (self-exciting) processes,
- Beta distributions for uncertain control effectiveness,
- Graph Neural Networks on the dependency graph.

An open question, deliberately **not** answered by this prototype:

> Can modern AI and machine learning improve early identification of deteriorating Operational Risk conditions when combined with classical frequency-severity modelling?
