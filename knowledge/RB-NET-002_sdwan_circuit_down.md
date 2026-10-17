---
id: RB-NET-002
title: Runbook - SD-WAN circuit down / carrier fault
classification: internal
owner: Network Operations
applies_to: SVC-004 Business Broadband & SD-WAN; SVC-006 Leased Lines
reviewed: 2026-03-02
---
# SD-WAN circuit down

1. Check carrier status portal and the upstream alert feed for an area outage.
2. Confirm whether SD-WAN has failed over to the secondary circuit or LTE. If failover worked, downgrade the incident to P3 and monitor.
3. Run line tests from the carrier portal; if the fault is on the carrier side, raise a carrier ticket and record the reference in the incident.
4. If the CPE is unreachable but the line tests clean, dispatch Field Engineering (SVC-012) with a replacement appliance.
5. Escalate to the carrier account manager if the carrier misses its own 5-hour fix time on a leased line.
