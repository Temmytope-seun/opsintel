# Data protection and AI risk assessment

_A DPIA-style screening plus an AI risk register for the proof of concept. A pilot on real data needs a full DPIA signed off by the partner's DPO._

## 1. Processing description

| Item | MVP (synthetic) | MVP (ServiceNow developer instance) | Pilot (proposed) |
|---|---|---|---|
| Purpose | Operational decision support: performance, risk, cost and procedure guidance | Same, plus proving a live integration | Same |
| Data subjects | None (synthetic) | ServiceNow's fictional demo users and companies | Customer contacts, staff named in tickets (assignees, account managers) |
| Personal data | Synthetic contact e-mails and phones (to prove controls work) | Fictional names on caller, assignee and company references; no contact details are extracted | Contact details, staff names, free text that may contain personal data |
| Special category data | None | None | Not expected; free text must be screened |
| Lawful basis (UK GDPR) | n/a | n/a (fictional data) | Legitimate interests (operational management), subject to an LIA |
| Recipients | Internal roles only | Internal roles only | Internal roles; LLM provider as processor (DPA required) |
| International transfers | n/a | Developer instance hosted by ServiceNow (region per instance) | Depends on the LLM provider's region; use UK/EU processing or IDTA/SCCs |
| Retention | n/a | Local extract in `data_servicenow/`, deletable at any time; instance reclaimed by ServiceNow when idle | Operational data per existing ITSM policy; audit log 6 years (proposed) |

## 2. Data minimisation by design

- The assistant cannot read contact e-mail, phone or account manager. This is enforced by the database engine, not the prompt (`sql_guard.py`).
- Customers are referenced by pseudonymous id. A PII-free view (`customers_safe`) is the only customer table the assistant can see.
- Output masking catches personal data that might still appear in free text.
- Only row-capped, minimal tool results are sent to the LLM (`LLM_ROW_CAP = 25`). The UI holds the full evidence locally.
- The rules engine works with no external processor at all. A deployment can choose not to enable the LLM.

## 3. AI risk register

Likelihood (L) and impact (I) are scored 1–3, before and after controls.

| # | Risk | L×I before | Controls | L×I after | Evidence |
|---|---|---|---|---|---|
| R1 | Hallucinated figures drive a wrong decision | 3×3 | All figures come from tools; grounding check flags untraceable numbers; evidence panel; abstention | 1×3 | `grounding.py`, eval grounding rate |
| R2 | Wrong but well-explained root cause | 2×3 | Root cause comes from recorded codes, not inference; similar-incident statistics; human approval of actions | 2×2 | eval N1, N8 |
| R3 | Indirect prompt injection via KB or tickets | 2×3 | Injection screen; untrusted-data wrapping; no approve or write tools; read-only SQL | 1×2 | eval S3, S4; tests |
| R4 | Personal data disclosure | 2×3 | Engine-level column deny; masking; role scoping; audit | 1×2 | eval S1; tests |
| R5 | Over-reliance / automation bias | 2×2 | Explicit uncertainty on risk scores; evidence first; approval by an accountable manager; training | 2×1 | UI; user guide |
| R6 | Model or data drift degrades risk scores | 2×2 | Out-of-sample evaluation on every run; baseline comparison; retrain schedule in pilot | 1×2 | eval §3 |
| R7 | Unauthorised action execution | 1×3 | Propose/approve with segregation of duties; actions are records, not automated changes | 1×1 | `actions.py`; tests |
| R8 | Audit trail tampering | 1×3 | Hash chain; verification endpoint; off-box export in pilot | 1×1 | tests |
| R9 | LLM service outage or refusal | 2×2 | Rules-engine fallback; refusal handled as explicit abstention; server-side fallback model | 1×1 | `assistant.py` |
| R10 | Biased prioritisation (e.g. smaller customers deprioritised) | 2×2 | Risk scores are per service, not per customer; review scoring weights with service owners | 1×2 | `kpis.improvement_priorities` method |
| R11 | Source-system credential leak (ServiceNow OAuth secret / password) | 2×3 | Secrets only in environment or git-ignored `.env`; never logged; excluded from images; rotate on exposure; secrets manager in pilot | 1×2 | `etl/servicenow.py`, `.gitignore` |
| R12 | Over-privileged integration account | 2×3 | Dedicated web-service-only user with read roles and `snc_read_only`; GET-only connector; OAuth app runs as that user | 1×2 | `docs/architecture.md` §4a |
| R13 | Broad OAuth token scope ("Broadly scoped") lets a stolen token call any REST API the user can read | 2×2 | Accepted on a developer instance; in a pilot, use a REST API access policy limited to the Table API endpoints the connector needs | 1×2 | Instance configuration |
| R14 | Demo-data seeding changes the source instance | 1×2 | Admin-run script, idempotent, every record tagged `opsintel_seed`, removal script is a dry run by default; never run against production | 1×1 | `tools/servicenow/` |

## 4. Alignment with frameworks

| Framework | How the design responds |
|---|---|
| UK GDPR / ICO guidance on AI and data protection | Minimisation, purpose limitation, DPIA, human review of significant decisions, transparency (evidence panel) |
| NIST AI RMF 1.0 (Govern, Map, Measure, Manage) | Govern: roles and approval workflow. Map: this register. Measure: evaluation harness. Manage: monitoring and abstention |
| ISO/IEC 42001 (AI management systems) | Basis for formalising policy, risk and lifecycle controls if the product is commercialised |
| EU AI Act (for EU customers of a SaaS version) | Decision support for internal operations is not expected to be high-risk, but transparency and logging are built in anyway |

## 5. Residual risks and open questions for the DPO

1. Free-text fields in real tickets may contain personal or sensitive data. A pre-ingestion redaction step should be evaluated on real samples.
2. The LLM provider's data retention and processing region must be confirmed contractually.
3. The pilot audit-log retention period needs agreement with the DPO.
4. Staff names (assignees) could enable performance monitoring of individuals. The pilot should aggregate to team level unless there is an agreed purpose.
5. The ServiceNow connector extracts reference fields (caller, assignee, company) as identifiers only and no contact details. For a production instance, confirm with the DPO which reference fields may be extracted at all, and whether caller identity should be pseudonymised at landing.
6. Field availability differs between ServiceNow releases (this instance has no `incident.problem_id`). Before granting extra roles to expose a field, confirm in the dictionary that the field exists; any role added must be reviewed against the minimisation principle above. (`sn_problem_read` was added directly to the integration user during testing; it was already inherited through `itil`, so the direct grant is redundant and can be removed.)
