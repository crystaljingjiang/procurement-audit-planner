---
name: builder-checks
description: How build_register.py checks rubric levels, signals and typed figures; pitfalls when writing risk-ratings.json
metadata:
  type: reference
---

Builder behaviour worth knowing before writing ratings (verify against the current build_register.py; it wins):

- L3+ "general procurement" check is a substring test: some holding signal's `metric` path must contain `general_procurement`. Tests without a by-tag breakdown in analytics.json cannot reach L3 that way; check the test's keys first, never invent a path.
- Threshold clustering at L3+ needs a holding signal whose `than` path contains `comparator` (e.g. `band_count > ...comparator_count`). A `<` signal is a clean way to show why it stays at L2.
- Signals need numeric operands; booleans like `$.contracts.register_present` can be cited as `[metric:...]` but not used as signals.
- Filters `[?threshold==25000]` work numerically; a filter must match exactly one element (a tag filter over a top20 list usually fails). Chained filters do not work.
- Typed-figure WARN catches any digit in prose outside IDs/tags/placeholders (including "30-day", "clause 1.6.2"); use placeholders such as `parameters.window_days|int` or cite the rule instead.
- L1 risks need no signals but still need a resolvable citation; DIM-CMP needs no financial_basis.

Related: [[risk-assessment skill]]
