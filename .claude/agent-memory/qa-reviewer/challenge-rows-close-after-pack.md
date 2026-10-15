---
name: challenge-rows-close-after-pack
description: Open challenges.md rows fail trace right after a PACK READY that responds to them; route to challenger, still send planner PASS
metadata:
  type: feedback
---

The challenger records its responses and closes challenges.md rows only after it has checked the pack the planner announced. So the QA run on a PACK READY that answers a round of challenges usually shows trace FAIL "challenge #N is not closed (status 'open')" for that round's rows. The challenger can close them later without any new PACK READY.

**Why:** found in a Phase 3 run. The planner's pack was clean, but each version's run still failed on open rows until the challenger caught up.

**How to apply:** Send those FAIL lines to the challenger only. If nothing is routed to the planner, send the planner `QA vN: PASS` (table as printed). Run the checks again after CHALLENGER DONE and PLANNER DONE, even when the pack version hasn't changed. Never count the challenger's own local check run as the result.
