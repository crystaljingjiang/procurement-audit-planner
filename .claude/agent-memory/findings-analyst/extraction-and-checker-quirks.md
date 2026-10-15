---
name: extraction-and-checker-quirks
description: How to rebuild committee-paper tables from pdftotext -layout and shape history.json items so verify_history.py passes without weakening quotes
metadata:
  type: feedback
---

Method lessons from the 2026-10-14 run (no paper content here; always re-read the current PDFs).

**Build history.json with a script, not by hand.** Write a builder in the scratchpad that pulls quotes
straight from outputs/committee-text/*.layout.txt (find the line containing a substring, collapse
whitespace). Copy-exact by construction; typos and odd dashes survive.
**Why:** hand-typed fragments are error-prone; the checker forgives only whitespace/glyphs.
**How to apply:** helper `L(file, page, substring)` -> collapsed layout line; split pages on `\f`.

**Table rebuilding**
- Fixed column slicing works only for left-aligned tables (e.g. the impact table). Centred-cell tables
  (e.g. the appetite table) need token assignment: split each line on runs of 2+ spaces, assign each
  token to the nearest header-column centre. Print the result and eyeball it before using it.
- Cells can straddle a page break; record each page's part as its own evidence object.

**Checker behaviour (scripts/verify_history.py)**
- `cells`: the first TWO words of each cell must be inside the item's row `quote`. A wrapped cell whose
  2nd word is on the next layout line fails. Fix: leave it out of `cells` and add a nested object
  `{source, quote_fragments:[line1, line2]}` (e.g. `opinion_report_cell`). Nested dicts with
  `source`/`quote_fragments` are verified too.
- Never name a nested list `cells` unless it is row cells of that item; it triggers the CELL check.
- `quote_fragments` with 2+ entries must total >= 8 chars (e.g. a number + short label fails); a single
  fragment has no length check. Fragments must be <= 4 lines apart and within 6 columns of the first.
- Any key ending in `quote` is checked as a quote (>= 8 chars) on the stated page; use this for
  secondary quotes (`level_quote`, `scores_quote`).
- Items outside `scoring_method` must not carry score/impact/likelihood/rating/rag/priority keys.
- Extra top-level sections (e.g. opinion basis, audit-plan method) are walked and verified like others.

**Page offsets:** the risk strategy's printed footer numbers matched physical pages on this run; the
strategy's Appendix 1 restarts paragraph numbering (cite as "Appendix 1 ... 6.x").
