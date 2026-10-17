# Proposed proof of concept for Unity World Ltd

*How OpsIntel maps onto Unity World's public service portfolio, framed as a proposal to validate in discovery. Everything here is based on public information (sources at the end, accessed 17 October 2026). Nothing in this repository uses Unity data, and statements about Unity's internal systems, volumes or priorities are **hypotheses** until confirmed with the company.*

## 1. What is publicly known

| Fact | Source |
|---|---|
| Founded in 1998 by founder and CEO Simon Scotchbrook; regrouped under the "Unity" brand in 2020 | unity.world/about |
| Headquartered in Middlesbrough (Brunel House), serving the North East and the UK | unity.world; KTP advert |
| 18 staff | KTP advert (jobs.ac.uk, ref T03163) |
| Specialist business units: Tech Group, Communications, Cloud Services, Workplace IT, AI Software, Tech Force, Tech Shop | unity.world/about |
| Product groups: Managed IT, Communications, Cloud & Data Centre, Software, IT Infrastructure, IT Equipment | unity.world |
| In-house, purpose-built, ISO 27001-certified data centre | unity.world |
| Sectors served: professional services, shipping and logistics, manufacturing and engineering, retail, education, hospitality and leisure, charity, public sector | unity.world |
| AI Software builds bespoke software, CRM, a Customer Portal, a **Support Ticket** system, time and attendance, fleet management and the **MYBE** SaaS portal, with integration via REST or SOAP APIs, webhooks and email | ai-software.unity.world |
| Tech Force provides outsourced support services, technical field services and technical logistics | tech-force.unity.world |
| KTP aim: "design, create and embed bespoke AI-enabled intelligence platform", integrating systems, data sources, workflows and reporting into an AI-assisted enterprise decision support system | KTP advert |

## 2. Mapping Unity's business units onto OpsIntel

| Unity business unit | Likely operational data (hypothesis) | OpsIntel capability already built | Decision it would support |
|---|---|---|---|
| **Workplace IT** (managed IT, proactive support, cybersecurity) | Helpdesk tickets, SLAs per customer contract, endpoint/RMM alerts | Incident KPIs, SLA breach analysis with root causes, next-week SLA risk, runbook retrieval | Which customers and services are drifting off SLA, and why; where to focus engineers next week |
| **Communications** (leased lines, broadband, VoIP, mobile) | Carrier fault tickets, provisioning orders with due dates, line/VoIP quality alerts | Delivery-delay risk for open orders (e.g. carrier wayleave blockers), network root-cause analysis | Which installations will miss their committed date; which faults recur by carrier or equipment |
| **Cloud Services / data centre** (hosting, backup, DR, ISO 27001 DC) | Capacity and backup alerts, power and cooling events, change records | Isolation Forest anomaly detection, capacity-risk signals, change-related incident analysis | Emerging capacity or backup problems before they become customer incidents |
| **AI Software** (bespoke software, CRM, Support Ticket, MYBE SaaS) | The systems themselves: ticket, CRM and customer data behind REST/SOAP APIs | The connector pattern (land, validate, lineage) proven against the ServiceNow Table API | Integration route for Unity's own platforms, and a commercial channel (§4) |
| **Tech Force** (outsourced support, field services, logistics) | Field visits, equipment lifecycle, stock movements | Request fulfilment and delivery performance; improvement priorities | Which field processes cause the most hours beyond target |
| **Tech Shop / IT Equipment** (95,000+ products) | Orders, supplier lead times | Not in scope for the first proof of concept | Later: hardware lead-time risk on projects |
| **Group finance** | Cost per unit or contract | Cost-change drivers and cost anomalies | Margin pressure by service, explained with ledger detail |

**Observation.** The synthetic data in this repository was designed around a five-unit multi-service IT group (managed IT support, telecoms and connectivity, cloud hosting, data-centre operations, software development). That structure closely matches Unity's public portfolio, so the demonstrated use cases transfer directly. The specific numbers and stories do not.

## 3. Key hypothesis: Unity's own platforms are the primary source

Unity's AI Software unit already sells a **Support Ticket** system, **CRM** and the **MYBE** SaaS portal, all of which integrate over REST or SOAP. It is therefore likely, but **unconfirmed**, that Unity's own operational tickets live in its in-house platforms rather than in ServiceNow. If so:

- **Integration** becomes an adapter from the Support Ticket / MYBE API into OpsIntel's raw landing format. It would follow exactly the pattern of `opsintel/etl/servicenow.py`: GET-only access, a dedicated read-only identity, data landed in the same raw format and run through the same validation, and mapping gaps recorded rather than invented. The ServiceNow work de-risks this: it showed how to handle authentication policies, field differences between versions and missing attribution.
- **Data quality** is under Unity's control. Gaps found by the pipeline (for example tickets without a service or customer) can be fixed at source in a product Unity owns. That is a faster feedback loop than with third-party ITSM tools.
- **The KTP's "integrating systems, data sources, workflows and reporting"** maps to connecting Support Ticket, CRM, monitoring and finance data, which is OpsIntel's layer 1–3 design.

## 4. Commercialisation route

If the platform proves itself internally, MYBE is a ready distribution channel: an existing SaaS portal sold to Unity's SME customers. OpsIntel's multi-tenant design ([roadmap_saas.md](roadmap_saas.md)) would become an **"operational intelligence" module for MYBE customers**:

- **Insight tier:** dashboards on a customer's own support tickets and SLAs (rules engine, no LLM cost).
- **Decision tier:** the AI assistant, risk scoring and approval workflow.
- **Differentiators:** governance (evidence, audit, data minimisation) and an ISO 27001-certified UK data centre for hosting, a strong position for regulated and public-sector customers in Unity's sector list.

## 5. Proposed proof-of-concept scope (12 weeks)

| Phase | Weeks | Work | Exit criterion |
|---|---|---|---|
| Discovery | 1–2 | Confirm systems, data owners and decision pain points with each business unit; DPIA; choose **two** business units (suggested: Workplace IT and Communications) | Signed-off scope, data access agreed |
| Integrate | 3–5 | Read-only adapter for the Support Ticket / MYBE API (and finance export); re-baseline data quality | Reconciliation report accepted by data owners |
| Evaluate | 6–7 | Re-write the 28-question benchmark with Unity staff's real questions; run the analytics-only and hybrid conditions | Targets met or gaps understood |
| Pilot | 8–11 | Live use by a small group of managers and engineers; feedback; usability study tasks | System Usability Scale ≥ 68; no security incidents; at least one approved action traced to an insight |
| Decide | 12 | Value review; go/no-go for wider rollout and the MYBE module | Board decision |

**Success measures to agree up front:**
- Time from "a metric moved" to an evidence-backed explanation (manual baseline vs OpsIntel).
- Share of answers with all figures traced to evidence.
- SLA breaches avoided in the pilot units.
- Hours of manual reporting saved per month.

## 6. Questions to confirm in discovery

1. Where do operational tickets, contracts/SLAs, monitoring alerts and costs live today, and who owns each system? Is the Support Ticket / MYBE platform used internally?
2. Which decisions are hardest today, for example where to deploy engineers, which contracts are at risk, or which provisioning orders will slip?
3. How are SLAs defined: per customer contract, per service, elapsed or business hours?
4. Are service, customer and root cause recorded consistently on tickets?
5. What are the constraints on hosting AI workloads and using a third-party LLM provider (data residency, customer contracts)?
6. With 18 staff, who would own the platform after the KTP? This argues for a lightweight, low-maintenance deployment.

## 7. What not to claim

- No Unity data has been used; all figures in this repository are synthetic or from a ServiceNow developer instance.
- Unity's internal tooling, volumes, pain points and priorities are hypotheses from public material.
- The 18-staff figure comes from the KTP advert and may have changed.

## Sources

- Unity World Ltd, home page: [unity.world](https://unity.world)
- Unity World Ltd, About: [unity.world/about](https://unity.world/about/)
- Unity AI Software: [ai-software.unity.world](https://ai-software.unity.world)
- Unity Tech Force: [tech-force.unity.world](https://tech-force.unity.world)
- Teesside University, KTP Associate - AI-Enabled Business Intelligence and Automation Engineer (ref T03163): [jobs.ac.uk/job/DTD868](https://www.jobs.ac.uk/job/DTD868/)
