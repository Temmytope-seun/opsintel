# OpsIntel AI - REST API

_Generated from the OpenAPI schema by `tools/gen_api_docs.py`. Interactive docs: run `make api` and open http://localhost:8000/docs._

Governed operational-intelligence API: KPIs, risk, anomalies, AI decision support, actions and audit.

## Authentication (demo)

Every endpoint except `/health` requires the header `X-User: <user_id>`. Demo users: `exec.demo`, `opsmgr.demo`, `opsmgr2.demo`, `analyst.demo`, `desk.demo`, `audit.demo`. Unknown users get **401**; a role without permission gets **403**. In a pilot this header is replaced by an OIDC bearer token whose group claims map to the same roles.

## Endpoints

| Method | Path | Summary | Access |
|---|---|---|---|
| GET | `/health` | Service health, last ETL run and data coverage | public (no `X-User` needed) |
| GET | `/kpis/headline` | Headline KPIs for the latest month vs the previous month | any known user |
| GET | `/kpis/sla-breach-rate` | SLA breach rate for a period, grouped, vs the previous period | any known user |
| GET | `/kpis/root-causes` | Root-cause breakdown for a period with change vs the previous period | any known user |
| GET | `/kpis/downtime` | Recurring causes of customer-facing downtime | any known user |
| GET | `/kpis/cost-change` | Operating cost change vs the previous month, with drivers | roles with financial access (not service_desk) |
| GET | `/kpis/improvement-priorities` | Process areas ranked by customer impact | any known user |
| GET | `/risk/sla-next-week` | Probability each service misses 90% SLA compliance next week | any known user |
| GET | `/risk/delivery` | Open service requests ranked by risk of missing their due date | any known user |
| GET | `/forecast/{metric}` | Three-month forecast of incident volume or operating cost, with 80% range and backtest | any known user |
| GET | `/anomalies/{kind}` | Recent operational or cost anomalies | `cost` needs financial access |
| POST | `/ask` | Ask the assistant a question; returns the answer with evidence and grounding | any known user |
| GET | `/actions` | List actions, optionally filtered by status | any known user |
| POST | `/actions` | Propose an action with supporting evidence | executive, ops_manager, analyst; at least one evidence record |
| POST | `/actions/{action_id}/approve` | Approve a proposed action | executive, ops_manager; not the proposer |
| POST | `/actions/{action_id}/reject` | Reject a proposed action | executive, ops_manager; not the proposer |
| POST | `/actions/{action_id}/progress` | Move an approved action to in progress or done | roles that can propose or approve |
| GET | `/audit` | Most recent audit-log entries | auditor, executive |
| GET | `/audit/verify` | Verify the audit log's hash chain | auditor, executive |
| GET | `/data-quality` | Data-quality metrics and rejects from the latest ETL run | any known user |
| GET | `/lineage` | Lineage of every table from the latest ETL run | any known user |
| GET | `/catalog` | Metadata catalogue and metric definitions | any known user |

## Details

### GET `/health`

Service health, last ETL run and data coverage

Responses: `200`

### GET `/kpis/headline`

Headline KPIs for the latest month vs the previous month

Responses: `200`, `422`

### GET `/kpis/sla-breach-rate`

SLA breach rate for a period, grouped, vs the previous period

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `period` | query | string | no | last_quarter |
| `group_by` | query | `category` / `service` / `priority` / `business_unit` / `assignment_group` | no | category |

Responses: `200`, `422`

### GET `/kpis/root-causes`

Root-cause breakdown for a period with change vs the previous period

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `period` | query | string | no | last_quarter |
| `category` | query | string | null | no |  |
| `rank_by` | query | `incidents` / `outage_minutes` / `breaches` | no | incidents |

Responses: `200`, `422`

### GET `/kpis/downtime`

Recurring causes of customer-facing downtime

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `months` | query | integer | no | 6 |

Responses: `200`, `422`

### GET `/kpis/cost-change`

Operating cost change vs the previous month, with drivers

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `month` | query | string | no | this_month |
| `group_by` | query | `service_cost_type` / `service` / `cost_type` / `business_unit` | no | service_cost_type |

Responses: `200`, `422`

### GET `/kpis/improvement-priorities`

Process areas ranked by customer impact

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `period` | query | string | no | last_quarter |

Responses: `200`, `422`

### GET `/risk/sla-next-week`

Probability each service misses 90% SLA compliance next week

Responses: `200`, `422`

### GET `/risk/delivery`

Open service requests ranked by risk of missing their due date

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `limit` | query | integer | no | 15 |

Responses: `200`, `422`

### GET `/forecast/{metric}`

Three-month forecast of incident volume or operating cost, with 80% range and backtest

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `metric` | path | `incidents` / `cost` | yes |  |
| `group_by` | query | string | null | no |  |

Responses: `200`, `422`

### GET `/anomalies/{kind}`

Recent operational or cost anomalies

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `kind` | path | `operational` / `cost` | yes |  |

Responses: `200`, `422`

### POST `/ask`

Ask the assistant a question; returns the answer with evidence and grounding

Request body: `AskBody`

| Field | Type | Required |
|---|---|---|
| `question` | string | yes |
| `engine` | `auto` / `claude` / `rules` | no |

Responses: `200`, `422`

### GET `/actions`

List actions, optionally filtered by status

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `status` | query | string | null | no |  |

Responses: `200`, `422`

### POST `/actions`

Propose an action with supporting evidence

Request body: `ProposeBody`

| Field | Type | Required |
|---|---|---|
| `title` | string | yes |
| `rationale` | string | yes |
| `evidence` | array | yes |
| `priority` | `P1` / `P2` / `P3` / `P4` | no |
| `service_id` | string | null | no |
| `owner_group` | string | null | no |

Responses: `201`, `422`

### POST `/actions/{action_id}/approve`

Approve a proposed action

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `action_id` | path | string | yes |  |

Request body: `DecisionBody`

| Field | Type | Required |
|---|---|---|
| `note` | string | no |

Responses: `200`, `422`

### POST `/actions/{action_id}/reject`

Reject a proposed action

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `action_id` | path | string | yes |  |

Request body: `DecisionBody`

| Field | Type | Required |
|---|---|---|
| `note` | string | no |

Responses: `200`, `422`

### POST `/actions/{action_id}/progress`

Move an approved action to in progress or done

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `action_id` | path | string | yes |  |

Request body: `ProgressBody`

| Field | Type | Required |
|---|---|---|
| `status` | `in_progress` / `done` | yes |
| `outcome` | string | no |

Responses: `200`, `422`

### GET `/audit`

Most recent audit-log entries

| Parameter | In | Type | Required | Default |
|---|---|---|---|---|
| `limit` | query | integer | no | 100 |

Responses: `200`, `422`

### GET `/audit/verify`

Verify the audit log's hash chain

Responses: `200`, `422`

### GET `/data-quality`

Data-quality metrics and rejects from the latest ETL run

Responses: `200`, `422`

### GET `/lineage`

Lineage of every table from the latest ETL run

Responses: `200`, `422`

### GET `/catalog`

Metadata catalogue and metric definitions

Responses: `200`, `422`

## Example

```bash
curl -s -X POST http://localhost:8000/ask \
  -H 'X-User: analyst.demo' -H 'Content-Type: application/json' \
  -d '{"question": "What are the recurring causes of service downtime?", "engine": "rules"}'
```

The response contains `answer`, `engine`, `abstained`, `grounding` (figures checked against evidence), `latency_ms` and `evidence` (one entry per tool call with its SQL and document sources).
