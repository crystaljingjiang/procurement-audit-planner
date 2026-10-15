# Team 9

# Procurement Audit Planner: West Berkshire Council

An agentic system, built on Claude Code, that plans an internal audit of
procurement for West Berkshire Council from the council's public data. It
turns the Contract Procedure Rules into testable rules, analyses the full
spend population against them, folds in past audit history, rates the risks
on the council's own scale, and produces a cross-checked audit planning pack
for a human auditor to approve and sign off.

We completed all 27 steps of the
[Procurement Audit Planner guide](https://procurement-audit-planner.vercel.app/).

Three principles run through every component:

- **The LLM reads and judges; Python computes every number.** Agents write
  judgments and citations; scripts and builders produce every figure.
- **Everything is traceable.** Quotes are checked against the source PDFs,
  every metric comes from a named script, and every rating cites a rule, a
  metric or a prior audit finding.
- **Indicators, not accusations.** Outputs describe risk indicators to
  investigate, never wrongdoing by the council, a department or a supplier.

`CLAUDE.md` holds the full specification.

---

## Skills (`.claude/skills/`)

| Skill | Used by | What it does |
| --- | --- | --- |
| **`extract-rules`** | The human, as `/extract-rules` | Reads `data/contract-rules.pdf` and writes `outputs/rules.json`: one entry per testable rule, with clause reference, thresholds (GBP integers), required action, approver and a verbatim quote. The anti-splitting rule is tagged `anti-avoidance`, and ambiguous clauses go in an `excluded` list with a reason. `verify_quotes.py` confirms every quote is in the PDF. |
| **`risk-assessment`** | `risk-assessor` sub-agent | Sets the method for rating risks on the council's likelihood × impact scale (taken from the Risk Management Strategy 2024–27). The agent writes judgments with `[rule:…]`, `[metric:…]` and `[history:…]` citations to `outputs/risk-ratings.json`. `build_register.py` resolves each citation, fills figures from `analytics.json`, checks likelihood against the rubric, computes scores and bands, and writes `risk-register.md`, `auditor-comments.md` and `risk-register.state.json`. A risk with no citation is dropped. Tests are in `tests/`. |
| **`audit-program`** | `planner` teammate | Turns the auditor-approved risks into an audit program. The planner writes controls, test steps, sample recipes, PBC (prepared-by-client) items and memo text to `outputs/audit-plan.json`. `build_pack.py` checks the approval gate, resolves citations, draws and verifies every sample, checks rule and control coverage, and writes `planning-memo.md`, `risk-control-matrix.md`, `audit-program.md`, `samples/T-*.csv` and `pack-figures.json`. Tests are in `tests/`. |

## Agents (`.claude/agents/`)

### Sub-agents (Phases 1–2)

| Agent | Reads | Writes | What it does |
| --- | --- | --- | --- |
| **`spend-analyst`** | `outputs/rules.json`, `data/spend/*.xlsx`, `data/contracts.csv` | `scripts/clean.py`, `scripts/analyse.py`, `scripts/selfcheck.py`; `outputs/analytics.json`, `outputs/analytics-full/` | Cleans the monthly spend workbooks and the Contracts Finder export, then runs six tests with thresholds taken from `rules.json`: threshold clustering, split purchases, off-contract spend (suppliers above the publication threshold only), duplicates, spend after a notice expired, and spend above the award value. It reads only aggregates and top-N lists. |
| **`findings-analyst`** | `data/committee/*.pdf` | `outputs/history.json` (checked by `scripts/verify_history.py`) | Records past audits and assurance opinions, follow-ups, risk themes, gaps and the council's risk scoring method. Every item has its source file, page and a verbatim quote. It records only and never scores. |
| **`risk-assessor`** | `rules.json`, `analytics.json`, `history.json`; on a revision, `auditor-comments.md` | `outputs/risk-ratings.json` (then runs `build_register.py`) | Follows the `risk-assessment` skill to rate risks with citations, and re-runs the builder until there are no failures or warnings. It recommends scope but never approves it. After the auditor's decisions it issues the next revision. |

### Agent team (Phase 3)

Turned on by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in
`.claude/settings.json`. The teammates message each other directly; the
lead does not relay between them.

| Member | Owns | Role |
| --- | --- | --- |
| **Lead** (main Claude Code session) | none | Runs the gate check (`build_pack.py --gate`), spawns the three teammates by name, answers questions, shuts them down after `PLANNER DONE`, `CHALLENGER DONE` and `QA DONE`, and reports to the auditor in under 300 words. |
| **`planner`** | `outputs/audit-plan.json` | Uses the `audit-program` skill to plan exactly the approved risks, runs `build_pack.py` until it passes, and announces `PACK READY vN`. It answers challenges and fixes QA failures, but never re-rates a risk or changes scope. |
| **`challenger`** | `outputs/challenges.md` | Reviews the pack against the register, the ratings, analytics and history. It sends cited `CHALLENGE #n` messages to the planner (at most two rounds), for example a low rating with a strong data signal or a repeat finding left out of scope. Items that need the auditor's call are marked *for the auditor*. |
| **`qa-reviewer`** | `outputs/review.md` | Runs `scripts/checks/run_checks.py` (quotes, numbers, trace, samples) on each pack version and reports `QA vN PASS/FAIL`. It then writes `review.md` with the results exactly as printed, the verdict `READY FOR SIGN-OFF` or `BLOCKED`, and the auditor's sign-off block. It never softens a failure. |

Each agent keeps lessons on how to do its job (never evidence) in
`.claude/agent-memory/<agent>/`.

---

## How it works, stage by stage

```
 data/contract-rules.pdf ──(1) /extract-rules──▶ outputs/rules.json
                                                     │
              ┌──────────────────────────────────────┴───────────────┐
 (2a) spend-analyst                                    (2b) findings-analyst
 data/spend/*.xlsx + data/contracts.csv                data/committee/*.pdf
              │                                                      │
 outputs/analytics.json + analytics-full/              outputs/history.json
              └──────────────────────────────┬───────────────────────┘
                                 (3) risk-assessor + build_register.py
                                             │
                     risk-register.md + auditor-comments.md
                                             │
                (4) HUMAN GATE 1: auditor approves / amends / rejects
                       (rejections or amendments go back to step 3)
                                             │
             (5) Agent team: planner ⇄ challenger, planner ⇄ qa-reviewer
                                             │
          planning-memo.md, risk-control-matrix.md, audit-program.md,
                     samples/, challenges.md, review.md
                                             │
                (6) HUMAN GATE 2: auditor signs off in review.md
```

| # | Stage | Who | Reads | Writes |
| --- | --- | --- | --- | --- |
| 1 | Extract rules | Human runs `/extract-rules` | `data/contract-rules.pdf` | `outputs/rules.json` |
| 2a | Spend analytics | `spend-analyst` | `outputs/rules.json`, `data/spend/*.xlsx`, `data/contracts.csv` | `scripts/*.py`, `outputs/analytics.json`, `outputs/analytics-full/*.csv` (cleaned spend, exclusions, flagged lists, cleaning log) |
| 2b | Audit history | `findings-analyst` | `data/committee/*.pdf` | `outputs/history.json`, `outputs/committee-text/` |
| 3 | Risk register | `risk-assessor` + `build_register.py` | `rules.json`, `analytics.json`, `history.json` | `outputs/risk-ratings.json`, `risk-register.md`, `risk-register.state.json`, `auditor-comments.md` |
| 4 | **Human gate 1: approve risks and scope** | Auditor | `risk-register.md` | `auditor-comments.md` (Approve / Amend / Reject on every risk). The `risk-assessor` then issues a revision that applies the decisions. |
| 5 | Planning pack | Lead → `planner`, `challenger`, `qa-reviewer` | Register revision, `auditor-comments.md`, `risk-ratings.json`, `rules.json`, `analytics.json`, `history.json`, `analytics-full/` | `audit-plan.json`, `planning-memo.md`, `risk-control-matrix.md`, `audit-program.md`, `samples/T-*.csv`, `pack-figures.json`, `challenges.md`, `review.md` |
| 6 | **Human gate 2: sign-off** | Auditor | The full pack, `challenges.md`, `review.md` | Sign-off block at the end of `outputs/review.md` |

The planner cannot start until gate 1 is closed: `build_pack.py --gate`
passes only when the register is a revision, every risk has a decision, and
neither the register nor the ratings have changed since. A `BLOCKED` QA
verdict sends the pack back to the team, not to the auditor.

---

## Getting the data

All inputs are public and go into `data/`, which is read-only. The copies
we used are already committed. To refresh them:

| File(s) | Where to get it |
| --- | --- |
| `data/contract-rules.pdf` | West Berkshire Council constitution, Part 8 *Contract Procedure Rules* (Sept 2025), on [westberks.gov.uk](https://www.westberks.gov.uk) |
| `data/spend/*.xlsx` | The council's *Expenditure over £500* page on [westberks.gov.uk](https://www.westberks.gov.uk). Download the monthly workbooks (sheet "Data to publish"); we used 2026 periods P02–P04 |
| `data/contracts.csv` | [Contracts Finder](https://www.contractsfinder.service.gov.uk) search for the quoted phrase `"West Berkshire Council"`, stage *Awarded*, status Open and Closed, published 2021 to today, no value filter, exported as CSV |
| `data/committee/*.pdf` | Governance Committee papers on [decisionmaking.westberks.gov.uk](https://decisionmaking.westberks.gov.uk): internal audit completed-work appendices (2024/25 annual, 2025/26 Q3), Internal Audit Plan 2025–28, Risk Management Strategy 2024–27 |

The Strategic Risk Register is exempt and not public. The scoring method
comes from the Risk Management Strategy instead.

## Running it

**Prerequisites:** [Claude Code](https://claude.com/claude-code), Python 3.10+,
and `pdftotext` (`brew install poppler`).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # pandas, openpyxl
```

Then, in a Claude Code session in the repo root:

1. **Rules:** run `/extract-rules`. Spot-check a few quotes in
   `outputs/rules.json`.
2. **Analysis:** ask Claude to run the `spend-analyst` and
   `findings-analyst` sub-agents. They are independent and can run in
   parallel.
3. **Register:** ask Claude to run the `risk-assessor`. Review
   `outputs/risk-register.md`.
4. **Gate 1:** fill in Decision (and Comment where needed) for every row of
   `outputs/auditor-comments.md`, then run the `risk-assessor` again to
   issue the revision.
5. **Pack:** ask the lead to run the agent team (planner, challenger,
   qa-reviewer) as described in `CLAUDE.md`. It runs the gate check first.
6. **Gate 2:** read the pack and `outputs/challenges.md`, then complete the
   sign-off block at the end of `outputs/review.md`.

Useful commands to run directly:

```bash
.venv/bin/python scripts/clean.py && .venv/bin/python scripts/analyse.py   # rebuild analytics
.venv/bin/python scripts/selfcheck.py                                      # re-derive one item per test
.venv/bin/python scripts/verify_history.py                                 # verify history.json quotes
.venv/bin/python .claude/skills/risk-assessment/build_register.py          # rebuild the register
.venv/bin/python .claude/skills/audit-program/build_pack.py --gate         # check approval gate
.venv/bin/python .claude/skills/audit-program/build_pack.py                # rebuild the pack
.venv/bin/python scripts/checks/run_checks.py --verbose                    # QA verdict
```

Tests (plain Python scripts, no test runner needed):

```bash
.venv/bin/python .claude/skills/risk-assessment/tests/test_build_register.py
.venv/bin/python .claude/skills/audit-program/tests/test_build_pack.py
.venv/bin/python scripts/tests/test_verify_history.py
.venv/bin/python scripts/checks/tests/test_checks.py
```

## Current outputs

`outputs/` holds a complete run: 7 risks in revision 1 of the register, all
approved by the auditor; the planning memo, risk-control matrix and audit
program with 8 sample files; and a QA verdict of **READY FOR SIGN-OFF** in
`outputs/review.md`.
