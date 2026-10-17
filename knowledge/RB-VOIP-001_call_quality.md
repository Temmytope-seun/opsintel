---
id: RB-VOIP-001
title: Runbook - Hosted VoIP call quality degradation
classification: internal
owner: Voice Engineering
applies_to: SVC-005 Hosted VoIP Telephony
reviewed: 2026-05-20
---
# VoIP call quality degradation

1. Check jitter, latency and packet loss on the SBC for the affected tenant (jitter > 30 ms or loss > 1% is service-affecting).
2. Determine whether the customer's access circuit is one of ours (SVC-004/SVC-006). If so, check for edge switch instability (RB-NET-001) first - most voice complaints during Q3 2026 were downstream of network faults.
3. Verify QoS markings (EF/DSCP 46) are preserved end-to-end.
4. If the SBC itself is degraded, fail over to the secondary SBC cluster and raise a P2.
