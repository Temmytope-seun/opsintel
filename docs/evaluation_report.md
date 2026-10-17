# Evaluation report

_Generated 2026-10-17T10:22:46+00:00 by `python -m eval.run_eval`. Synthetic data, seed 42, snapshot 2026-09-30._

All results below are produced by the harness from this run. Targets were fixed in `eval/run_eval.py` before testing.

## 1. Assistant benchmark

28 questions per engine: 12 numeric/entity, 5 retrieval, 5 should-abstain, 6 security/governance.

| Metric | Target | rules |
|---|---|---|
| run at | |  |
| overall_pass_rate |  | 0.929 |
| deterministic_accuracy | ≥ 0.95 | 0.833 |
| citation_accuracy | ≥ 0.9 | 1.0 |
| abstention_recall | ≥ 0.9 | 1.0 |
| false_abstention_rate | ≤ 0.1 | 0.0 |
| security_pass_rate | ≥ 1.0 | 1.0 |
| grounding_rate | ≥ 0.98 | 1.0 |
| ungrounded_figures |  | 0 |
| latency_ms_median |  | 0 |
| latency_ms_p90 |  | 13 |
| input_tokens |  | 0 |
| output_tokens |  | 0 |
| usd_per_question |  | 0.0 |

> **Not run in this report:** claude, llm_only - no Anthropic credentials were available when the harness ran. Set `ANTHROPIC_API_KEY` and run `python -m eval.run_eval --engines rules claude llm_only` to produce the three-condition comparison described in docs/research_proposal.md.

### Failures - rules (2)

- **N2** What was the SLA breach rate for Network in Q2 2026 compared with Q3 2026? - failed: number_1=27.2
- **N8** What was the most common root cause of Network incidents last quarter and how many were there? - failed: number_0=176, contains:Firmware defect

## 2. Data integration quality (ETL reconciliation against truth tables)

| Table | Truth rows | Loaded | Missing | Spurious | Record accuracy | Lowest field accuracy |
|---|---|---|---|---|---|---|
| incidents | 7484 | 7484 | 0 | 0 | 1.0 | service_id 1.0 |
| service_requests | 4202 | 4202 | 0 | 0 | 1.0 | service_id 1.0 |
| alerts | 14370 | 14370 | 0 | 0 | 1.0 | service_id 1.0 |
| costs | 684 | 684 | 0 | 0 | 1.0 | amount_gbp 1.0 |

Raw-source quality before vs after the pipeline:

| Source | Metric | Before | After |
|---|---|---|---|
| alerts | duplicate_keys | 150 | 0 |
| alerts | exact_duplicate_rows | 150 | 0 |
| alerts | missing_required_cells | 0 | 0 |
| alerts | rows | 14520 | 14370 |
| alerts | schema_violations | 1501 | 0 |
| alerts | unmatched_references | 0 | 0 |
| costs | duplicate_keys | 12 | 0 |
| costs | exact_duplicate_rows | 12 | 0 |
| costs | missing_required_cells | 0 | 0 |
| costs | rows | 696 | 684 |
| costs | schema_violations | 834 | 0 |
| costs | unmatched_references | 0 | 0 |
| incidents | duplicate_keys | 156 | 0 |
| incidents | exact_duplicate_rows | 45 | 0 |
| incidents | missing_required_cells | 127 | 0 |
| incidents | rows | 7680 | 7484 |
| incidents | schema_violations | 1824 | 0 |
| incidents | unmatched_references | 1360 | 0 |
| service_requests | duplicate_keys | 42 | 0 |
| service_requests | exact_duplicate_rows | 19 | 0 |
| service_requests | missing_required_cells | 0 | 0 |
| service_requests | rows | 4244 | 4202 |
| service_requests | schema_violations | 1530 | 0 |
| service_requests | unmatched_references | 703 | 0 |

## 3. SLA risk model (out-of-sample)

| Measure | Model | Persistence baseline |
|---|---|---|
| ROC AUC | 0.668 | 0.567 |
| Brier score (lower is better) | 0.233 | 0.408 |

Train to 2026-04-02 (655 service-weeks); test 2026-04-02 to 2026-09-30 (356 service-weeks, positive rate 0.393). Precision of the 14 highest-scored test windows: 0.929.

## 4. Reading these results

- The rules engine is the *analytics-only* condition: it can only answer question shapes it was built for, so its failures show where templates break down - the gap the LLM condition is meant to close.
- Grounding counts every figure in an answer and checks it against tool evidence; it measures numeric hallucination, not whether the explanation is sensible. Human rating of usefulness is part of the pilot protocol.
- The data, the planted signals and the questions were written by the same author. That inflates absolute scores; comparisons between conditions on the same set are the meaningful output.
