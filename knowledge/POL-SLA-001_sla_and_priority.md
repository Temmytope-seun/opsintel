---
id: POL-SLA-001
title: Policy - Service levels and incident priority matrix
classification: public
owner: Service Management Office
reviewed: 2026-01-05
---
# Service levels and priority

Priority is derived from **impact** (1 = organisation-wide, 2 = department/site, 3 = single user) and **urgency** (1 = work stopped, 2 = degraded, 3 = can wait):

| Impact \ Urgency | 1 | 2 | 3 |
|---|---|---|---|
| 1 | P1 | P2 | P3 |
| 2 | P2 | P3 | P4 |
| 3 | P3 | P4 | P4 |

| Priority | Response target | Resolution target |
|---|---|---|
| P1 Critical | 15 minutes | 4 hours |
| P2 High | 1 hour | 8 hours |
| P3 Moderate | 4 hours | 24 hours |
| P4 Low | 8 hours | 72 hours |

Resolution targets are measured in elapsed (24x7) hours. A service meets its SLA for a reporting period when at least **90%** of its incidents are resolved within target. Repeated SLA misses (two consecutive months) trigger a service improvement plan owned by the service owner.
