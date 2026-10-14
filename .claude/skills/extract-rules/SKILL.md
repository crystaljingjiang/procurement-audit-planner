---
name: extract-rules
description: Convert West Berkshire Council's Contract Procedure Rules (data/contract-rules.pdf) into outputs/rules.json, with one entry per testable rule with clause, page, thresholds as printed and a verbatim quote, plus parameters for named-but-unvalued thresholds, an excluded list covering every other clause, and notes on contradictions. Verified by verify_quotes.py. Use when the human runs /extract-rules or rules.json must be rebuilt after the PDF changes.
---

# extract-rules

Turn `data/contract-rules.pdf` into `outputs/rules.json`. You read and judge;
`verify_quotes.py` (next to this file) proves every quote, ID and clause.
Never guess, never fill a value from memory, never edit the PDF.

## 0. Preconditions: stop and report if any fail

- `data/contract-rules.pdf` exists and `pdfinfo` reads it.
- `pdftotext` is on PATH (poppler).
- `.venv/bin/python` exists.

## 1. Read the document

```bash
pdftotext -layout data/contract-rules.pdf "$TMP/rules-layout.txt"   # read clauses
pdftotext        data/contract-rules.pdf "$TMP/rules-plain.txt"    # read tables
.venv/bin/python .claude/skills/extract-rules/verify_quotes.py --list-clauses
```

Use a scratch directory for `$TMP`, not `outputs/`. Pages are separated by
form feeds (`\f`). Page N = the Nth `\f`-separated block = the printed page
number in the footer.

Structure of the document (Part 8 of the constitution, file printed as "Part []"):

| Pages | Content | Clause IDs to use |
| --- | --- | --- |
| 1–10 | Numbered sections 1–11; clauses like `6.16`, sub-items like `7.4.2`, `10.7.9.1` | the number as printed |
| 11 | Appendix A: delegated authority by Total Contract Value (4 unlabelled bands) | `AppA-1` … `AppA-4`, top to bottom |
| 12–13 | Appendix B: financial thresholds and mandatory processes (rows A, B1, B2, C, D), footnotes `*`–`****` on p13 | `AppB-A`, `AppB-B1`, … ; footnotes `AppB-notes` |
| 14–15 | Appendix C: exclusions from competition (rows A–F; F is on p15); closing sentence on p15 | `AppC-A` … `AppC-F`; closing sentence `AppC-closing` |

Reading traps in the extracted text:
- **Layout mode** is best for clause text, but splits table cells across columns.
  **Plain mode** keeps each table cell together (band text then procedure text),
  so quote table rows from plain mode.
- Bullets come out as U+F0B7 (``); footers read `$3inav0bz.docx` plus page number.
  Neither belongs in a quote.
- Section headings (`6 Buying / procuring …`, `Advertising`) are not clauses.
  A numbered line holding only a heading (e.g. a clause number followed by a title
  and no requirement) is still a clause: exclude it with a reason.

## 2. Classify every clause

`--list-clauses` prints the inventory the verifier will enforce. Each item goes
to **rules** (one or more entries) or **excluded** (exactly one entry). Appendix A
rows, `AppB-notes` and `AppC-closing` are not auto-detected: add them yourself.

A clause is a **testable rule** if an auditor could test compliance against it:
it sets a value threshold, a required action (quotes, tender, advert, written
report, record kept, approval obtained), or an approver. Split a clause into
several rules when it holds several distinct tests (e.g. an Appendix B row's
award procedure and its advertising requirement; each band of 7.4).
For a parent clause whose obligations sit in its sub-items, put the rules on the
sub-items and exclude the parent ("lead-in to 7.4.1–7.4.3").

**Exclude** with a one-line reason (≤200 characters, no newline): definitions,
statutory background, purpose statements, lists of examples, cross-references
with no obligation of their own, headings, duties too vague to test ("should
consider"), sealing/signature formalities outside procurement. If you cannot
decide whether a clause is testable, exclude it, say why, and add a note.

## 3. Fill each rule

| Field | Rule |
| --- | --- |
| `rule_id` | `CPR-01`, `CPR-02`, … in document order, no gaps |
| `clause` | clause ID as in step 1 |
| `page` | page where the quote is; add `page_end` only if the quote runs onto the next page |
| `type` | one of `procurement_route` (quotes/tender by value), `advertising`, `approval` (who authorises), `exception` (waivers, Appendix C exclusions), `documentation` (reports, records, register), `contract_terms`, `anti-avoidance` (no splitting/disaggregation, aggregation) |
| `scope` | list from `goods_services`, `works`, `concession`, `light_touch`, or `["all"]` when the text does not limit it |
| `condition` | plain-English trigger, e.g. "Goods & services, £25,000 or more and below the Threshold" |
| `threshold_low` / `threshold_high` | GBP integer **as printed**, or null if absent/open-ended |
| `threshold_*_inclusive` | `true`/`false` from the wording (table below); null when that bound is null |
| `threshold_*_param` | parameter key when the bound is a named threshold ("the Threshold"); then the integer stays null |
| `threshold_*_text` | the bound's words exactly as printed, e.g. `"less than £25,000"`; must be inside the quote |
| `required_action` | what must be done, or null |
| `approver` | who must approve/decide, exactly as the PDF names the role, or null |
| `evidence_source` | where an auditor would find evidence, from: `spend_data`, `contract_notices` (both in `data/`), `procurement_portal`, `approval_records`, `decision_records`, `waiver_records`, `contract_file`, `contract_register` |
| `verbatim_quote` | copy-exact text from the stated page. Join non-adjacent parts with ` [...] ` (each part must still be exact and in order). Do not fix typos or grammar |

Bound wording → inclusive flag:

| Printed | Bound | Inclusive |
| --- | --- | --- |
| "£X or more", "at least £X", "from £X" | low | true |
| "above £X", "over £X", "more than £X", "exceeds £X", "in excess of £X" | low | false |
| "less than £X", "below £X", "under £X" | high | false |
| "up to £X", "not exceeding £X" | high | true (add a note if the neighbouring band uses the same X) |

Amounts printed with pence (e.g. "£24,999.99"): `threshold_*` must be an integer,
so use the exactly equivalent whole-pound bound ("more than £24,999.99" →
`25000`, inclusive `true`), keep the printed words in `threshold_*_text`, and add
a note. If no exact equivalent exists, set the bound to null and add a note.

## 4. Parameters (named thresholds with no printed value)

Where the PDF names a threshold without giving its amount (e.g. "the Threshold",
"the relevant Threshold", "the Threshold for Goods & Services"), declare it once
at top level and point to it from the rule:

```json
"parameters": {
  "THRESHOLD_GOODS_SERVICES": {
    "value": null,
    "printed_as": "<the words exactly as printed>",
    "defined_in": "<clause that defines or first uses it>",
    "page": "<integer page where printed_as appears>",
    "note": "<where the PDF says the value is published>"
  }
}
```

`value` is ALWAYS null. Never insert the statutory figure from memory, even if
known; the auditor supplies it later. `printed_as` must appear verbatim on `page`.
When the PDF says only "the relevant Threshold" and the category depends on the
contract type, use one parameter per category the rule's scope covers, split
into one rule per category if needed, and add a note on the ambiguity.

## 5. Notes: contradictions and drafting gaps

Add a note for anything an auditor should know before relying on a rule:
bands that overlap or leave a gap between Appendix A, Appendix B and section 7;
value basis conflicts (e.g. VAT inclusive vs exclusive); undefined terms or
roles; placeholders (`Part []`, `Parts []`); broken numbering or a clause that
reads as part of another; cross-references to the wrong clause; pence amounts;
thresholds published only outside the PDF. One note per issue:
`{"clauses": ["6.15", "AppB-A"], "page": 5, "issue": "one or two sentences"}`.
Notes describe the document, never the council's conduct.

## 6. Output and verify

Write `outputs/rules.json`:

```json
{
  "source": {"file": "data/contract-rules.pdf", "pages": 15, "title_as_printed": "Contract Rules", "extracted": "YYYY-MM-DD"},
  "parameters": { … },
  "rules": [ … ],
  "excluded": [ {"clause": "1.1", "page": 1, "reason": "Statutory background (s.135 LGA 1972); no obligation"} ],
  "notes": [ … ]
}
```

Then run, and fix every ERROR until it prints `RESULT: PASS`:

```bash
.venv/bin/python .claude/skills/extract-rules/verify_quotes.py \
  --pdf data/contract-rules.pdf --rules outputs/rules.json
```

Fix errors by correcting rules.json against the PDF, never by loosening a
quote or by deleting a rule to silence a check. If an error cannot be fixed
(e.g. text unextractable), stop and report it.

## 7. Report to the human (under 200 words)

Counts (rules by type, excluded, notes), the parameters that need a value from
the auditor, the anti-avoidance rule ID(s), the most important notes, and the
verifier result line. Do not paste rules.json.
