# Research proposal

**Provisional title:** *Design and Evaluation of a Governed, LLM-Assisted Operational Intelligence Platform for IT Service Businesses*

## 1. Motivation

Decision support systems (DSS) research has a long history of systems that combine data, models and a user interface. Large language models add a new capability: answering open, natural-language questions across structured data and documents. They also add a new risk: fluent answers that are wrong. Small and medium-sized multi-service enterprises feel both effects strongly. They have fragmented systems and few analysts, so the promise is large, but they cannot absorb confident errors or a data-protection breach. There is still little empirical work on **governed** LLM decision support evaluated against non-LLM alternatives on the *same* operational tasks.

## 2. Research questions

- **RQ1 (accuracy):** Does combining structured analytics with retrieval and an LLM (hybrid) improve the accuracy and completeness of answers to operational questions, compared with (a) analytics-only and (b) an LLM-only baseline?
- **RQ2 (data quality):** How sensitive are AI-generated insights to source data-quality defects, and how much of that sensitivity does an explicit integration and validation layer remove?
- **RQ3 (efficiency):** Do source-grounded recommendations reduce the time needed to investigate recurring incidents, without lowering decision quality?
- **RQ4 (governance):** Which controls are necessary and sufficient to deploy LLM decision support safely in a small multi-service enterprise, and what do they cost in usability and latency?

## 3. Literature review plan

These themes structure the review. The references are starting points that must be verified and extended during the review.

| Theme | Starting points |
|---|---|
| DSS foundations and taxonomies | Power's work on DSS concepts; Arnott & Pervan's critical reviews of DSS research |
| Data quality dimensions | Wang & Strong (1996), *Beyond accuracy: what data quality means to data consumers* |
| Retrieval-augmented generation | Lewis et al. (2020), RAG for knowledge-intensive NLP; long-context limits (Liu et al., *Lost in the Middle*) |
| Text-to-SQL and tool-using LLMs | Text-to-SQL benchmarks (e.g. Spider, BIRD); tool-use / function-calling agents |
| Hallucination and grounding | Surveys of hallucination in LLMs; attribution and citation evaluation |
| LLM security | Greshake et al. (2023) on indirect prompt injection; OWASP Top 10 for LLM applications |
| AI governance | NIST AI RMF 1.0; ISO/IEC 42001; ICO guidance on AI and data protection |
| IT service management | ITIL 4 practices for incident, problem and change management; SLA measurement |

**Expected gap:** most evaluations of LLM analytics use public benchmarks with clean schemas. Few compare hybrid, analytics-only and LLM-only conditions on realistic, defect-laden enterprise data with governance controls in place.

## 4. Method

### 4.1 Artefact
OpsIntel (this repository) is a design-science artefact. It has a layered architecture (integration → foundation → analytics → AI → interface) and cross-cutting governance.

### 4.2 Conditions

| Condition | Implementation | Purpose |
|---|---|---|
| C0 Manual baseline | Analyst using source exports and spreadsheets | Current practice (user study only) |
| C1 Analytics-only | `engine=rules`: deterministic KPIs, risk, retrieval and templates | Value of integration and analytics without an LLM |
| C2 Hybrid AI | `engine=claude`: LLM + tool calling over C1's tools + guarded SQL | Value added by the LLM |
| C3 LLM-only | `engine=llm_only`: same model, no tools or data | Ungrounded-chatbot baseline |

### 4.3 Measures

| Construct | Metric | Instrument |
|---|---|---|
| Correctness | Deterministic accuracy (numbers within tolerance, entities exact) | `eval/run_eval.py` against independent ground truth |
| Grounding | Share of stated figures traceable to evidence; count of ungrounded figures | `ai/grounding.py` |
| Citation | Correct document cited **and** actually retrieved | Harness |
| Calibration of refusal | Abstention recall; false abstention rate | Harness |
| Safety | Pass rate on PII, role, injection and destructive-SQL probes | Harness |
| Data quality effect | Accuracy with the validation layer vs. answering over the raw sources (RQ2 ablation) | Planned: run the KPI layer on naively loaded raw data |
| Real-source defects | Mapping gaps and quarantine rates on live ITSM data (e.g. incidents without business service or company) | ServiceNow connector `source_manifest.json` |
| Efficiency | Task time, number of steps | User study |
| Decision quality | Expert-rated correctness and usefulness (1–5, blinded) | User study |
| Usability / trust | SUS; trust-in-automation scale | User study |
| Cost | Tokens and £ per answered question | Harness (`usage`) |

### 4.4 Pre-set targets
Targets are fixed in code (`TARGETS` in `eval/run_eval.py`) before any runs. The report states the actual result next to each target, whether or not it was met. For example, ≥95% deterministic accuracy is an **experimental target, not a claim**.

### 4.5 User study (pilot phase)
Within-subjects design. About 8–12 operations staff each complete 6 investigation tasks (2 per condition C0/C1/C2), with task order counterbalanced. Each session records time, answer, confidence and SUS. Two blinded senior staff rate decision quality. Ethics approval goes through the university panel, with informed consent and no personal performance reporting.

### 4.6 Threats to validity
- **Construct:** the synthetic data and questions share an author, which inflates absolute scores. Mitigations: independent ground-truth code, compare conditions on the same items, then re-run on a real pilot extract with questions written by staff.
- **Ecological:** the live ServiceNow connection uses a developer instance whose incidents are ServiceNow demo records plus history seeded by this project (`tools/servicenow/seed_incidents.js`). It shows the integration and pipeline work end to end on a real platform; it is *not* evidence about real operational performance.
- **Internal:** LLM non-determinism. Repeat C2 and C3 runs (n ≥ 3) and report variance.
- **External:** a single company and sector. Frame the findings as transferable design principles rather than general effect sizes.

## 5. Current results

See [`evaluation_report.md`](evaluation_report.md), which is generated by the harness. Headline from the first full three-condition run (one run per condition, Claude Opus 5.5):

| | C1 analytics-only | C2 hybrid | C3 LLM-only |
|---|---|---|---|
| Deterministic accuracy | 0.833 | 1.0 | 0.0 |
| Citation accuracy | 1.0 | 1.0 | 0.0 |
| False abstention | 0.0 | 0.0 | 0.824 |
| Security probes | 1.0 | 1.0 | 0.833 |
| Grounding | 1.0 | 0.979 | 0.0 |

Early reading for RQ1: the hybrid condition removes the template brittleness of C1 (it passes the comparative and count questions C1 fails) without introducing the ungrounded answers of C3. The residual risk is the model doing arithmetic in its own reasoning, which the grounding check detects (5 genuine flags). Next steps: n ≥ 3 runs per condition, a prompt variant that forbids derived figures, and the RQ2 ablation on raw (unvalidated) data.

> The report file currently on disk was regenerated by a rules-only run and does not include the C2/C3 rows above; re-running `python -m eval.run_eval` with an API key restores them (the harness now preserves results for engines that are not re-run).

**Integration result (RQ2 groundwork).** The live ServiceNow sync loaded 1,474 incidents with 0 rejects and 0 foreign-key violations, and surfaced real-source gaps: 181 incidents without a business service, 242 without a company, and an incident field (`problem_id`) hidden from the integration account by access controls. The planted signals in the seeded history were recovered by the analytics (Network breach rate 11.1% → 34.4% from Q2 to Q3 2026, driven by VPN).

## 6. Planned outputs

1. Conference paper (e.g. a UK Academy for Information Systems or ECIS track on AI in organisations): artefact and the C1/C2/C3 comparison.
2. Journal paper after the pilot: user study (RQ3) and governance analysis (RQ4).
3. Open benchmark: the synthetic generator, question set and harness, so other researchers can reproduce and extend the comparison.
