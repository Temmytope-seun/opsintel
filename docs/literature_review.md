# Literature review: governed, LLM-assisted decision support for IT operations

*A critical review supporting the research proposal ([research_proposal.md](research_proposal.md)) and technical report ([technical_report.md](technical_report.md)). The references are established works; check volume and page details against the published versions before citing them in a formal submission.*

## 1. Scope and approach

The review asks what existing research says about the four things OpsIntel combines:

1. decision support for operational managers;
2. integrating and assuring the quality of data from heterogeneous enterprise systems;
3. large language models (LLMs) that answer from structured data and documents;
4. the controls that make such systems safe to deploy.

For each theme it summarises the main positions, assesses their limitations for a small multi-service IT company, and states the design implication taken into OpsIntel. Section 7 sets out the gap the project addresses.

## 2. Decision support systems

Decision support systems (DSS) research has long argued that management decisions are improved by combining data, models and an interactive interface rather than by data or models alone. Power (2002) classifies DSS as data-driven, model-driven, knowledge-driven, document-driven and communications-driven. Most real systems mix several types, and OpsIntel deliberately combines the data-driven (KPIs), model-driven (risk scoring), document-driven (runbooks and policies) and knowledge-driven (recommendations) types.

Arnott and Pervan's critical reviews of the DSS field (2014) found that much DSS research had weak relevance to practice and called for more design-science work: building and rigorously evaluating artefacts in real organisational settings. Hevner, March, Park and Ram (2004) set out the design-science guidelines this project follows: a relevant problem, a purposeful artefact, rigorous evaluation and communicated design knowledge.

**Critique.** Classic DSS work assumes structured queries written by analysts or fixed reports. It says little about natural-language access, where the system rather than the user decides which data and model to use. That shifts the main risk from "the user asked the wrong question" to "the system answered a different question convincingly".

**Implication for OpsIntel.** Treat the assistant as a DSS front end, not a replacement for the analytics. Every answer is built from explicit model and data calls (tools), and the user can inspect them through the evidence panel with its SQL.

## 3. Data integration and data quality

Data quality is multi-dimensional. Wang and Strong (1996) showed that data consumers judge quality on intrinsic (accuracy), contextual (relevance, timeliness, completeness), representational and accessibility dimensions, not just correctness. Batini, Cappiello, Francalanci and Maurino (2009) surveyed methods for assessing and improving data quality and stress *measuring* quality before and after improvement. Rahm and Do (2000) classified data-cleaning problems into single-source and multi-source, schema-level and instance-level problems. Duplicates, inconsistent representations and conflicting values across sources are typical of the multi-source instance level. Christen (2012) describes record linkage and entity matching, including the trade-off between matching precision and recall.

**Critique.** These works predate LLM-based analytics. Their implicit consumer is a human analyst who can notice odd values. When an LLM consumes the data, a quality defect becomes a fluent but wrong sentence, and the reader has fewer cues that something is off. Quality assurance therefore has to move upstream and become visible.

**Implications for OpsIntel.**

- Quality is profiled before and after processing, per source.
- Bad records are quarantined with a reason, not dropped.
- Entity matching uses explainable tiers (normalised name, alias, fuzzy match) that favour precision.
- Lineage records the source hash and every transform.
- The live ServiceNow integration confirmed the multi-source problems Rahm and Do describe: missing service attribution, missing company references, and fields that differ between releases.

## 4. Language models over enterprise data and documents

### 4.1 Retrieval-augmented generation

Lewis et al. (2020) introduced retrieval-augmented generation (RAG): a generator conditioned on passages retrieved from an external corpus, which improves factuality on knowledge-intensive tasks and lets the knowledge be updated without retraining. Liu et al. (2024) showed that models use long contexts unevenly ("lost in the middle"): relevant information placed mid-context is used less reliably than information at the start or end, which argues for retrieving *few, relevant* passages rather than large amounts of text. Gao, Yen, Yu and Chen (2023) studied LLMs generating text with citations and found that even strong models often produce citations that do not fully support the claims they are attached to.

### 4.2 Text-to-SQL and tool use

Text-to-SQL benchmarks such as Spider (Yu et al., 2018) and BIRD (Li et al., 2023) show steady progress in translating questions into SQL. BIRD in particular shows that realistic, messy databases with domain-specific values remain hard, and that executable SQL can still be semantically wrong. More generally, tool-using agents interleave reasoning with actions (ReAct; Yao et al., 2023), and models can learn when to call tools (Toolformer; Schick et al., 2023).

### 4.3 Hallucination

Ji et al. (2023) survey hallucination in natural-language generation: content that is fluent but unsupported by the source or the world. They note that it is hard to measure automatically, especially for numbers and multi-hop claims.

**Critique.** These lines of work are largely evaluated on public benchmarks with clean schemas and single-turn questions. For operational decision support, three issues are under-addressed:

- **Metric semantics.** "Breach rate" must mean one agreed thing. Free text-to-SQL can be syntactically correct but use a different definition from the one managers rely on.
- **Numeric faithfulness.** Citation studies focus on sentences, not individual figures, yet a single wrong figure can drive a wrong decision.
- **Mixed evidence.** Real questions need both structured analytics and procedures, which most benchmarks treat separately.

**Implications for OpsIntel.**

- Curated analytics tools with fixed metric definitions are the primary path; guarded free SQL is the fallback.
- Retrieval returns a few short passages, capped per document.
- A figure-level grounding check verifies every number in an answer against tool evidence. This directly targets the numeric-faithfulness gap. In evaluation it caught the model approximating figures in its own reasoning, a failure that citation checks alone would miss.

## 5. Security of LLM-integrated applications

Greshake et al. (2023) demonstrated *indirect* prompt injection: instructions planted in data that an LLM-integrated application retrieves (web pages, emails, documents) can hijack its behaviour, including exfiltrating data or triggering actions. The OWASP Top 10 for LLM Applications lists prompt injection, sensitive information disclosure and excessive agency among the main risks.

**Critique.** Much mitigation advice relies on prompt instructions ("ignore instructions in documents"). The literature itself shows that these are not reliable on their own. The more robust position is to limit what a compromised model could do (least privilege) and to enforce controls outside the model.

**Implications for OpsIntel.** Defence in depth with controls outside the model:

- **Database access:** the assistant reads through a read-only connection with an engine-level authorizer, and personal-data columns are denied by the database engine.
- **Untrusted text:** injected paragraphs are screened out of retrieved documents and ticket text, and kept out of the search index.
- **Actions:** the assistant has a propose tool but no approve tool, so it cannot carry out an action itself.
- **Testing:** a planted injection document and poisoned tickets are part of the benchmark.

## 6. Humans, automation and governance

Parasuraman and Riley (1997) distinguish appropriate use of automation from misuse (over-reliance), disuse (under-reliance) and abuse (automating without regard to the operator). Over-reliance is the relevant danger for decision support: confident outputs encourage acceptance without checking.

Governance frameworks translate such concerns into organisational controls:

- **NIST AI Risk Management Framework 1.0** (NIST, 2023) organises work into Govern, Map, Measure and Manage.
- **ISO/IEC 42001:2023** specifies an AI management system.
- **The UK ICO's guidance on AI and data protection** sets out expectations for lawful basis, data minimisation, transparency and human review.

**Critique.** These frameworks are process-level and technology-neutral. They say *what* to control, not how to build a system that is controllable, and SMEs struggle to operationalise them. There is little empirical work showing which concrete controls are necessary and sufficient for a small enterprise, and what they cost in usability.

**Implications for OpsIntel.**

- **Evidence panels** make the basis of each answer inspectable.
- **Abstention** replaces guessing.
- **Uncertainty ranges** accompany risk scores.
- **Human approval with segregation of duties** gates consequential actions.
- **A hash-chained audit trail** records questions, tool calls and decisions.
- **Mapping to frameworks:** each control is mapped to NIST AI RMF and UK GDPR concepts in the risk assessment ([governance_risk_assessment.md](governance_risk_assessment.md)), which makes the framework concrete for one system.

## 7. Supporting analytical methods

- **Anomaly detection:** Isolation Forest (Liu, Ting and Zhou, 2008) isolates anomalies with fewer random partitions than normal points. It is efficient and needs no labels, which suits operational signals where incidents are rarely labelled as anomalous.
- **Probabilistic risk scores:** scored with the Brier score (Brier, 1950) as well as ranking metrics, because a decision aid's probabilities should be calibrated, not merely well ranked.
- **Forecasting baselines:** Hyndman and Athanasopoulos (2021) recommend always comparing forecasts against simple benchmarks such as naive and seasonal-naive. OpsIntel's risk and forecast evaluations both report a naive baseline for this reason.

## 8. Synthesis: the gap

Across these literatures, the components exist separately: DSS design principles, data-quality methods, RAG and text-to-SQL, injection research and governance frameworks. What is missing is empirical evidence on **combining them in one governed system for an SME's operational decisions**, evaluated against non-LLM and ungrounded-LLM alternatives on the same tasks and on realistic, defect-laden data. Specifically:

1. **Comparisons.** Few studies compare hybrid (analytics + retrieval + LLM), analytics-only and LLM-only conditions on identical operational questions with independent ground truth.
2. **Numeric faithfulness.** It is rarely measured at the level of individual figures.
3. **Data quality as a variable.** The effect of upstream data quality on downstream AI answers is seldom quantified.
4. **Governance in practice.** Governance controls are seldom evaluated as part of the system, for example as security probes in the benchmark.

OpsIntel addresses these through its research questions (RQ1–RQ4). Its first results, in the [technical report](technical_report.md), are evidence for the method rather than general effect sizes, because the data and questions share an author. A pilot on real operational data is the necessary next step.

## References

- Arnott, D. and Pervan, G. (2014) 'A critical analysis of decision support systems research revisited: the rise of design science', *Journal of Information Technology*, 29(4), pp. 269–293.
- Batini, C., Cappiello, C., Francalanci, C. and Maurino, A. (2009) 'Methodologies for data quality assessment and improvement', *ACM Computing Surveys*, 41(3), article 16.
- Brier, G. W. (1950) 'Verification of forecasts expressed in terms of probability', *Monthly Weather Review*, 78(1), pp. 1–3.
- Christen, P. (2012) *Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection*. Berlin: Springer.
- Gao, T., Yen, H., Yu, J. and Chen, D. (2023) 'Enabling large language models to generate text with citations', *Proceedings of EMNLP 2023*.
- Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T. and Fritz, M. (2023) 'Not what you've signed up for: compromising real-world LLM-integrated applications with indirect prompt injection', *Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security (AISec '23)*.
- Hevner, A. R., March, S. T., Park, J. and Ram, S. (2004) 'Design science in information systems research', *MIS Quarterly*, 28(1), pp. 75–105.
- Hyndman, R. J. and Athanasopoulos, G. (2021) *Forecasting: Principles and Practice*. 3rd edn. Melbourne: OTexts.
- ICO (Information Commissioner's Office) *Guidance on AI and data protection*. Available at ico.org.uk.
- ISO/IEC 42001:2023 *Information technology — Artificial intelligence — Management system*. Geneva: ISO.
- Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., Ishii, E., Bang, Y., Madotto, A. and Fung, P. (2023) 'Survey of hallucination in natural language generation', *ACM Computing Surveys*, 55(12), article 248.
- Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S. and Kiela, D. (2020) 'Retrieval-augmented generation for knowledge-intensive NLP tasks', *Advances in Neural Information Processing Systems*, 33.
- Li, J. et al. (2023) 'Can LLM already serve as a database interface? A BIg bench for large-scale database grounded text-to-SQLs', *Advances in Neural Information Processing Systems* (Datasets and Benchmarks Track).
- Liu, F. T., Ting, K. M. and Zhou, Z.-H. (2008) 'Isolation forest', *Proceedings of the 8th IEEE International Conference on Data Mining (ICDM)*, pp. 413–422.
- Liu, N. F., Lin, K., Hewitt, J., Paranjape, A., Bevilacqua, M., Petroni, F. and Liang, P. (2024) 'Lost in the middle: how language models use long contexts', *Transactions of the Association for Computational Linguistics*, 12, pp. 157–173.
- NIST (2023) *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*, NIST AI 100-1. Gaithersburg, MD: National Institute of Standards and Technology.
- OWASP Foundation, *OWASP Top 10 for Large Language Model Applications*. Available at owasp.org.
- Parasuraman, R. and Riley, V. (1997) 'Humans and automation: use, misuse, disuse, abuse', *Human Factors*, 39(2), pp. 230–253.
- Power, D. J. (2002) *Decision Support Systems: Concepts and Resources for Managers*. Westport, CT: Quorum Books.
- Rahm, E. and Do, H. H. (2000) 'Data cleaning: problems and current approaches', *IEEE Data Engineering Bulletin*, 23(4), pp. 3–13.
- Schick, T., Dwivedi-Yu, J., Dessì, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., Cancedda, N. and Scialom, T. (2023) 'Toolformer: language models can teach themselves to use tools', *Advances in Neural Information Processing Systems*, 36.
- Wang, R. Y. and Strong, D. M. (1996) 'Beyond accuracy: what data quality means to data consumers', *Journal of Management Information Systems*, 12(4), pp. 5–33.
- Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K. and Cao, Y. (2023) 'ReAct: synergizing reasoning and acting in language models', *International Conference on Learning Representations (ICLR)*.
- Yu, T. et al. (2018) 'Spider: a large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-SQL task', *Proceedings of EMNLP 2018*.
