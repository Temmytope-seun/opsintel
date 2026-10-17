# User guide and training plan

## 1. Getting started

Open the dashboard (`make ui`, then http://localhost:8501). Pick your demo identity in the sidebar. Each identity has a role, and the role decides what you can see and do.

| View | What it is for |
|---|---|
| **Overview** | Headline KPIs for the latest month, SLA breach rate by category against last quarter, root causes, volumes, cost by business unit, emerging anomalies |
| **Ask OpsIntel** | Ask questions in plain English. Every answer lists its evidence (E1, E2 …) with the data, chart and SQL behind it |
| **Risk & anomalies** | Next week's SLA risk per service, with uncertainty and drivers; open requests most likely to miss their date; anomalies |
| **Actions & approvals** | Proposed actions with their evidence; approve, reject, start or complete them |
| **Data quality & lineage** | Source quality before and after processing; quarantined records; lineage of every table; metric definitions |
| **Audit log** | Every question, tool call and decision, hash-chained (auditors and executives only) |

### Using live ServiceNow data

Two dashboards can run at the same time:

| Dashboard | Start it with | Address | Data |
|---|---|---|---|
| Synthetic | `make ui` | http://localhost:8501 | Fictional company with planted signals (default) |
| ServiceNow | `make sn-ui` | http://localhost:8502 | Last `make sn-sync` extract from the connected instance |

The ServiceNow dashboard shows *Data source: servicenow* and the date range under the title. Run `make sn-sync` to refresh the data, then restart the dashboard, because the sync rebuilds its database. A standard instance has no finance, monitoring or outage data, so cost tiles are hidden and questions about costs or downtime get a clear "not available from this source" answer. The risk forecast needs several months of incident history and says so when there isn't enough. Credentials live in the project's `.env` file. Set them up once with the platform owner, as described in the README, and never share them in chat or email.

## 2. Reading an answer

- **Evidence tags** like `[E2]` point to the evidence panel under the answer. Open it to see the exact rows and SQL.
- **"All figures traced to evidence"** means every number in the text was found in the evidence. A ⚠️ warning lists any number that was not found. Treat those as unverified.
- **"I can't answer that reliably…"** means the data does not cover your question. This is deliberate: the assistant does not guess.
- **Withheld text** means a document or ticket contained text that looked like instructions to an AI. It was hidden from the model.

## 3. Good questions to ask

- "Why did our operational costs increase this month?"
- "Which service category had the highest SLA breach rate last quarter, and what explains the increase?"
- "Which services are at greatest risk of missing their SLA next week?"
- "What should the support team do when a recurring network incident occurs?"
- "Which business process should we improve first, and why?"

Include a period when it matters (`Q2 2026`, `August 2026`, `this month`). "This month" and "last quarter" refer to the latest data snapshot.

## 4. Turning insight into action

1. Under an answer, choose **Propose an action from this answer**. Give it a title, an owner group and the evidence to attach.
2. A manager who is **not** the proposer approves or rejects it on the Actions page. The owner group is notified.
3. The owner marks it *in progress*, then *done* with an outcome note. Everything is audited.

## 5. Training plan (90 minutes per cohort)

Slides for this session (13 slides with speaker notes): [OpsIntel AI user training deck](https://claude.ai/artifact/QGo2fUhUCnFJUt9RudasdL). The link is private until the owner shares it.

| Segment | Minutes | Content |
|---|---|---|
| Why and what | 10 | The problem; what the platform does and does not do |
| Live demo | 20 | The demo script (docs/demo_script.md) |
| Hands-on | 35 | Five role-specific tasks, e.g. find this quarter's worst category and its cause; raise an action |
| Trust and limits | 15 | Evidence, grounding warnings, abstention, uncertainty in risk scores, when not to rely on it |
| Feedback | 10 | Feedback form (below) |

## 6. Feedback form

1. Which task did you use OpsIntel for? (free text)
2. The answer was correct. (1–5)
3. I could check where the answer came from. (1–5)
4. It saved me time compared with how I would normally do this. (1–5, plus estimated minutes saved)
5. I would act on this recommendation after reviewing the evidence. (1–5)
6. Something it got wrong or could not answer: (free text)
7. System Usability Scale (10 standard items)
