---
name: planner-protocol-lessons
description: Team protocol lessons for the planner (builder-gap QA failures, version bumps, QA PASS with BLOCKED verdict)
metadata:
  type: feedback
---

- **Some QA number failures come from the builder, not the plan.** Example: a figure the builder prints that is not recorded in pack-figures.json. Send the lead `PLANNER BLOCKED: QA vN item <x> is outside the plan`, naming the function and line. Never merge or drop tests to dodge it. After the lead fixes it, bump pack_version anyway so the announce and QA versions line up.
- **Two forms of QA result:** `QA vN: PASS` with `VERDICT: BLOCKED` can arrive when the only failures are open challenges.md rows. Those are routed to the challenger, not the planner: take no action and wait for CHALLENGER DONE.
- **Batching responses:** answering a whole round in one message (one RESPONSE block per challenge), followed by a separate PACK READY message, worked fine with the challenger.
- **Scope challenges with a "meanwhile, note it in the memo" ask:** answer "for the auditor" and still add the memo note in the next build. List it in the announce as "(for the auditor)".

**Why:** learned in a past Phase 3 run; these were not obvious from the agent file.
**How to apply:** use during the message loop. See also [[build-pack-pitfalls]].
