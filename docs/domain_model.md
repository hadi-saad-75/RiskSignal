# Domain Model: Operational Risk Concepts

This document explains the vocabulary used throughout RiskSignal. Each concept starts with a plain English explanation, followed by a more technical definition where useful.

All examples refer to **Atlas Bank**, a fictional institution. The data are synthetic.

---

## Operational Risk

**Plain English.** The chance that something goes wrong inside the bank's own machinery and costs money or disrupts service. The cause is not the market moving or a customer defaulting. It is a crashed system, a mistake, a failed supplier, a cyber attack, or a safeguard that did not work.

**Technical definition.** The Basel framework defines Operational Risk as the risk of loss resulting from inadequate or failed internal processes, people and systems, or from external events. It includes legal risk and excludes strategic and reputational risk. RiskSignal focuses on the **technology-related** part.

---

## Technology system

**Plain English.** A piece of software, with its infrastructure, that the bank runs. Examples: a payment engine, a customer login service, a reporting database.

**Technical definition.** A configuration item in the bank's technology inventory with an owner, a criticality level and relationships to other items. In RiskSignal each system has an ID such as `PAYMENT_ENGINE_01`.

---

## Business process

**Plain English.** A job the bank does for customers or for itself, such as "send a payment" or "open an account". Processes are what actually matter to the business. Systems matter because processes rely on them.

**Technical definition.** A defined sequence of activities producing a business outcome. A process **depends on** one or more systems. If a system fails, every process depending on it can be disrupted.

---

## Incident

**Plain English.** Something that went wrong and actually had an effect. A payment system was down for two hours. A software release broke a feature. A vendor service failed.

**Technical definition.** A recorded operational event with a date, an affected system, a cause category (for example deployment failure or vendor failure), a severity and, often, a financial loss. Incidents are the historical observations used to estimate how often events happen and how large they are.

---

## Financial loss

**Plain English.** The money an incident cost. This can include compensation to customers, regulatory fines, staff overtime to fix the problem, and the cost of repairs. Many incidents cost little or nothing. A few cost a lot.

**Technical definition.** The monetary amount attributed to an incident, in a single currency. Losses are non-negative and typically **right-skewed**: many small values and a few very large ones. That shape is why RiskSignal models them with a Lognormal distribution.

---

## Near miss

**Plain English.** Something that could have caused harm but did not, for example a faulty release caught just before it reached customers. No money was lost, but it is a warning.

**Technical definition.** An event with the potential to cause an operational loss but with zero realised loss because of a control, a detection or luck. Near misses are valuable leading signals. In RiskSignal V1 they are not part of the frequency-severity model, which uses actual incidents only.

---

## Control

**Plain English.** A safeguard designed to prevent a problem or reduce its damage. Examples: requiring two people to approve a software release, running a backup, or reviewing vendor performance every quarter.

**Technical definition.** A policy, procedure or technical mechanism intended to reduce the likelihood or impact of an operational risk event. Controls are typed (preventive, detective, corrective) and have an owner, a testing or review schedule and an assessed effectiveness. An **overdue review** means the control has not been checked when it should have been, which is a reason to ask questions, not proof that it has failed. RiskSignal V1 records controls as evidence and does **not** model their effect on losses.

---

## KRI (Key Risk Indicator)

**Plain English.** A dashboard dial that tells you whether risk is rising. Examples: number of failed deployments this month, percentage of patches overdue, system downtime minutes. If the dial drifts the wrong way, it is a prompt to look closer.

**Technical definition.** A measurable metric, observed periodically (here, monthly), used as a leading indicator of risk exposure. KRIs usually have thresholds (amber, red). RiskSignal V1 displays KRI trends as evidence. It does **not** use them to predict anything.

---

## External vendor

**Plain English.** A company outside the bank that supplies something the bank depends on, such as cloud hosting, a payment network connection, or a software licence.

**Technical definition.** A third party providing a service on which one or more internal systems rely. When several systems rely on the same vendor, a single vendor failure can hit all of them at once. This is **concentration risk**.

---

## Dependency

**Plain English.** "A needs B to work." If B fails, A is in trouble. Processes depend on systems, and systems depend on vendors and on other systems.

**Technical definition.** A directed relationship between two entities, modelled as an edge in a directed graph, for example `process -> system` or `system -> vendor`. Walking the graph answers questions such as "which processes are affected if this vendor fails?" and "which other systems share this vendor?". RiskSignal uses NetworkX for this.

---

## Risk scenario

**Plain English.** A "what if" story. For example: "What if our main payment vendor has a serious outage?" A scenario changes the assumptions and shows how the picture changes.

**Technical definition.** A defined set of assumptions applied to a model, such as a higher incident frequency or higher loss severity, to explore outcomes. RiskSignal separates a **baseline** (assumptions estimated from synthetic history) from a **stress scenario** (predefined, explicitly labelled adjustments). Scenario parameters are illustrative.

---

## Frequency

**Plain English.** How often incidents happen. "About 6 a year" is a frequency. Because the future is uncertain, one year might have 3 and another 9.

**Technical definition.** The distribution of the number of incidents `N` in a fixed period. RiskSignal uses a **Poisson** distribution: `N ~ Poisson(lambda)`, where `lambda` is the expected number of incidents per year. A Poisson model assumes incidents arrive independently at a steady average rate. `E[N] = Var[N] = lambda`.

---

## Severity

**Plain English.** How costly an incident is when it happens. Most are cheap. Occasionally one is extremely expensive.

**Technical definition.** The distribution of the loss `X` caused by a single incident. RiskSignal uses a **Lognormal** distribution: `ln X ~ Normal(mu, sigma^2)`. The parameter `mu` sets the typical size and `sigma` sets how heavy the right tail is. The mean is `E[X] = exp(mu + sigma^2 / 2)`.

---

## Monte Carlo simulation

**Plain English.** A way to explore uncertainty by playing out many imaginary years on a computer. In each imaginary year, the computer randomly decides how many incidents happen, randomly decides how costly each one is, and adds them up. After tens of thousands of imaginary years, we can see how often total losses are small, medium or very large.

**Technical definition.** Estimating properties of a random quantity by drawing many independent samples from the model. Here the annual loss is `L = X_1 + ... + X_N` (zero if `N = 0`), simulated `M` times to give `L^(1), ..., L^(M)`. From this sample we read off:

- mean and median annual loss,
- **P95 / P99** (percentiles): the loss level exceeded in about 1 year in 20 / 1 year in 100,
- **Expected Shortfall (ES)** at 95% and 99%: the average loss in the worst 5% / 1% of simulated years, defined as `ES_alpha = E[L | L >= VaR_alpha]`.

Simulations use a fixed random seed so results are reproducible. Estimates in the extreme tail (99%) are noisy unless `M` is large.

---

## How the concepts fit together

A **business process** depends on **systems**. Systems depend on **vendors** and are protected by **controls**. **KRIs** are dials that move over time. When something fails, it becomes an **incident** with a **financial loss**. History of incidents gives estimates of **frequency** and **severity**, and **Monte Carlo simulation** turns those into a distribution of possible annual losses. A **risk scenario** changes the assumptions to ask "what if". The investigation agent assembles all of this evidence for a human analyst.
