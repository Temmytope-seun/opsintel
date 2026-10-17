# Data dictionary

_Generated from the metadata catalogue (`opsintel/db.py`) by `python -m opsintel.cli docs`._

## Metric definitions

- **sla_breach_rate** - Share of incidents opened in the period whose SLA outcome is known that breached the resolution target. Open incidents count as breached once they pass target; open incidents still inside target are excluded.
- **mttr_hours** - Mean resolution_hours of incidents opened in the period and resolved.
- **outage_minutes** - Sum of customer-facing downtime minutes of incidents opened in the period.
- **operating_cost** - Sum of costs.amount_gbp for the accounting month(s).
- **on_time_delivery_rate** - Share of closed service requests in the period that met their due date.

## actions

0 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| action_id | TEXT |  |  |  |
| created_at | TEXT |  |  |  |
| created_by | TEXT |  |  |  |
| title | TEXT |  |  |  |
| rationale | TEXT |  |  |  |
| evidence | TEXT |  |  |  |
| service_id | TEXT |  |  |  |
| owner_group | TEXT |  |  |  |
| priority | TEXT |  |  |  |
| status | TEXT |  |  |  |
| decided_by | TEXT |  |  |  |
| decided_at | TEXT |  |  |  |
| decision_note | TEXT |  |  |  |
| outcome | TEXT |  |  |  |

## alerts

14,370 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| alert_id | TEXT | Monitoring event id (deduplicated) |  | Monitoring REST API |
| ts | TEXT |  |  |  |
| asset_id | TEXT |  |  |  |
| service_id | TEXT | Service resolved via CMDB asset -> service |  | derived |
| severity | TEXT | Normalised to lower case |  | Monitoring REST API |
| metric | TEXT |  |  |  |
| value | REAL |  |  |  |

## assets

362 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| asset_id | TEXT |  |  |  |
| service_id | TEXT |  |  |  |
| asset_type | TEXT |  |  |  |
| vendor | TEXT |  |  |  |
| install_date | TEXT |  |  |  |
| status | TEXT |  |  |  |
| location | TEXT |  |  |  |
| firmware_version | TEXT |  |  |  |

## audit_log

23 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| seq | INTEGER |  |  |  |
| ts | TEXT |  |  |  |
| user_id | TEXT |  |  |  |
| role | TEXT |  |  |  |
| event | TEXT |  |  |  |
| detail | TEXT |  |  |  |
| prev_hash | TEXT |  |  |  |
| hash | TEXT |  |  |  |

## business_units

5 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| bu_id | TEXT |  |  |  |
| name | TEXT |  |  |  |

## catalog

41 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| table_name | TEXT |  |  |  |
| column_name | TEXT |  |  |  |
| description | TEXT |  |  |  |
| is_pii | INTEGER |  |  |  |
| source | TEXT |  |  |  |

## costs

684 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| month | TEXT | Accounting month YYYY-MM |  | Finance export |
| service_id | TEXT |  |  |  |
| cost_type | TEXT | Staff, Licences, Third-party, Hardware or Energy |  | Finance export |
| amount_gbp | REAL | Cost in GBP (parsed from currency string) |  | Finance export |
| description | TEXT | Finance ledger narrative |  | Finance export |

## customers

120 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| customer_id | TEXT | Customer account code |  | CMDB.core_company |
| name | TEXT | Customer organisation name |  | CMDB.core_company |
| sector | TEXT | Industry sector |  | CMDB.core_company |
| contact_email | TEXT | Named operational contact e-mail | yes | CMDB.core_company |
| contact_phone | TEXT | Named operational contact phone | yes | CMDB.core_company |
| contract_value_gbp | INTEGER | Annual contract value (GBP) |  | CMDB.core_company |
| account_manager | TEXT | Internal account manager | yes | CMDB.core_company |

## customers_safe

120 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| customer_id | TEXT |  |  |  |
| name | TEXT |  |  |  |
| sector | TEXT |  |  |  |
| contract_value_gbp | INTEGER |  |  |  |

## dq_results

126 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| run_id | TEXT |  |  |  |
| source | TEXT |  |  |  |
| stage | TEXT |  |  |  |
| metric | TEXT |  |  |  |
| value | REAL |  |  |  |

## etl_rejects

40 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| run_id | TEXT |  |  |  |
| source | TEXT |  |  |  |
| record_key | TEXT |  |  |  |
| reason | TEXT |  |  |  |
| payload | TEXT |  |  |  |

## etl_runs

1 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| run_id | TEXT |  |  |  |
| started_at | TEXT |  |  |  |
| finished_at | TEXT |  |  |  |
| status | TEXT |  |  |  |

## incidents

7,484 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| incident_id | TEXT | ITSM incident number |  | ITSM export |
| opened_at | TEXT | Timestamp the incident was logged (UTC, ISO-8601) |  | ITSM export |
| resolved_at | TEXT | Timestamp resolved; NULL if still open at snapshot |  | ITSM export |
| status | TEXT | ITSM state at snapshot |  | ITSM export |
| service_id | TEXT |  |  |  |
| customer_id | TEXT |  |  |  |
| asset_id | TEXT |  |  |  |
| impact | INTEGER |  |  |  |
| urgency | INTEGER |  |  |  |
| priority | TEXT | P1-P4. Imputed from impact x urgency matrix when missing |  | ITSM export + rule |
| priority_imputed | INTEGER | 1 if priority was imputed by the ETL |  | derived |
| category | TEXT | Service category (from CMDB service) |  | derived |
| assignment_group | TEXT |  |  |  |
| root_cause | TEXT | Root cause code recorded at resolution |  | ITSM export |
| short_description | TEXT | Free-text summary. Untrusted user-supplied text |  | ITSM export |
| caused_outage | INTEGER | 1 if the incident caused customer-facing downtime |  | ITSM export |
| outage_minutes | INTEGER | Customer-facing downtime in minutes |  | ITSM export |
| reopened | INTEGER |  |  |  |
| resolution_hours | REAL | resolved_at - opened_at in hours |  | derived |
| sla_target_hours | REAL | Resolution target for the priority |  | derived from sla_policies |
| sla_breached | INTEGER | 1 if resolution exceeded target (or open past target); NULL if open and within target |  | derived |
| opened_month | TEXT | YYYY-MM of opened_at |  | derived |
| opened_quarter | TEXT | YYYYQn of opened_at |  | derived |

## lineage

9 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| run_id | TEXT |  |  |  |
| target_table | TEXT |  |  |  |
| source_name | TEXT |  |  |  |
| source_type | TEXT |  |  |  |
| source_uri | TEXT |  |  |  |
| source_sha256 | TEXT |  |  |  |
| rows_in | INTEGER |  |  |  |
| rows_out | INTEGER |  |  |  |
| rows_rejected | INTEGER |  |  |  |
| transforms | TEXT |  |  |  |

## notifications

0 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| notification_id | INTEGER |  |  |  |
| created_at | TEXT |  |  |  |
| channel | TEXT |  |  |  |
| recipient | TEXT |  |  |  |
| subject | TEXT |  |  |  |
| body | TEXT |  |  |  |
| delivered | INTEGER |  |  |  |

## service_requests

4,202 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| request_id | TEXT | ITSM requested-item number |  | ITSM export |
| opened_at | TEXT |  |  |  |
| due_at | TEXT | Committed delivery date |  | ITSM export |
| closed_at | TEXT |  |  |  |
| status | TEXT |  |  |  |
| service_id | TEXT |  |  |  |
| customer_id | TEXT |  |  |  |
| request_type | TEXT |  |  |  |
| target_days | REAL |  |  |  |
| blocked_reason | TEXT | Why fulfilment is waiting, if anything |  | ITSM export |
| assignment_group | TEXT |  |  |  |
| fulfilment_days | REAL | closed_at - opened_at in days |  | derived |
| met_due_date | INTEGER | 1 if closed on/before due_at; NULL while open |  | derived |

## services

14 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| service_id | TEXT | Service code (CMDB) |  | CMDB.cmdb_service |
| name | TEXT | Canonical service name |  | CMDB.cmdb_service |
| category | TEXT | Service category used for SLA reporting (Network, Cloud, ...) |  | CMDB.cmdb_service |
| bu_id | TEXT | Owning business unit |  | CMDB.cmdb_service |
| tier | TEXT | Commercial service tier |  | CMDB.cmdb_service |
| owner_group | TEXT | Resolver group that owns the service |  | CMDB.cmdb_service |

## sla_policies

4 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| priority | TEXT |  |  |  |
| label | TEXT |  |  |  |
| response_target_hrs | REAL |  |  |  |
| resolution_target_hrs | REAL |  |  |  |

## users

6 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| user_id | TEXT |  |  |  |
| full_name | TEXT |  |  |  |
| role | TEXT |  |  |  |

## v_incidents

7,484 rows

| Column | Type | Description | PII | Source |
|---|---|---|---|---|
| incident_id | TEXT |  |  |  |
| opened_at | TEXT |  |  |  |
| resolved_at | TEXT |  |  |  |
| status | TEXT |  |  |  |
| service_id | TEXT |  |  |  |
| customer_id | TEXT |  |  |  |
| asset_id | TEXT |  |  |  |
| impact | INTEGER |  |  |  |
| urgency | INTEGER |  |  |  |
| priority | TEXT |  |  |  |
| priority_imputed | INTEGER |  |  |  |
| category | TEXT |  |  |  |
| assignment_group | TEXT |  |  |  |
| root_cause | TEXT |  |  |  |
| short_description | TEXT |  |  |  |
| caused_outage | INTEGER |  |  |  |
| outage_minutes | INTEGER |  |  |  |
| reopened | INTEGER |  |  |  |
| resolution_hours | REAL |  |  |  |
| sla_target_hours | REAL |  |  |  |
| sla_breached | INTEGER |  |  |  |
| opened_month | TEXT |  |  |  |
| opened_quarter | TEXT |  |  |  |
| service_name | TEXT |  |  |  |
| bu_id | TEXT |  |  |  |
| business_unit | TEXT |  |  |  |
| tier | TEXT |  |  |  |

## ServiceNow source mapping

When the platform is loaded from a ServiceNow instance (`make sn-sync`), the tables above are filled as follows. The same validation, entity matching, quarantine and lineage apply.

| Platform field | ServiceNow source | Rule |
|---|---|---|
| `incidents.incident_id` | `incident.number` | as is |
| `incidents.opened_at / resolved_at` | `incident.opened_at / resolved_at (else closed_at)` | UTC 'YYYY-MM-DD HH:MM:SS' |
| `incidents.status` | `incident.state (display)` | as is |
| `incidents.priority` | `incident.priority 1-5` | 1-4 -> P1-P4; 5 (Planning) -> P4; missing -> impact x urgency matrix |
| `incidents.impact / urgency` | `incident.impact / urgency` | as is (1-3) |
| `incidents.service_id` | `incident.business_service` | entity-matched to services; empty -> 'Unassigned service' |
| `incidents.customer_id` | `incident.company` | empty or unknown -> 'Internal / unspecified' |
| `incidents.asset_id` | `incident.cmdb_ci` | only CIs referenced by incidents are extracted |
| `incidents.category` | `incident.category (display)` | carried through (Network, Software, ...) |
| `incidents.root_cause` | `incident.problem_id -> subcategory -> close_code` | first available; problem link needs a role that can read it |
| `incidents.assignment_group` | `incident.assignment_group (display)` | as is |
| `incidents.reopened` | `incident.reopen_count` | > 0 |
| `incidents.caused_outage / outage_minutes` | `(not in a standard instance)` | 0 - recorded as a mapping gap |
| `service_requests.*` | `sc_req_item` | due_at from due_date -> estimated_delivery -> opened + default target days |
| `services.*` | `cmdb_ci_service` | category = service_classification; tier = busines_criticality; owner = support_group |
| `customers.*` | `core_company` | no contact details are extracted |
| `assets.*` | `cmdb_ci (referenced CIs)` | service = most frequent business service on that CI's incidents |
| `business_units.*` | `business_unit` | optional; missing -> 'Unassigned business unit' |
| `sla_policies.*` | `(platform policy P1-P4)` | ServiceNow task_sla is not used; targets from POL-SLA-001 |
| `costs, alerts` | `(not in a standard instance)` | skipped; features that need them say so |
