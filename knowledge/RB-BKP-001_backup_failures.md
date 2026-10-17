---
id: RB-BKP-001
title: Runbook - Managed backup job failures
classification: internal
owner: Cloud Platform
applies_to: SVC-008 Managed Backup & DR
reviewed: 2026-02-11
---
# Backup job failures

1. Check the backup console for failed jobs in the last 24h and group by error code.
2. Re-run failed jobs once. Two consecutive failures for the same customer = P3 incident.
3. Repository capacity above 90% blocks new restore points: expand the repository or apply retention policy.
4. Any failure affecting a customer with a contracted RPO of 4 hours or less must be escalated to the Cloud Platform manager within 1 hour.
