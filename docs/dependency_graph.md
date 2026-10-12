# Dependency Graph

This document explains the dependency graph in RiskSignal from zero. Each idea is explained in plain English first, then with notation.

> **Important limitation.** A real bank dependency graph would require **verified configuration, service, process and vendor data** (for example from a configuration management database, service catalogues, process inventories and vendor registers, kept up to date and reconciled). The graph in this prototype is built from **synthetic** data and demonstrates **reasoning mechanics only**. It says nothing about any real institution. See [limitations.md](limitations.md).

Code: [`src/risksignal/graph/`](../src/risksignal/graph). Uses NetworkX only (no graph database, no machine learning).

---

## 1. What is a node?

**Plain English.** A node is a *thing* we want to talk about, drawn as a dot on a map. In RiskSignal there are four kinds:

| Node type | Example | Meaning |
|---|---|---|
| system | `PAYMENT_ENGINE_01` | A piece of software the bank runs. |
| process | `P01` International Payments | A job the bank does for customers or itself. |
| vendor | `V04` Keystone Payment Rails | An external company the bank depends on. |
| control | `C002` Pre-Release Regression Testing | A safeguard attached to a system. |

## 2. What is an edge?

**Plain English.** An edge is a *relationship* between two nodes, drawn as an arrow. The arrow has a direction and a label saying what the relationship is.

| Edge | Reads as | Source of the data |
|---|---|---|
| `SYSTEM --SUPPORTS--> PROCESS` | "this system helps run that process" | `dependencies` table |
| `SYSTEM --DEPENDS_ON--> VENDOR` | "this system relies on that vendor" | `dependencies` table |
| `SYSTEM --DEPENDS_ON--> SYSTEM` | "this system relies on that other system" | `dependencies` table |
| `SYSTEM --PROTECTED_BY--> CONTROL` | "this control safeguards that system" | `system_id` in the `controls` table |

The graph is built directly from the SQLite tables. Nothing is typed in by hand in the graph code. Incidents are deliberately **not** nodes: the graph describes structure, and incident history is retrieved from the data tables.

## 3. Why a graph is useful

Looking at each system alone answers "what happened to this system?". Many Operational Risk questions are about **connections**:

- Which other systems use the same vendor?
- If this system fails, which processes and systems are affected?
- Which vendors are reached only indirectly, through another system?

Those answers are hidden if each system is examined in isolation, but they are quick to read off a graph, because we can simply **follow the arrows**.

### Example: PAYMENT_ENGINE_01 and PAYMENT_ENGINE_02

```
  PAYMENT_ENGINE_01 --DEPENDS_ON--> V04 Keystone Payment Rails <--DEPENDS_ON-- PAYMENT_ENGINE_02
          |                                                                          |
          +--DEPENDS_ON--> V02 Vertex Messaging Networks            V01 NimbusCloud <--+
```

Suppose `PAYMENT_ENGINE_01` has had several recent incidents and `PAYMENT_ENGINE_02` has had none. Looking only at incident counts, `PAYMENT_ENGINE_02` looks fine. The graph shows that both depend on vendor `V04`. If the vendor is a common cause of trouble, `PAYMENT_ENGINE_02` is exposed to the same source even though nothing has happened to it yet. An analyst may therefore still choose to investigate it. This is called **concentration risk**: several systems relying on one supplier.

The graph does not say that `PAYMENT_ENGINE_02` will fail or even that it is risky. It says the two systems share an exposure, which is a good question to ask.

## 4. What the queries return

All queries return structured Pydantic objects (never raw NetworkX objects) and raise a clear error for an unknown system instead of returning an empty answer.

| Function | Answers |
|---|---|
| `get_system_dependencies` | Direct vendors; upstream systems (what it depends on) and downstream systems (what depends on it), with the number of hops and the systems in between; and vendors reached only indirectly, with the nearest system they come through. |
| `get_shared_vendors` | Direct vendors that at least one other system also uses, and which systems. |
| `get_related_systems` | Systems linked through a shared vendor or a shared business process, each relationship explained in a sentence. |
| `get_controls_for_system` | Controls attached to the system, with review dates and counts by review status. |
| `get_supported_processes` | Processes the system supports, with the primary one flagged. |
| `get_neighbor_summary` | A compact overview of all of the above for one system. |

"Related" means **structurally linked**. It does not mean that a failure in one system causes a failure in the other.

## 5. The mathematical notation

A graph is written

```
G = (V, E)
```

**V** is the set of **vertices** (nodes), the things. **E** is the set of **edges**, the relationships between them.

In RiskSignal the node set is the union of four kinds of things:

```
V = S ∪ P ∪ W ∪ C        S = systems, P = processes, W = vendors, C = controls
```

Edges are *directed*: an edge is an ordered pair `(u, v)` with `u, v ∈ V`, drawn as an arrow from `u` to `v`, so `E ⊆ V × V`. Each edge also carries a label from a small set of relations. Writing `s → v` for "`(s, v) ∈ E`":

```
E_supports     = { (s, p) : s ∈ S, p ∈ P }     SUPPORTS
E_depends      = { (s, w) : s ∈ S, w ∈ W }  ∪  { (s, t) : s, t ∈ S }     DEPENDS_ON
E_protected_by = { (s, c) : s ∈ S, c ∈ C }     PROTECTED_BY

E = E_supports ∪ E_depends ∪ E_protected_by
```

**Neighbours and sharing.** The vendors directly used by system `s` are

```
W(s) = { w ∈ W : (s, w) ∈ E_depends }
```

Systems `s` and `t` have shared vendors when the intersection is not empty:

```
W(s) ∩ W(t) ≠ ∅
```

For the example, `W(PAYMENT_ENGINE_01) ∩ W(PAYMENT_ENGINE_02) = {V04}`. Systems sharing a business process are found the same way, using the sets of processes `P(s) = { p : (s, p) ∈ E_supports }`.

**Indirect dependencies.** A *path* is a sequence of edges `s → t₁ → t₂ → … → tₖ`. System `s` depends indirectly on `tₖ` if such a path exists through system-to-system DEPENDS_ON edges. The number of edges in the shortest path is the number of **hops**. A vendor `w` is an *indirect vendor* of `s` if `w ∉ W(s)` but `w ∈ W(t)` for some system `t` that `s` depends on through such a path. Paths are found by breadth-first search.

## 6. How it is implemented

- NetworkX `DiGraph`. Node keys are prefixed with their type (`system:PAYMENT_ENGINE_01`, `vendor:V04`), so identifiers of different types can never collide.
- Node attributes copy the table columns (name, criticality, review status and so on). Edges carry a `relation` attribute, and SUPPORTS edges record whether the process is the system's primary process.
- The builder refuses rows that refer to entities that do not exist, instead of silently creating them.
- Query results are sorted, so they are deterministic.
- Circular system dependencies are handled (breadth-first search visits each system once).

## 7. What the graph does not do

- It does not estimate probabilities, propagate losses or simulate contagion between systems. The stochastic engine still treats each system on its own.
- It does not weight edges (for example by how critical a dependency is) and does not distinguish how a system uses a vendor.
- It is not connected to scenarios. Scenarios do not read the graph. The graph only supplies facts for an analyst, or for the agent, to ask better questions.
- It contains no incident, KRI or loss data.
- It does not use machine learning or graph neural networks (listed only as future research).

## 8. Limitation, again

The synthetic graph shows how structural reasoning works. Whether `V04` really is a single point of failure, which dependencies are real, which are only logical, and how dependency changes over time can only be established with verified data from the institution's configuration, service, process and vendor inventories, and with the people who know them.
