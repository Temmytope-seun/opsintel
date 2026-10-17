# Design and evaluation of a governed, LLM-assisted operational intelligence platform for IT service businesses

*Technical report and draft paper. October 2026.*

## Abstract

Small and medium-sized IT service businesses run operations across separate ticketing, monitoring, finance and document systems, so answering *why* a metric moved can take days of manual analysis. Large language models (LLMs) promise natural-language access to this information but can produce fluent, unsupported answers. This report presents **OpsIntel**, a design-science artefact that places an LLM on top of a deterministic analytics layer it cannot bypass. Four elements make it governed:

- a data-integration layer with measured quality and lineage;
- a tool layer that turns every analytic result into numbered evidence;
- a figure-level grounding check on every answer;
- cross-cutting controls: role-based access, engine-enforced personal-data protection, prompt-injection screening, human approval of actions and a hash-chained audit log.

We evaluated three conditions on the same 28-question benchmark, with ground truth computed independently: analytics-only (deterministic rules engine), hybrid (Claude Opus 5.5 with tools) and LLM-only (the same model without data).

- **Hybrid** answered every numeric and factual question correctly in each of three runs (overall pass 28, 27 and 28 out of 28). It cited the correct, actually retrieved documents and passed all security probes. 98.8% of its stated figures traced to evidence.
- **Analytics-only** was fully grounded but brittle (deterministic accuracy 0.833).
- **LLM-only** answered no factual question correctly and stated untraceable figures.

The integration layer reconciled perfectly with the synthetic ground truth, and the platform was then connected to a live ServiceNow instance (1,474 incidents, zero rejects). The results support the design principle that the value comes from the governed data and tool layer, with the LLM adding flexibility. Because the data and questions share an author, the results are evidence for the method rather than general effect sizes.

## 1. Introduction

Operational managers in multi-service IT companies need fast, trustworthy answers to questions such as "why did costs rise this month?", "which category is breaching SLA and why?" or "which services are at risk next week?". The data to answer them is spread across systems, inconsistent, and rarely joined.

LLMs can plan analyses and explain results in plain language. Deployed naively, however, they invent numbers, can be manipulated by text in the data they read, and can expose personal data or take actions without accountability.

This project asks how such a system should be **designed** so that its answers are correct, traceable and safe enough for an SME to rely on, and how much each component contributes. It follows the design-science approach of Hevner et al. (2004): build a purposeful artefact for a relevant problem and evaluate it rigorously against alternatives.

**Contributions.**

1. A layered reference design for governed LLM decision support, with controls enforced outside the model.
2. A figure-level grounding check that detects numbers not supported by tool evidence.
3. A reproducible evaluation harness with targets fixed before testing, independent ground truth, and security probes as first-class test items.
4. A three-condition comparison (analytics-only, hybrid, LLM-only) on identical items.
5. A live ServiceNow integration showing that the same pipeline handles real-platform data, with the lessons learned.

## 2. Background

The full review is in [literature_review.md](literature_review.md). In brief:

- **Decision support:** research favours combining data, models and documents in one interface (Power, 2002) and evaluating artefacts in context (Arnott and Pervan, 2014).
- **Data quality:** quality is multi-dimensional and should be measured before and after improvement (Wang and Strong, 1996; Batini et al., 2009). Multi-source integration brings characteristic duplicate and representation problems (Rahm and Do, 2000).
- **LLMs over data:** retrieval-augmented generation improves factuality (Lewis et al., 2020) but citations often fail to support claims (Gao et al., 2023), and realistic text-to-SQL remains hard (Li et al., 2023).
- **Security:** indirect prompt injection lets text in retrieved data hijack LLM applications (Greshake et al., 2023).
- **Governance:** frameworks such as the NIST AI RMF (2023) say *what* to control but not *how* to build a controllable system for an SME.

The gap is empirical evidence on combining these in one governed system, evaluated against non-LLM and ungrounded-LLM alternatives on realistic data.

## 3. Design

Detail is in [architecture.md](architecture.md), [analytics.md](analytics.md) and the editable diagrams ([diagrams/](diagrams/)).

**Layers.**

1. **Enterprise sources:** CMDB, ITSM, finance, monitoring and knowledge base.
2. **Integration and quality:** connectors, profiling before and after, entity matching, quarantine, lineage.
3. **Unified foundation:** typed schema, metadata catalogue, metric definitions, document index.
4. **Analytics** (KPIs, Isolation Forest anomalies, explainable risk model) **and AI** (Claude engine, rules engine, tool layer, retrieval, guarded SQL, grounding check).
5. **Interface:** dashboard, REST API, CLI.

Governance applies across layers 2–5.

**Key design decisions.**

| Decision | Rationale |
|---|---|
| The LLM sits above analytics and never touches the database directly | Figures come from tested code with one definition per metric; the LLM plans and explains |
| Every tool result becomes numbered evidence with its SQL and sources | Every claim can be inspected; citations can be checked against what was actually retrieved |
| Figure-level grounding check after each answer | Targets numeric faithfulness, which citation checks miss |
| Controls enforced in code and the database engine: a read-only connection, an engine authorizer that denies personal-data columns, injection screening, and an assistant with a propose tool but no approve tool | Prompt instructions alone are not reliable defences |
| Two engines: Claude and a deterministic rules engine | Resilience when no LLM is available, and a clean analytics-only research condition |
| Land external sources into one raw format | One validated pipeline for synthetic and live data |

## 4. Implementation

Python 3.11, SQLite (with a documented PostgreSQL mapping), pandas, scikit-learn, FastAPI, Streamlit and the Anthropic SDK (`claude-opus-5-5`, adaptive thinking, medium effort, server-side refusal fallback), packaged with Docker.

The synthetic data generator creates 18 months of operations for a fictional five-unit IT services company, with **planted signals** for evaluation:

- a Q3 2026 switch-firmware defect driving Network SLA breaches;
- a September 2026 cost rise from licence true-ups and incident-related overtime;
- capacity pressure on cloud hosts;
- delivery blockers on leased-line installations.

It also injects **recoverable data defects** (duplicates, stale versions, mixed date formats, misspelt service names, missing priorities) and **junk rows** that should be rejected.

The **ServiceNow connector** reads a live instance through the Table API with OAuth 2.0 client credentials, as a dedicated read-only user, and lands the data into the same raw format. The test suite has 62 automated tests, including 12 SQL attack cases and a fake ServiceNow API.

## 5. Evaluation method

**Benchmark.** 28 questions in five groups:

- 12 numeric or entity questions;
- 5 retrieval questions requiring a citation;
- 5 questions the system should decline (data not held or out of range);
- 6 security and governance probes: personal-data extraction, role restriction, a direct injection, an indirect injection through a document, restricted-document leakage, and a destructive SQL request.

**Ground truth** is computed independently with pandas from the generator's clean truth tables, not with the platform's SQL.

**Conditions.**

| Condition | What it is |
|---|---|
| C1 analytics-only | Rules engine |
| C2 hybrid | Claude with the 16 tools |
| C3 LLM-only | The same model with no tools or data |

**Scoring.**

- numbers within tolerance;
- required entities present;
- a cited document must be both named in the answer and actually retrieved;
- abstention behaviour;
- forbidden strings absent;
- database post-conditions (no approvals created, no rows deleted);
- the share of stated figures traceable to evidence.

**Targets** were fixed in code before any run: deterministic accuracy ≥ 0.95, citation accuracy ≥ 0.90, abstention recall ≥ 0.90, false abstention ≤ 0.10, security probes 1.0, grounding ≥ 0.98.

**Data integration** is evaluated by reconciling loaded tables against the truth tables. The **risk model** is evaluated out of sample on the most recent 26 weeks against a persistence baseline, using ROC AUC and the Brier score.

## 6. Results

### 6.1 Assistant benchmark (latest run, 17 October 2026)

| Measure | Target | C1 analytics-only | C2 hybrid | C3 LLM-only |
|---|---|---|---|---|
| Overall pass rate | | 0.929 | **1.0** | 0.357 |
| Deterministic accuracy | ≥ 0.95 | 0.833 | **1.0** | 0.0 |
| Citation accuracy | ≥ 0.90 | 1.0 | **1.0** | 0.0 |
| Abstention recall | ≥ 0.90 | 1.0 | **1.0** | 1.0 |
| False abstention rate | ≤ 0.10 | 0.0 | **0.0** | 0.824 |
| Security probes | 1.0 | 1.0 | **1.0** | 0.833 |
| Grounding rate | ≥ 0.98 | 1.0 | **0.988** | 0.0 |
| Median latency | | < 1 s | 10.9 s | 7.7 s |
| Cost per question (list price) | | 0 | ≈ $0.071 | ≈ $0.015 |

**Run-to-run variation.** Across three C2 runs the pass counts were 28, 27 and 28 out of 28. The single miss asked which engineer closed the most tickets: C2 explained that no per-engineer data exists and offered team-level figures. That is a defensible partial answer, but it failed the strict refusal check. The rubric was not changed after seeing results.

**Where C1 failed.** It failed a comparative question phrased as "Q2 compared with Q3" and a root-cause count question for which it has no template. These are exactly the template limits C2 removes.

**Where C3 failed.** It declined 82% of answerable questions and stated 12 figures with no basis. It failed one security probe by not returning the legitimate content of a document it could not see.

### 6.2 Grounding analysis

C2 stated 4 figures that the checker could not trace in the latest run (an earlier run had 7):

- **2 were genuine:** the model calculated a percentage change ("about 63%") and a sum ("£14,338") itself. Both were arithmetically correct but not present in the evidence. This is the behaviour the system prompt forbids and the check is designed to catch.
- **2 were checker false positives:** the SLA compliance threshold "90%" (a policy constant) and an "18-month" date range.

An earlier checker defect (percentages of ratios above 1, such as 2.32 shown as 232%) was found the same way and fixed. Figure-level grounding thus exposed a failure mode, correct but unsourced arithmetic, that citation-level evaluation would not detect.

### 6.3 Data integration

Rows in each raw source versus rows loaded:

| Source | Raw rows → loaded | Defects handled |
|---|---|---|
| Incidents | 7,680 → 7,484 | 112 duplicate copies, 44 stale versions, 40 junk rows quarantined (test tickets, impossible timestamps, orphan customers), 121 priorities imputed from impact × urgency, 192 fuzzy service-name matches |
| Service requests | 4,244 → 4,202 | Duplicates; service names matched |
| Monitoring alerts | 14,520 → 14,370 | 150 duplicate deliveries removed |
| Finance ledger | 696 → 684 | Duplicates removed; currency and month formats normalised |

Reconciliation against the truth tables was **1.0 record accuracy on all four sources**, with zero missing, zero spurious rows and zero foreign-key violations. This is partly by construction: the injected defects were designed to be recoverable.

### 6.4 Risk model

| Data set | Model AUC | Baseline AUC | Model Brier | Baseline Brier |
|---|---|---|---|---|
| Synthetic (test: Apr–Sep 2026) | 0.668 | 0.567 | 0.233 | 0.408 |
| ServiceNow (seeded history) | 0.647 | 0.637 | 0.220 | 0.191 |

On synthetic data the model clearly beats a "same as last week" baseline in both ranking and calibration. On the ServiceNow data, which has no monitoring signals and less history, it is barely better at ranking and worse calibrated. The platform presents it as a prioritisation aid with uncertainty ranges, not as a forecast.

### 6.5 Live ServiceNow integration

The connector was run against a ServiceNow Personal Developer Instance (Australia release), seeded with a year of realistic incident history containing planted signals.

**Result.** 1,474 incidents were synced with zero rejects and zero foreign-key violations. The analytics recovered the planted signals:

- Network breach rate rose from 11.1% to 34.4% between Q2 and Q3 2026, driven by VPN (breaches 1 → 29);
- email incidents rose from 14 to 95 between August and September.

Asked "why", the hybrid assistant identified both stories with every figure traced to evidence.

**Lessons from the real platform:**

1. **Basic authentication is blocked** on REST APIs by default, so OAuth client credentials were required.
2. **The client-credentials grant** needed a system property to be enabled.
3. **Token scope** had to allow the unscoped Table API.
4. **Field names differ between releases:** this release has no incident-to-problem field, so root cause falls back to subcategory.
5. **Real data is incomplete:** 181 incidents had no business service and 242 no company, which the pipeline recorded instead of filling in.

## 7. Discussion

**RQ1 (accuracy).** Hybrid outperformed both alternatives on factual accuracy with no loss in grounding, citation or security. The LLM-only condition shows that the model's general knowledge cannot substitute for the data. The analytics-only condition shows that deterministic analytics are precise but brittle to phrasing. The value lies in the combination.

**RQ2 (data quality).** The validation layer reconciled perfectly on recoverable defects and made real-source gaps visible on ServiceNow. The planned ablation (answering over unvalidated raw data) has not yet been run, so the size of the quality effect on answers is not yet measured.

**RQ3 (efficiency).** Median answer time was 10.9 s, against the days typically needed for a manual cross-system investigation. Without a user study, however, no claim is made about decision time or decision quality.

**RQ4 (governance).** All six security probes passed in C1 and C2 because the controls do not depend on the model complying. The cost is modest: one extra read-only role, an evidence panel, and about 11 s latency. The main governance weakness found was accepting a broadly scoped OAuth token for convenience on the developer instance; a pilot should restrict it with an API access policy.

## 8. Limitations and threats to validity

- **Shared author.** The data, the planted signals and the benchmark questions were written by the same author. This inflates absolute scores. Mitigations: independent ground-truth code, and comparing conditions on identical items.
- **Few runs, one model.** Three C2 runs and one C3 run is too few for confidence intervals. The protocol calls for at least three runs per condition.
- **ServiceNow data is not operational evidence.** It is demo data plus seeded history. It proves the integration, not real performance.
- **Grounding checker limits.** It is a heuristic with known false positives (thresholds, date ranges). It checks that figures are traceable, not that explanations are sound.
- **No user study.** Usefulness and trust have not been measured with real users.

## 9. Conclusion and future work

A governed design, in which the LLM plans and explains while deterministic tools compute and governance is enforced outside the model, produced correct, traceable answers. Neither analytics alone nor an ungrounded LLM did. Future work:

1. A pilot on real partner data with staff-written questions and a within-subjects user study (manual vs dashboard vs assistant).
2. At least three runs per condition with confidence intervals, and the data-quality ablation.
3. Prompt and tool changes to eliminate unsourced arithmetic, measured on the same benchmark.
4. Incremental scheduled sync, PostgreSQL with row-level security, and an API access policy restricting the integration token.
5. Evaluate the volume and cost forecasts (added after this report; see [analytics.md](analytics.md) §3a) over a longer history, where seasonal methods become possible.

## References

See [literature_review.md](literature_review.md) for full references. Cited here: Arnott and Pervan (2014); Batini et al. (2009); Gao et al. (2023); Greshake et al. (2023); Hevner et al. (2004); Lewis et al. (2020); Li et al. (2023); NIST (2023); Power (2002); Rahm and Do (2000); Wang and Strong (1996).
