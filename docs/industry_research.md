# Industry research and requirements

Research date: 6 November 2026. Purpose: select credible improvements to the existing RiskSignal prototype, not estimate market size.

## 1. Evidence quality and scope

The final [job evidence register](research/job_evidence.csv) contains **34 distinct roles**, with full source URLs, location, date evidence, access quality, paraphrased requirements, classification and limitations. Requisition/location variants were deduplicated. Initial title-only leads, unknown employers, generic careers landing pages and unrecoverable truncated URLs were not used for requirement counts.

**This is not 34 fully retrieved, publication-date-verified 2025-2026 AI operational-risk job descriptions.** It is a mixed-depth exploratory corpus:

- 26 employer/official ATS sources: **5 full descriptions** and **21 indexed description excerpts**.
- 8 mirrors/employer LinkedIn listings: **1 full description** and **7 indexed excerpts**.
- 13 AI-risk/governance roles, 8 roles applying AI/automation to risk work, 5 foundational operational/control roles, and 8 adjacent quantitative/analytics/engineering roles.
- Explicit 2025-2026 posting/update dates are retained where visible. Closing dates, start dates and undated descriptions are distinguished. A search crawl date, a company award year, a relative “posted recently” timestamp or a future internship start does **not** establish publication date.

London, Paris/La Defense/Pantin, Lisbon, Madrid, Amsterdam, Zurich, Warsaw and Nordic financial centres are represented. US, Canadian and Asian roles are labelled comparators, not evidence of European hiring volume. London headquarters do not establish job location: the Man enterprise-risk analyst is in **Sofia**, HSBC's advisory role is in **Bengaluru**, and Aviva's role explicitly excludes London.

Many official bank ATS pages returned 403/404/410, JavaScript shells or closed-job notices. Indexed excerpts demonstrate only the responsibilities actually visible, not the entire job. Missing tags mean **not confirmed**, not that employers do not require a skill. Prefer the full-description subset for detailed interpretation. The curated sample overrepresents discoverable large employers and AI governance; it is not representative of the labour market. It cannot measure year-on-year demand, prove production deployment, or justify invented percentages of institutions adopting a technology.

### Strongest directly useful examples

| Evidence | Actual business need | Consequence for this application |
|---|---|---|
| J25: [Man Group enterprise-risk analyst](https://builtin.com/job/risk-analyst-enterprise-risk/7644567), full mirror | Risk/control records, attestations, KRIs, issues, vendor lifecycle, data quality, dashboards, automated workflows and AI-assisted review/challenge. Excel, Power BI and Power Automate are named. | Evidence collation and exception review are more useful than another generic conversation page. |
| J27: [EY wealth/asset-management risk consulting](https://careers.ey.com/ey/job/London-Senior-Consultant%2C-Wealth-&-Asset-Management%2C-Risk-&-Regulatory-Advisory-E14-5EY/1447704033/), full official | RCSAs, control environments, automated testing/monitoring, data/AI transformation and responsible human-led governance. | Prepare source-linked RCSA review evidence, but do not pretend control review dates are operating-effectiveness tests. |
| J16: [Swiss Re AI technology-risk manager](https://www.swissre.com/careers/job/Senior-Digital-and-Technology-Risk-Manager-Hybrid-m-f-x-d-80-100-/1448562033), full official | Second-line AI policies, control objectives, KRIs, independent challenge, committee reporting, GenAI/agentic risks; NIST AI RMF/ISO 42001 familiarity. | Make methodology, limitations and human ownership visible. AI engineering is not required for every AI-risk role. |
| J19: [Aviva AI model-risk lead](https://aviva.talent-community.com/projects/ai-model-risk-governance-lead/74590), full employer page | Independent review of ML/AI performance, quantitative assumptions and governance, including operational decision models. | Demonstrate temporal evaluation and transparent pooling, not unsupported model-accuracy claims. |
| J23: [Wells Fargo NLP/GenAI validator](https://www.wellsfargojobs.com/en/jobs/r-582033/quantitative-model-validator-nlp-and-gen-ai-agentic-ai/), full official | Sampling, replication, performance assessment, reusable validation libraries, monitoring and analytical reports; Python/Java and PyTorch/TensorFlow/Keras are desired. | Test evidence fidelity, temporal separation and failure cases. An offline scripted provider does not validate a live LLM. |
| J10: [ING NFR solutions specialist](https://careers.ing.com/de/stellenbeschreibung/madrid/non-financial-risk-solutions-specialist-1lod/3121/42491872704), official excerpt | End-to-end controls, root causes, structural prevention, issues/events, resilience and third parties in an AI-adoption context. | Support linked incident/control/KRI investigation, without asserting causality from co-occurrence. |
| J21: [JPMorgan model-risk programme associate](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1002/job/210747764/), official excerpt | Build AI/LLM-native tools for validation/governance processes, as well as review AI models. | Extend the existing bounded tool-calling assistant rather than build an unconstrained multi-agent replacement. |
| J31: [BNP AIR Tech internship, Paris](https://www.efinancialcareers.fr/emploi-France-Paris-Stage_-_Data_Scientist_-_HF_-_6_mois_-_BNP_Paribas.id23416841), mirror excerpt with 2025 start | RISK/Compliance GenAI and RPA, RAG/GraphRAG, prompt tuning, explainability, CI/CD and multi-agent research. | Document intelligence is a credible next experiment, but needs an approved corpus and retrieval/citation evaluation first. |
| J32: [BNP AI/ML operational-risk officer, Lisbon](https://www.cybersecurityjobsite.com/job/5433652/operational-risk-officer-artificial-intelligence-and-machine-learning-expert/), mirror excerpt, 2025 closing date | Second-line AI/ML use-case oversight, lifecycle understanding and coordination with operational-risk officers. | Distinguish using AI for risk analysis from governing the bank's own AI use cases. |
| J33: [Citi risk Python developer, London](https://jobs.citi.com/job/london/python-counterparty-credit-risk-senior-developer-vice-president/287/95630921568), official excerpt | Efficient tested Python analytics, model integration, Git/Jenkins/CI/CD and production support. | Good engineering is relevant, but counterparty-credit analytics are adjacent evidence, not proof of operational-loss model demand. |

## 2. Ranked recurring requirements

Binary coding: one tag per role if explicit in the reviewed description/excerpt; each role counts at most once per tag. Denominator **34**, including the explicitly labelled adjacent and undated roles. These are **observed lower-bound counts in this corpus**, not industry prevalence. Mandatory and desirable requirements are not conflated: the register notes the distinction where visible.

| Rank | Requirement/application tag | Roles with evidence |
|---|---|---:|
| 1 | Operational/business risk controls, review or assurance (`risk_controls`) | 18 |
| 2 | AI lifecycle governance and independent challenge (`ai_governance`) | 16 |
| 3 | Decision-useful reporting/documentation (`reporting`) | 11 |
| 4= | Model validation, quantitative checks or explainability evaluation (`model_validation`) | 10 |
| 4= | Workflow/process automation (`automation`) | 10 |
| 6 | Statistical/quantitative modelling (`quantitative_methods`) | 9 |
| 7= | Monitoring, indicators or model drift (`monitoring`) | 8 |
| 7= | Explicit GenAI, LLM or NLP (`genai_nlp`) | 8 |
| 9= | Named regulatory/governance framework (`named_framework`) | 5 |
| 9= | Explicit agentic/multi-agent AI (`agentic`) | 5 |
| 11 | Explicit Python or SQL (`python_sql`) | 4 |
| 12 | Explicit resilience/third-party operational lifecycle (`resilience`) | 2 |

The broad model-validation tag includes explainability/model assurance and is **not** ten dedicated independent-validation vacancies. “Monitoring” spans controls, indicators and AI models; eight mentions are not eight requests for ML-based KRI anomaly detection. The resilience count is particularly incomplete because many sources were partial excerpts.

Recompute counts locally without dependencies:

```powershell
@'
import csv
from collections import Counter
with open(r"docs\research\job_evidence.csv", encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
print("Denominator:", len(rows))
print(Counter(tag for row in rows for tag in row["tags"].split("|")).most_common())
'@ | python -
```

### Practical technical skill priorities

1. **Risk data and control reasoning:** reconcile records, identify evidence gaps, understand RCSA/KRI/events/three lines of defence, and communicate challenge. Domain correctness takes priority over an impressive model.
2. **Reproducible quantitative implementation:** Python, SQL, statistical assumptions, sample/exposure definitions, temporal evaluation, pooling disclosure and tests. Named-language evidence is concentrated in technical roles, not policy roles.
3. **Automation and reporting:** reliable data pipelines, structured evidence packs, dashboards and committee-ready drafts. Power BI/Excel/Power Automate are explicit in J25; Streamlit demonstrates transferable workflow skills, not experience with those proprietary tools.
4. **Applied GenAI/NLP:** constrained tool use, retrieval/citations, evaluation and explainability. RAG/GraphRAG/fine-tuning in J31 are research/delivery options, not universal baseline requirements.
5. **AI governance and lifecycle monitoring:** risk inventory, independent validation, model limitations, drift, third-party AI and human accountability. Examples include SS1/23, NIST AI RMF and ISO 42001, with institution/jurisdiction-specific scope.
6. **Production software delivery:** modular services, type-safe boundaries, exception handling, Git, CI/CD and reusable validation libraries. Demonstrating a maintainable small system is stronger than adding infrastructure without a business case.

## 3. Established needs, growing themes and experiments

**Established needs:** risk/control records, RCSA, incident/issue processes, data quality, KRIs, audit evidence, quantitative challenge and management reporting. These remain valuable without generative AI. J01/J02/J06/J25/J27 anchor the ordinary risk workflow.

**Growing themes suggested by current job wording, not measured growth rates:** embedding AI into existing risk/assurance functions; second-line oversight of enterprise GenAI; AI-enabled control monitoring; reusable validation tooling; translating technical findings into committee decisions. J16/J19/J21/J23/J27 give direct examples.

**Experimental or selectively deployed:** agentic/multi-agent workflows, GraphRAG, autonomous decision support and fine-tuning. Postings demonstrate interest or responsibilities, not measured reliability or enterprise-wide rollout. A role governing agentic AI does not mean agents should automatically approve a control, determine legal applicability or close an incident.

### Business applications, ranked for this project

| Priority | Application | Evidence and evaluation | Decision |
|---|---|---|---|
| 1 | Source-linked risk/control review and RCSA preparation | J25/J27; evidence coverage, source identity, reproducibility and human-review boundaries | Implemented using existing records. No invented effectiveness or residual score. |
| 2 | KRI exception monitoring and data-quality visibility | J10/J16/J25/J27; past-only calculations, missing/stale/gapped states, review workload | Implemented explainable rolling median/MAD signals. This exact statistic is an engineering choice, not a quoted employer requirement. |
| 3 | Quantitative model challenge and evaluation | J19/J23 plus adjacent J07/J33; training-only fitting, pooling disclosure, temporal holdout, assumption checks | Implemented diagnostics around the existing model, without changing its baseline outputs. |
| 4 | Grounded management-report drafts | J16/J21/J25/J28; cited evidence and explicit draft status | Existing assistant reused with new tools; matching workpaper fingerprint required in workbench AI drafts. |
| 5 | Continuous control testing | J10/J27; actual test populations, test logic, exceptions and effectiveness evidence | Deferred: a review date is not a test result. Current implementation prepares review questions only. |
| 6 | NLP incident classification/document intelligence | J23/J31; labelled taxonomy or approved documents, extraction/classification and citation evaluation | Deferred: existing labels and templated synthetic narratives would make reported accuracy circular. |
| 7 | Predictive losses/emerging risk ML | Quantitative roles support modelling skills, but weak direct evidence for a specific operational-loss predictor | Deferred: no real calibration or labelled future outcome. Preserve illustrative scenario simulation. |
| 8 | More autonomous/multi-agent workflows | J11/J23/J30/J31; compare measurable benefit against current single-agent design | Deferred: no evidenced need to replace a working bounded agent. |

## 4. Regulatory and industry sources

These are context and design constraints, not evidence of compliance:

- **Basel operational risk:** [BIS operational-risk standard](https://www.bis.org/committees/bcbs/basel-framework/standard/ope) and [OPE25 chapter](https://www.bis.org/basel_framework/chapter/OPE/25.htm). The standardised approach uses the Business Indicator Component and Internal Loss Multiplier, subject to jurisdictional implementation/discretion. Loss-data standards matter. A compound Poisson/Lognormal P99 or Expected Shortfall is **not** Basel SMA capital. RiskSignal has no business-indicator data or capital calculation.
- **DORA:** [ECB, Operational resilience in the digital age, 17 January 2025](https://www.bankingsupervision.europa.eu/press/blog/2025/html/ssm.blog20250117~32b79d4efa.en.html). DORA applied from that date. It strengthens ICT-incident reporting, testing and ICT third-party oversight/registers. Existing dependency maps and review questions are relevant preparation, not a DORA incident-classification, reporting or certification engine.
- **UK model risk:** [PRA SS1/23](https://www.bankofengland.co.uk/prudential-regulation/publication/2023/may/model-risk-management-principles-for-banks-ss). Principles cover identification/classification, governance, development/use, independent validation and mitigants. Applicability has a defined institutional scope; it is not a universal rule for every European firm. Documentation and an internal holdout test do not constitute independent validation.
- **EU AI Act:** [European Commission live framework overview](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) and [Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj). Applicability depends on intended use, provider/deployer role and specific risk classifications; an internal banking assistant is not automatically Annex III high-risk solely because its user is a bank. Transparency, literacy, governance and oversight must be assessed appropriately. The Commission overview describes staged and amended timelines, including high-risk dates beyond the original 2026 timetable. No legal timetable or compliance determination is hardcoded here; check current enacted texts and legal advice before relying on deadlines.
- **AI governance frameworks:** [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework). A useful governance/evaluation vocabulary, explicitly named by some employers. Referencing NIST/ISO is not certification, and their presence in a job description does not make them legislation.

## 5. Conclusion

The strongest interview narrative is **an analyst workflow with transparent evidence and quantitative challenge, assisted by a bounded AI system**. It is not “AI predicts operational failures” or “the platform automates regulatory compliance.” Preserve the existing graph, model, tools and interface; add the missing review and evaluation steps. See the [audit, implementation and roadmap](platform_upgrade.md).
