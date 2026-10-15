---
name: build-pack-pitfalls
description: build_pack.py FAIL causes and recipe pitfalls in audit-plan.json (typed figures, rule accounting, near-match threshold filter, n)
metadata:
  type: feedback
---

How-to lessons from building audit-plan.json. Verify against the current skill and builder first: they win over this note.

- **Typed-figure check:** any digit not inside a `{{$.path}}` placeholder, a citation tag, or a prose ID (CPR-, AUD-, GAP-, R-, T-, L1–5 …) fails the build. "S.151 Officer" fails because the dot leaves "151" standing alone; write "S151 Officer". Write durations in words ("three years", "thirty days"). Control IDs (C-xx-n) are not in the prose-ID pattern, so leave them out of prose.
- **Rule accounting:** rules cited only in `memo.*` do NOT count toward coverage. Only these count: risk rule_ids and register text, control descriptions, and test steps. A rule may not be both cited and in `rules_not_tested`.
- **Not-tested reasons get challenged.** If the pack already requests the documents a rule needs (contracts, invoices), testing the rule is better than a "no trace in payment data" reason. Keep each reason consistent with how the memo treats the same input (e.g. the null Threshold).
- **near-matches.csv and other supplier files can hold suppliers below the quotation threshold.** Add `"annualised_estimate": {">=": "$.tests.off_contract.parameters.threshold"}` (or the equivalent column) so the sample never questions small suppliers.
- **`n`:** an integer at least the auto size is allowed. Use the population size to draw a whole small population when the sort would otherwise bias the draw (e.g. split windows sorted by total_gbp miss the few-payment windows).
- **Cite metrics that match the drawn population.** If no metric does, say in the step why the counts differ.
- **Memo must not contradict the program.** When a challenge adds a test, re-read the Limitations text.

**Why:** each of these cost a FAIL or an accepted challenge in a past run.
**How to apply:** check this list before the first build. See also [[planner-protocol-lessons]].
