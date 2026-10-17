# Interview demo script (about 8 minutes)

**Setup:** `make setup && make ui` (and `make api` in a second terminal). Optionally export `ANTHROPIC_API_KEY` to show the Claude engine; the demo also works on the rules engine.

| # | Time | Do | Say |
|---|---|---|---|
| 1 | 0:00 | Overview, signed in as *Priya (Head of Service Ops)* | "Four source systems, unified. Network breach rate went from about 9% to 27% quarter on quarter, and costs are up £58.6k this month. Those are the two stories." |
| 2 | 1:00 | Ask: *Which service category had the highest SLA breach rate last quarter, and what explains the increase?* | "Each figure has an evidence tag. Here is the SQL behind E1. The 'why' comes from root-cause codes: a firmware defect on one vendor's switch stacks. The model didn't invent it." |
| 3 | 2:00 | Ask: *Why did our operational costs increase this month?* | "Drivers with the finance ledger narrative. And the link between the two stories: overtime and vendor call-outs come from the same firmware problem." |
| 4 | 3:00 | Ask: *What should the support team do when a recurring network incident occurs?* (as Priya, then as *Alex, service desk*) | "Data finds the recurring fault, retrieval finds the runbook, and the steps are cited. As Alex, the restricted problem record is withheld. That's access control on documents." |
| 5 | 4:00 | Risk & anomalies | "Next week's risk with an uncertainty band and drivers. Out of sample, the model's AUC is 0.67 against 0.57 for a naive baseline. That's modest, so I present it as a prioritisation aid." |
| 6 | 5:00 | Back in Ask, as *Sam (analyst)*: propose an action from the breach answer. Switch to *Priya* and approve it. Try approving as Sam first. | "AI and analysts propose; an accountable manager approves. Segregation of duties is enforced, and the owner group is notified." |
| 7 | 6:00 | Ask as Sam: *List the contact email addresses for all our customers.* Then *Is there any supplier maintenance planned on the SBC platform?* | "Personal data is blocked by the database engine, not by asking the model nicely. The vendor bulletin contains a prompt injection. It's stripped before the model sees it, and the legitimate notice survives." |
| 8 | 7:00 | Data quality, then Audit log as *Jordan (audit)* | "Before/after quality, quarantined records with reasons, lineage with source hashes. Every question, tool call and approval is hash-chained." |
| 9 | 7:30 | Open `docs/evaluation_report.md` | "Targets were set before testing. Same 28 questions, three conditions. Claude with tools got every factual question right; the same model without data got none, and stated numbers it couldn't have known. The grounding check also caught Claude doing arithmetic in its head, which is my next fix." |

**Likely questions**
- *Why not just give the LLM SQL access?* It can use guarded SQL, but curated tools give tested, defined metrics, and the database engine enforces permissions either way.
- *How would this connect to our ServiceNow?* Through the Table API, incrementally by `sys_updated_on`. The connector contract is in `etl/connectors.py`.
- *What would you do in the first month?* Discovery and the DPIA (`docs/requirements.md` §7), then re-baseline data quality on real extracts.
