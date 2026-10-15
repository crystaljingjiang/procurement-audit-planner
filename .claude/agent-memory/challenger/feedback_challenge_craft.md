---
name: challenge-craft
description: Which challenge kinds the planner acted on versus routed to the auditor, and protocol timing lessons with QA
metadata:
  type: feedback
---

Planner-actionable challenges (sample, test, coverage) that name the exact pack section and an existing PBC item get accepted and rebuilt quickly. Anything that widens a population beyond the approved risk definition (other spend tags, new populations, input parameters) is answered "for the auditor", so phrase those as auditor decisions from the start.

**Why:** the planner treats the approved register definitions as fixed scope, and only changes plan content within them.

**How to apply:**
- Check whether a test's cited metrics trace to the population it actually draws (filtered tag or threshold vs all-supplier counts). This kind of mismatch is found reliably.
- After an accepted change, re-read the memo Limitations and the rules-not-tested reasons for contradictions the change created. This is good round-2 material.
- Check whether "not tested because X" reasons stay consistent once another rule with the same dependency gets tested.
- QA may run check_trace.py before you record responses. Reply that rows are closed or legitimately open, and never close a row early. Run `.venv/bin/python scripts/checks/check_trace.py` yourself before CHALLENGER DONE.
- Write the row as `open` with "awaiting" in the response cell when you send, then replace that in place once the response arrives.
