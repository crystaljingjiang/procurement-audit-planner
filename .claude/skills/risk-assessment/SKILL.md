---
name: risk-assessment
description: Rate procurement risks on the council's likelihood × impact method. The agent writes judgments with citations to outputs/risk-ratings.json; build_register.py resolves every citation and figure, computes scores and bands, and renders outputs/risk-register.md and the auditor's decision template. Loaded by the risk-assessor.
---

# risk-assessment

You judge; the builder computes. You write **judgments only** to
`outputs/risk-ratings.json`: which risks, which likelihood and impact level,
why, with citations. `build_register.py` (next to this file) resolves every
citation, fills every figure from analytics.json, checks your likelihood
against the rubric below, computes score, matrix label and band from the
council's method in history.json, and writes:

- `outputs/risk-register.md`: the register, ending with "Auditor decisions";
- `outputs/auditor-comments.md`: one row per rated risk with blank Decision
  and Comment cells (decisions already in the file are kept on rewrite);
- `outputs/risk-register.state.json`: what the next revision and the
  planning gate compare against. Never edit it.

```bash
.venv/bin/python .claude/skills/risk-assessment/build_register.py
```

Exit 0 means the register was written. Read the `DROPPED` and `WARN` lines:
a dropped risk is not in the register. Fix it or withdraw it, then rebuild.
Exit 1 means nothing was written; the message says why.

## Inputs

| File | What you cite from it |
| --- | --- |
| `outputs/rules.json` | `rule_id` (CPR-01…) |
| `outputs/analytics.json` | metric paths (see syntax) |
| `outputs/history.json` | any `id`: audits `AUD-*`, follow-ups `FU-*`, themes `RT-*`, scoring entries `LIK-*`, `IMP-n-DIM`, `MX-I*`, `BAND-*`, `ESC-*`, discrepancies `DISC-*`, gaps `GAP-*` |
| `outputs/auditor-comments.md` | on a revision: the auditor's decisions |

Inspect analytics.json with `jq`/`python` key listings, not by printing it
whole. If any input is missing, stop and report.

## Citation and figure syntax

- `[rule:CPR-11]`, `[history:AUD-12]`, `[metric:$.path]`: citation tags.
  Every justification needs at least one that resolves.
- `{{$.path}}` or `{{$.path|fmt}}`: a figure, filled from analytics.json.
  `fmt` is `gbp` (£1,234), `gbp2` (£1,234.56), `int`, `num` (default),
  `ratio`, `raw`. **Never type a figure in prose.** Thresholds, counts, £,
  percentages and day windows are all placeholders. The builder warns on
  any digit left in prose outside IDs.
- Paths: `$.a.b`, `['key with space']`, `[0]`, and filters
  `[?key==value]` that must match exactly one element. Use filters, not
  indexes, for lists. Examples that exist today:
  - `$.tests.split_purchases.per_threshold[?threshold==25000].headline_general_procurement.windows`
  - `$.tests.threshold_clustering.per_threshold[?threshold==25000].band_by_tag.general_procurement.n`
  - `$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.gbp_beyond_first`
  - `$.tests.off_contract.headline_general_procurement_no_notice_found.annualised_estimate_gbp`
  - `$.tests.spend_vs_award.flagged`, `$.tests.expired_notice_spend.suppliers`
  - `$.contracts.register_present`, `$.population.months_covered`

## `outputs/risk-ratings.json`

```json
{
  "generated_at": "ISO timestamp",
  "revision": null,
  "risks": [{
    "risk_id": "R-01",
    "title": "short indicator statement, figures as placeholders",
    "theme": "split purchases",
    "status": "proposed",
    "description": "one or two sentences, indicator language, cited",
    "rule_ids": ["CPR-11", "CPR-56"],
    "likelihood": {
      "base_score": 3,
      "rubric_level": "L3",
      "justification": "why, with [metric:…] and {{…}}",
      "signals": [{"metric": "$.path", "op": ">", "than": 0},
                  {"metric": "$.path", "op": ">", "than": "$.other.path"}],
      "uplift": null
    },
    "impact": {
      "score": 5,
      "dimension": "DIM-FIN",
      "financial_basis": "$.path to the £ value exposed (DIM-FIN only)",
      "justification": "why, citing [history:IMP-5-FIN]"
    },
    "evidence": ["[metric:…]", "[history:…]"],
    "proposed_focus": "what fieldwork should test, cited",
    "proposed_scope": "in",
    "scope_reason": "one line, cited"
  }]
}
```

`uplift`, when used: `{"history_id": "AUD-12", "justification": "…[history:AUD-12]…"}`.
`dimension` is one of `DIM-FIN`, `DIM-PER`, `DIM-AST`, `DIM-REP`, `DIM-CMP`.
Risk IDs are `R-01`, `R-02`, … and never reused or renumbered.

## Which risks to rate

One risk per distinct indicator theme with evidence: threshold clustering
per competition-triggering threshold, split purchases, high-value suppliers
with no notice found, duplicates, expired-notice spend, spend beyond award,
plus any theme from history.json that bears on procurement (e.g. a
procurement-related audit, a gap such as the missing action tracker).
Each rule in rules.json of type `threshold`, `anti-avoidance` or `approver`
with a spend-data test should trace to at least one risk; say in
`scope_reason` when a rule has no risk because the data cannot test it.

## Likelihood rubric

Likelihood is the chance, within 12 months, that the indicator reflects
real non-compliance (the council's own scale: LIK-1 Rare <2% … LIK-5 Certain
100%). Pick the **highest level whose conditions all hold**, and state the
signals that prove them. The builder evaluates every signal; a signal that
does not hold, or a level whose structural conditions are missing, drops
the risk.

| Level | Conditions (all must hold) |
| --- | --- |
| L1 Rare | No data indicator for the theme, or the test was skipped; only a rule or a gap is cited |
| L2 Unlikely | ≥1 signal holds (indicator present), but only outside general procurement (placements, grants, premises), **or** it does not beat its comparator |
| L3 Likely | ≥1 holding signal on the `general_procurement` population; for `threshold_clustering`, a holding signal that the band beats its comparator (`band_count > comparator_count`, same threshold) |
| L4 Almost certain | L3, plus holding signals from **two different tests** pointing at the same theme (e.g. clustering and split purchases at the same threshold) |
| L5 Certain | L4, plus a history item recording that the condition has already occurred (e.g. an audit finding of non-compliance on this theme). Not available while history.json has no action tracker (see its gaps) |

Then:
- **Repeat finding (+1, cap 5).** Only when an audit or follow-up on the
  same theme has an **adverse** opinion: Limited Assurance, No Assurance,
  Weak, Unsatisfactory. Put it in `uplift` with the `AUD-`/`FU-` id; the
  builder checks the opinion and states the uplift on the risk. A
  Reasonable or Substantial opinion is coverage, not a repeat finding; cite
  it in the justification, never as uplift. The theme match is your
  judgment: name the shared theme in the uplift justification.
- Placement and grant spend may be exempt from competition (App C row F;
  clause 1.6.2). Never rate above L2 on those populations alone.
- "No notice found" is not evidence of off-contract spend. Off-contract
  risk is at most L3 while `$.contracts.register_present` is false; say so.
- Use the same conditions for every risk. Do not adjust for how serious a
  theme feels; that belongs in impact.

## Impact

Use the council's Table 1 (history.json `impact_scale`). Choose the single
dimension that best describes the consequence and cite its definition
`[history:IMP-{score}-{DIM}]`; the builder requires that citation.

- **DIM-FIN:** give `financial_basis`, the path to the £ value exposed to
  the indicator (flagged window value, value beyond first payment, annualised
  estimate). The builder maps it to the council's £ band and drops the risk
  if your score differs. It is value exposed, not a loss; say so.
- **DIM-CMP / DIM-REP:** for rules breaches with little £ exposure (e.g.
  approvals, publication). Justify against the printed wording.
- Never use DIM-PER or DIM-AST for procurement indicators unless the
  evidence is about people or assets.

## What the builder decides, and the conflicts it marks

It computes score = L × I and checks it against Figure 1's printed scores;
the band and RAG come from Table 4, and the Figure 1 cell name is shown as
"matrix label". Where the council's method contradicts itself it uses one
value, marks the other and names the `DISC-*` in the register header:

- band names (Figure 1 'High' vs Table 4 'Medium - High'): Table 4 used;
- Corporate Risk Register entry (Table 4 Extreme 15-25 vs Figure 4 'Score 9
  or above'): Table 4 used; risks at 9-12 are marked ‡;
- financial £ ranges sharing end points and % ranges overlapping: £ ranges
  used, a value on a shared end point takes the higher level, % not used;
- 'Medium (2)' in §4.3 vs Medium = 3 in Table 1: Table 1 used.

Any other discrepancy touching an input it reads is listed as **not
resolved**. Do not work round any of these in your ratings. If
history.json has no usable method, the builder uses 1-5 Very low…Very high
and says so in the header.

## Process

1. Read the inputs (keys and aggregates only). List the candidate themes and
   the metric paths you will cite.
2. Write `outputs/risk-ratings.json`.
3. Run the builder. Fix every `DROPPED` risk (resolvable citations, rubric,
   £ band) or remove it with a line in your report; fix every typed-figure
   `WARN`. Rebuild until no risk is dropped unintentionally.
4. Report: the summary table (copied from the register), dropped or
   withdrawn risks, conflicts marked, and that decisions are awaited in
   `outputs/auditor-comments.md`.

Do not edit `risk-register.md`, `auditor-comments.md` (except as the auditor
asks) or the state file by hand; re-run the builder.

## Revisions (after the auditor's decisions)

The auditor fills Decision (Approve / Amend / Reject) and Comment per row,
and may add lines under "Other instructions". Then:

1. Read `outputs/auditor-comments.md`. For each pending decision:
   - **Approve:** change nothing on that risk.
   - **Amend:** make exactly the change asked for, no more.
   - **Reject:** set `"status": "rejected"`. Never delete a risk.
   - A new risk only when an "Other instructions" line asks for it. Give it
     the next unused id.
2. Add the revision block:
   ```json
   "revision": {"number": 1, "summary": "one line",
     "changes": [{"risk_id": "R-03", "decision": "Amend", "change": "likelihood 3 → 2"},
                 {"risk_id": "R-07", "change": "added", "requested_in": "exact line from Other instructions"}]}
   ```
   `number` is the previous revision + 1 (the first revision is 1).
3. Run the builder. It fails if a risk is undecided, a decision was left
   unapplied, something changed that the auditor did not ask for (likelihood,
   uplift, impact, dimension, scope, status, title, focus or the set of
   citations), a change is not listed, or a listed change has no decision.
   It marks every Amend/Reject as an **auditor override** on the risk. An
   amended rating that departs from the rubric is kept with a build note,
   not dropped, because the auditor decided it.
4. Report what changed, in one line per risk.

## Language

Indicators to investigate, never wrongdoing. Name patterns ("payments within
10% below the threshold"), not intentions ("avoiding competition"). No
supplier, officer or service is accused of anything.
