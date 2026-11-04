# Agent Design

This document explains how the RiskSignal investigation agent works and why it is built the way it is.

> All data are synthetic and all model parameters are illustrative. The agent supports human analysts and makes no risk decisions. See [limitations.md](limitations.md).

Code: [`src/risksignal/agent/`](../src/risksignal/agent).

---

## 1. What makes this agent different from a chatbot

A general chatbot answers from what its language model "knows" and from the conversation. This agent is built on the opposite principle: **the model is given no knowledge of the institution and is instructed to calculate nothing**; every fact and number is supposed to come from a tool. Instructions are not guarantees, so the code also checks what the model writes (section 3).

| A general chatbot | The RiskSignal agent |
|---|---|
| Answers from its training and whatever it is told | Answers only from tool results retrieved in this conversation |
| Can produce any number that sounds plausible | Obtains every number from a deterministic Python tool |
| Free-form conversation on any topic | Investigates one selected technology system (or answers a narrow question about it) |
| Can say a system is "high risk" | Presents evidence and questions; never gives verdicts |
| Leaves no record of how an answer arose | Records every tool call: name, input, status, time and result |
| Cannot change anything either, but nothing prevents it from claiming to | Read-only by construction: no tool writes or modifies records |

What the agent does is **decide which tools to call**. For "Investigate PAYMENT_ENGINE_01" it would normally look at the system profile, recent incidents, recent KRIs, controls, dependencies and a baseline simulation. It runs the stress comparison only if the user asks for it or the evidence makes it relevant, and it does not call tools the question does not need. A narrow question such as "What incidents affected this system?" needs one tool.

## 2. How an investigation runs

```
analyst question
      |
      v
  Investigator loop  <------------------------------+
      |                                              |
      v                                              |
  LLM provider (Anthropic live / mock in tests)      |
      |  requests tools?                             |
      +-- yes --> Tool registry --> deterministic tools --> results (JSON)
      |
      +-- no  --> final answer + tool activity log + warnings
```

1. The question and the system prompt go to the language model, together with the list of seven tools and their input schemas.
2. If the model asks for tools, the registry validates the arguments, runs the real Python tools and sends the JSON results back.
3. This repeats until the model writes its final answer, or a step limit (10 model turns) stops it.
4. The result contains the answer, a tool activity log, warnings, and the structured output of every tool.

The agent is a short, plain loop. No agent framework is used.

## 3. Why calculations stay outside the language model

- **Correctness.** Percentiles and Expected Shortfall come from a Monte Carlo simulation. A language model cannot run one. A plausible number it made up would be worse than no number.
- **Reproducibility.** The same data, seed and assumptions give the same result from a Python function. They do not from a language model.
- **Verifiability.** Each number in an answer can be matched to a tool output. If it cannot be matched, that is visible.
- **Separation of duties.** The model reads, chooses, explains and organises. Python retrieves and calculates. Neither does the other's job.
- **Replaceability.** Because the model only touches the tool interface, it can be swapped (or mocked in tests) without changing any risk logic.

The model is also told not to add, subtract, average or compute percentages itself, and to use values the tools return (for example the scenario comparison's `percentage_differences`).

### Two layers of enforcement

Instructions to a language model are not guarantees, so the design does not rely on the prompt alone.

| Rule | In the system prompt | Enforced in code |
|---|---|---|
| Read-only, no data changes | Yes | There is no write tool. |
| No direct database access | Yes | The agent package imports no `sqlite3`, `pandas`, `numpy`, or data and graph modules (tested). Tools use fixed SQL with bound parameters. |
| No invented tools or arguments | Yes | The registry rejects unknown tools, missing or unexpected arguments with a typed error. |
| Only predefined stress scenarios | Yes | The scenario ID is an enum in the tool schema, and the tool rejects anything else. |
| Numbers must come from tools | Yes | After the run, the answer is scanned and any number that matches no tool output is listed in `ungrounded_numbers` with a warning. |
| Failures are reported, not hidden | Yes | Tool errors reach the model flagged as errors, and appear in the activity log. |
| No runaway loops | n/a | Step limit, with a clear status and warning. |
| No secrets | n/a | The API key comes from the environment and appears in no output; a test scans the repository for key-shaped strings. |

## 4. Human in the loop

The agent is an assistant for an analyst, not a decision maker.

- It **may**: retrieve information, query dependencies, run simulations, compare scenarios, summarise evidence and suggest questions to investigate.
- It **may not**: modify risk records, make final risk decisions, call a system safe or unsafe, invent incidents, controls or numbers, or take remediation actions.
- Its output ends in **suggested investigation questions** for a person, for example "Should control C002 be retested?" rather than "Retest control C002."
- Outputs always state that the data are synthetic and the model is illustrative, and describe simulation results as **outputs under stated assumptions, not forecasts**.
- A shared vendor or process is presented as a **shared exposure to investigate**, not as evidence that one failure causes another.

A human analyst decides what, if anything, to do with the answer.

## 5. Auditability

Every investigation returns an `InvestigationResult` containing:

- **Tool activity**: for each call, its order, tool name, exact input, status (`completed` or `failed`), error type, start time, duration, a one-line summary and the structured output the model received. Summaries are written in Python from the tool results (for example "Retrieved 12 months of incidents (5 found)" and "Ran 100,000 year Monte Carlo simulation (seed 42)"), so they are suitable for display in a UI and cannot be altered by the model.
- **The final answer** and **warnings**: ungrounded numbers, truncated or empty answers, step limits.
- The provider used, the number of model calls and a disclaimer.

A reviewer can replay any tool call and obtain the identical result, because tools are deterministic and simulations take an explicit seed.

The model's internal reasoning is **not recorded or exposed**. What is exposed is the final answer and what the agent did.

## 6. Model providers

The agent depends only on a small interface, `LLMProvider.complete(system, messages, tools, max_tokens)`, with provider-neutral message types.

- **`AnthropicProvider`**: live implementation using Anthropic tool calling. It reads `ANTHROPIC_API_KEY` from the environment (or a local `.env` file, which is git-ignored). The model name comes from `ANTHROPIC_MODEL` or defaults to a value defined in the provider. SDK errors become a single `LLMProviderError` without secrets.
- **`MockProvider`**: deterministic. It replays scripted tool requests and answers. `investigation_script(system_id)` provides a ready-made plan whose final summary is composed only from the tool results it received. Automated tests use it and never call any API.

### Running it

Offline, no API key (deterministic mock):

```bash
python -m risksignal.agent.investigator --mock "Investigate PAYMENT_ENGINE_01."
python -m risksignal.agent.investigator --mock --stress "Investigate PAYMENT_ENGINE_01."
```

Live check with Anthropic (needs `ANTHROPIC_API_KEY`; sends only synthetic data to the API):

```bash
python -m risksignal.agent.investigator "Investigate PAYMENT_ENGINE_01."
python -m risksignal.agent.investigator --model <model-name> "What controls protect PAYMENT_ENGINE_02?"
```

Both print the tool activity, the answer and any warnings. Generate the data first with `python -m risksignal.data.generator`.

## 7. Limitations

- **A language model can still be wrong.** It may misread a tool result, misstate a relationship, or ignore an instruction. The prompt and the code checks reduce this risk but do not remove it. Human review remains essential.
- **The number check is best-effort.** It catches figures that match nothing the tools returned. It cannot catch a real number attached to the wrong thing (for example the P99 described as the P95), a wrong ID, or a false qualitative claim. An empty `ungrounded_numbers` list is not proof that the answer is right. Whole numbers up to 20 and identifiers or dates are not checked.
- **Free text in data is untrusted input.** Incident descriptions come from the database and are passed to the model. In this prototype they are synthetic and harmless. With real data, text could contain instructions that attempt to steer the model (prompt injection), and would need handling.
- **No live evaluation yet.** The live provider is tested with a stand-in client for message conversion and the loop, not against the real API. The behaviour of a real model (how well it follows the prompt, which tools it picks) has not been evaluated here, and the default model name is an assumption that may need overriding with `ANTHROPIC_MODEL`.
- **Non-deterministic when live.** Tools are deterministic, but a live model's choice of tools and wording can vary between runs. The mock is fully deterministic.
- **Conversation memory is short and textual.** The investigation endpoint answers one question per run. The assistant (`POST /agent/chat`) keeps context by receiving the last turns as plain text; earlier tool outputs are not resent, so a follow-up that needs fresh data calls the tools again.
- **No authentication, access control or production audit store.** Activity records are returned to the caller, not persisted.
- **Not an institutional tool.** Real use would need institution data, approved model governance, security review and approved LLM usage. See [project_brief.md](project_brief.md).
