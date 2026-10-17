---
id: RB-CLD-001
title: Runbook - Virtual Private Server host capacity exhaustion
classification: internal
owner: Cloud Platform
applies_to: SVC-007 Virtual Private Servers
reviewed: 2026-06-30
---
# VPS host capacity exhaustion

## Triggers
- Hypervisor host CPU > 85% for 15 minutes, or memory ballooning on more than 10% of VMs.
- Customers report slow VMs; incidents with root cause *Capacity exhaustion*.

## Actions
1. Identify the saturated cluster and the top 10 consuming VMs.
2. Live-migrate noisy workloads to hosts with headroom (keep N+1 per cluster).
3. If cluster headroom is below N+1, power on reserve hosts. Note: powering on reserve hosts increases hypervisor licence consumption under per-core licensing - inform Finance and the Cloud Platform manager.
4. Contact customers whose VMs exceed their contracted vCPU allocation.
5. If the cluster stays above 85% for three consecutive days, raise a capacity change request (POL-CHG-001) for additional hardware.

## Escalate when
- More than 20 customer VMs are affected, or a Gold customer production VM is degraded for more than 1 hour.
