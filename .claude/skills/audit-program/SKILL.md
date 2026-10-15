---
name: audit-program
description: Turn the auditor-approved risks into an audit program. The planner writes judgments (controls, test steps, sample recipes, PBC items, memo text) to outputs/audit-plan.json; build_pack.py checks the approval gate, resolves every citation, draws and verifies every sample, checks rule and control coverage, and renders planning-memo.md, risk-control-matrix.md, audit-program.md, samples/ and pack-figures.json. Loaded by the planner.
---

# audit-program

You judge; the builder computes. You write **judgments only** to
`outputs/audit-plan.json`: for each approved risk, the controls you expect,
the test steps, a recipe for the sample, and what to request from the
council. `build_pack.py` (next to this file) does everything else:

```bash
.venv/bin/python .claude/skills/audit-program/build_pack.py --gate   # approval gate only
.venv/bin/python .claude/skills/audit-program/build_pack.py          # gate + full pack
```

Exit 0 means the pack was written; exit 1 prints `FAIL` lines and writes
nothing. Never edit the outputs it writes; change the plan and rebuild.

## The gate

`--gate` passes only when:
- the register is a **revision** (1 or later), not the draft;
- `risk-register.md` still matches the builder's state (not edited by hand);
- every rated risk has a decision in `outputs/auditor-comments.md`, and every
  decision has been applied in that revision;
- `risk-ratings.json` has not changed since the register was built.

**Approved scope** = risks the auditor marked Approve or Amend, not
rejected, with proposed scope `in`. The gate prints it. Plan exactly those
risks: no more, no fewer. If the gate is closed, stop: the auditor completes
`auditor-comments.md` and the risk-assessor issues a revision.

## Inputs

| File | Use |
| --- | --- |
| `outputs/risk-register.md`, `outputs/risk-ratings.json` | the approved risks, their focus, rules and evidence |
| `outputs/auditor-comments.md` | decisions and comments (respect any Amend comment) |
| `outputs/rules.json` | rule IDs for controls and tests |
| `outputs/analytics.json` | metric paths and `{{$.path}}` figures |
| `outputs/history.json` | prior audits, gaps (cite as `[history:ID]`) |
| `outputs/analytics-full/*.csv` | sample sources (read headers and `.head()` only) |

Citation and placeholder syntax is the same as the risk-assessment skill:
`[rule:CPR-NN]`, `[metric:$.path]`, `[history:ID]`, `{{$.path|fmt}}`.

## `outputs/audit-plan.json`

```json
{
  "generated_at": "ISO timestamp",
  "memo": {
    "objective": "what the audit will conclude on, cited",
    "approach": "how: targeted tests over the full population, cited",
    "limitations": "what the data and papers cannot show, cited"
  },
  "risks": [{
    "risk_id": "R-02",
    "controls": [
      {"control_id": "C-02-1", "description": "the control expected to be operating, citing the rule it implements [rule:CPR-11]"}
    ],
    "tests": [{
      "test_id": "T-02-1",
      "control_ids": ["C-02-1"],
      "step": "what the auditor does with each sampled item, citing a rule or a metric",
      "sample": {
        "source": "split_purchases.csv",
        "unit": "group",
        "filter": {"threshold": "$.tests.split_purchases.per_threshold[?threshold==25000].threshold",
                   "tag": "general_procurement"},
        "sort": [{"by": "total_gbp", "desc": true}],
        "n": "auto"
      },
      "pbc": ["Purchase orders and invoices for each sampled window"]
    }]
  }],
  "rules_not_tested": [{"rule_id": "CPR-13", "reason": "electronic tender handling leaves no trace in payment data"}]
}
```

- IDs: `C-<risk number>-<n>` and `T-<risk number>-<n>`, unique.
- **Every control cites ≥1 rule.** Every control is covered by ≥1 test
  (`control_ids`). Every test cites a rule or a metric and has ≥1 PBC item.
- A test that needs no transactions (e.g. requesting the action tracker)
  sets `"sample": null` and gives `"no_sample_reason"`.
- **Every rule in rules.json** is either cited by an in-scope risk (its
  `rule_ids` or text), a control or a test, **or** listed in
  `rules_not_tested` with a reason; never both. Reasons are specific: what
  the payment data cannot show, or why the rule is outside this audit.

## Sample recipes

| Source (analytics-full) | `unit` | One unit is | Useful columns |
| --- | --- | --- | --- |
| `threshold_clustering.csv` | `row` | a payment | `threshold`, `tag`, `Net amount`, `Supplier name` |
| `split_purchases.csv` | `group` | a 30-day window (all its payments) | `threshold`, `tag`, `total_gbp`, `n_payments` |
| `duplicates.csv` | `group` | a repeat-amount group | `tier`, `tag`, `gbp_beyond_first`, `amount` |
| `high_value_suppliers.csv` | `supplier` | a supplier (largest payments) | `dominant_tag`, `match_class`, `annualised estimate` |
| `expired_notice_spend.csv` | `supplier` | a supplier | `dominant_tag`, `total_gbp`, `latest_end_date` |
| `spend_vs_award.csv` | `supplier` | a supplier | `flag`, `ratio`, `notice_id` |
| `near-matches.csv` | `supplier` | a near-match candidate | `match_class`, `annualised_estimate` |
| `spend-clean.csv` | `row` | a payment | `Service`, `Narrative`, `tag`, `Net amount` |

- `filter`: `{"col": value}` (equality), `{"col": [v1, v2]}` (any of),
  `{"col": {">=": v}}` (`>`, `>=`, `<`, `<=`, `!=`). A value may be a
  `$.path` into analytics.json; use that for thresholds rather than typing
  them.
- `sort`: list of `{"by": col, "desc": true}`; ties break on `row_id` /
  `supplier_norm`, so the draw is the same on every run. Sort by the
  indicator's strength (value, ratio, count), highest first: samples are
  **targeted, not random**.
- `unit: supplier` takes the largest `payments_per_supplier` payments
  (default 3) of each supplier from spend-clean.csv.
- `n`: `"auto"` (recommended) or an integer **at least** the size for the
  risk's score:

  | Register score | Units per test |
  | --- | --- |
  | 15+ | 25 |
  | 8–14 | 15 |
  | 4–7 | 10 |
  | 1–3 | 5 |

  If the filtered population is smaller, all of it is taken.
- Placements and grants (`tag` care_or_education_placement / grant) may be
  exempt from competition; filter to `general_procurement` unless the test is
  specifically about them.
- Never sample on supplier-level "no notice found" below the publication
  threshold, and say in the step that a notice gap is checked against the
  council's register.

The builder verifies every drawn transaction exists in `spend-clean.csv`
(and that amounts and suppliers agree for row samples), and writes
`outputs/samples/<test_id>.csv`.

## PBC items

One short request per document type the test step needs ("Purchase orders
and invoices for each sampled window", "The council's contract register
with values and end dates"). Reuse the exact wording across tests when the
request is the same: the PBC list at the end of `audit-program.md` merges
identical items.

## What the builder writes

- `planning-memo.md`: basis (register revision), objective, scope table with
  decisions, approach, sampling (sizes, populations, transactions, value),
  limitations, sources.
- `risk-control-matrix.md`: risk → control → rules → tests, then rule
  coverage with every not-tested rule and its reason.
- `audit-program.md`: per risk, per test: step, sample recipe in words with
  its population and file, PBC; ends with the consolidated **PBC list**.
- `samples/T-*.csv`: the drawn transactions (spend-clean columns + test,
  risk and sample unit).
- `pack-figures.json`: `computed` (every figure the builder calculated:
  sizes, populations, counts, £), `from_analytics` (every analytics value it
  printed) and `from_register` (L, I, score), for the QA number check.

## Language

Fails the build: a figure typed in prose (use placeholders), an unresolved
citation, and accusatory words (fraud, corrupt, theft, deliberate,
dishonest, collusion, misconduct…; "anti-fraud" is allowed as a name).
Write tests as "establish whether", "confirm", "trace", never "prove"
or "detect wrongdoing". Every document carries the indicator disclaimer.

## Process

1. `--gate`. If closed, stop and report why.
2. Read the approved risks (focus, rules, evidence, any Amend comments) and
   the headers of the source files you will sample.
3. Write `outputs/audit-plan.json`.
4. Build. Fix every `FAIL` in the plan (never by editing outputs, inputs or
   the builder) and rebuild until it passes.
5. Report: risks in scope, tests and sample sizes, rules not tested, PBC
   count, the builder's final lines.
