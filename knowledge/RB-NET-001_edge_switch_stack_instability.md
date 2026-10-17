---
id: RB-NET-001
title: Runbook - Edge switch stack instability (reboots, master re-election, packet loss)
classification: internal
owner: Network Operations
applies_to: SVC-004 Business Broadband & SD-WAN; SVC-006 Leased Lines
reviewed: 2026-08-14
---
# Edge switch stack instability

## Symptoms
- Customer site loses connectivity for 2-15 minutes, then recovers.
- Monitoring raises `stack_member_reset` (critical/major) on an edge switch stack.
- Logs show stack master re-election or firmware watchdog reset.
- SD-WAN overlay tunnels flap while the stack re-forms.

## Troubleshooting sequence
1. **Confirm scope.** Check monitoring for other `stack_member_reset` events on the same site and on other sites in the last 24h. More than three sites affected in 24h indicates a fleet-level issue: go straight to step 7 (escalate).
2. **Check firmware version.** Run `show version` on every stack member. Veltrix stacks on firmware **4.2.7** are affected by known error KE-0042 (see PRB-0042). If the version is 4.2.7, apply the workaround in step 5 before further diagnosis.
3. **Check power and cabling.** Verify both PSUs are healthy and stack cables are seated. Replace any stack cable reporting CRC errors.
4. **Collect diagnostics.** Capture `show tech-support stack` and the crash file from flash *before* reloading anything. Attach both to the incident; the vendor will not progress a case without them.
5. **Workaround for KE-0042.** Disable the `stack-mac persistent` feature and set the master priority explicitly (`switch 1 priority 15`). This prevents the re-election loop on 4.2.7 in most cases. Record the change under the emergency change process (POL-CHG-001).
6. **Restore service.** If the stack is still unstable, fail the site over to the 4G backup path (SD-WAN policy `failover-lte`) and inform the customer of degraded bandwidth.
7. **Escalate.**
   - Raise a P2 (or P1 if more than 5 sites / a Gold customer HQ is down) and engage the Major Incident Manager per POL-MIM-001.
   - Open a vendor case with Veltrix TAC, priority S2, referencing KE-0042.
   - Link the incident to problem record PRB-0042.

## Escalate immediately when
- The same site has had 3+ stack resets in 7 days.
- A Gold-tier customer HQ site is affected.
- The workaround in step 5 fails.

## Permanent fix
Firmware 4.2.9 resolves KE-0042. Upgrades must be scheduled through the normal change process (CAB approval, maintenance window, rollback plan). Do not upgrade ad hoc during an incident.
