---
id: PRB-0042
title: Problem record - Veltrix edge switch firmware 4.2.7 stack re-election defect (known error KE-0042)
classification: restricted
owner: Network Operations - Problem Management
applies_to: SVC-004; SVC-006
reviewed: 2026-09-22
---
# PRB-0042 - Veltrix firmware 4.2.7 known error

**Status:** Known error, workaround available, permanent fix pending change approval.

**Root cause:** A defect in Veltrix firmware 4.2.7 causes the stack master to re-elect under sustained control-plane load, rebooting stack members. Fleet impact grew sharply from July 2026 as more sites took on SD-WAN traffic.

**Affected estate:** Veltrix edge switch stacks running 4.2.7 on Business Broadband & SD-WAN and Leased Lines.

**Workaround:** RB-NET-001 step 5.

**Permanent fix:** Upgrade to firmware 4.2.9. Proposed rollout: pilot 5 sites, then 20 sites per maintenance window. Estimated effort 3 engineer-weeks. Vendor has confirmed the fix in their release notes.

**Commercial note:** Vendor call-out costs and engineer overtime have increased while the defect remains unfixed. The vendor has offered service credits subject to evidence of impact.
