# Architecture

This document describes the architecture of RiskSignal as implemented. Run it locally or with Docker as described in the README.

## Overview

```
Synthetic Atlas Bank
        |
        v
SQLite data access
        |
        v
NetworkX dependency graph
        |
        v
Stochastic frequency-severity engine
        |
        v
Deterministic tool layer
        |
        v
AI investigation agent
        |
        v
FastAPI
        |
        v
Streamlit
```

Each arrow means "is used by the next layer". Dependencies point one way: lower layers never import upper layers.

## Layers

| Layer | Package | Responsibility |
|---|---|---|
| Synthetic Atlas Bank | `risksignal.data` | Generate a small, seeded, fictional dataset: systems, processes, vendors, controls, incidents, monthly KRIs. |
| SQLite data access | `risksignal.data` | Store the dataset in one SQLite file and provide typed read functions. |
| Dependency graph | `risksignal.graph` | Build a NetworkX directed graph from the database. Answer: which processes depend on a system, which vendors it uses, which systems share a vendor. |
| Stochastic engine | `risksignal.stochastic` | Estimate Poisson and Lognormal parameters from history, run seeded Monte Carlo simulations, compute mean, median, P95, P99, ES95, ES99, and apply predefined stress scenarios. |
| Tool layer | `risksignal.tools` | Small typed, read-only functions that wrap the layers above and return structured (pydantic) results. This is the only surface the agent can use. |
| Investigation agent | `risksignal.agent` | A simple tool-calling loop. It talks to an LLM through a small provider interface, executes the tools the LLM requests, and assembles the final summary. Includes a mock LLM for tests. |
| FastAPI | `risksignal.api` | A thin REST layer exposing the tools and the agent. |
| Streamlit | `risksignal.ui` | A simple dashboard calling the API. Presentation only. |

## Design principles

- **One-way dependencies.** The stochastic engine does not import the agent, the LLM or the UI. It can be tested with no network and no API key.
- **Business logic outside the UI.** Streamlit and FastAPI contain no modelling or data logic.
- **Simplicity.** One repository, one Python package, one SQLite file. No microservices, no graph database, no vector database, no agent framework.
- **Determinism.** Data generation and simulation accept seeds so that results are reproducible.
- **Provider isolation.** Only the agent package knows about a specific LLM vendor. Everything else is vendor neutral.

## Provenance of numbers

Every number in the system belongs to exactly one of five categories, and result objects will carry labels so readers can tell which:

1. historical synthetic observations,
2. estimated parameters,
3. user-supplied assumptions,
4. stress scenario assumptions,
5. simulation outputs.

## Why the LLM sits above deterministic tools

A language model is good at reading context, choosing what to look at next and writing clear prose. It is **not** a reliable calculator and it can state false things confidently. For a risk setting this matters:

- **Correctness.** Percentiles and Expected Shortfall come from a Monte Carlo simulation. A language model cannot execute one, and a plausible-looking number it made up would be worse than no number.
- **Reproducibility.** The same data, seed and assumptions must give the same result. A deterministic function does this. A language model does not.
- **Auditability.** Each fact in the answer can be traced to a specific tool call with specific arguments. A reviewer can check the evidence trail.
- **Safety by construction.** The agent can only call read-only tools. It cannot modify records, and it cannot produce numbers except by quoting tool results.
- **Testability.** Tools are ordinary Python functions with unit tests. The agent loop can be tested with a mock LLM.
- **Replaceability.** Because the LLM touches only the tool interface, the provider can be swapped without changing any risk logic.

In short, **the LLM chooses and explains, and Python computes and retrieves.**

## Agent output structure

When relevant, agent answers separate:

1. Observed evidence
2. Model assumptions
3. Simulation results
4. Suggested investigation questions

The agent may suggest questions for a human analyst. It does not make final risk decisions or declare systems safe or unsafe.

## Out of scope

Authentication, cloud infrastructure, real-time streaming, predictive machine learning and any write-capable tool are intentionally excluded. See [project_brief.md](project_brief.md).
