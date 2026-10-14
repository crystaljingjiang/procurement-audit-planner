#!/usr/bin/env python3
"""Verify outputs/rules.json against the Contract Procedure Rules PDF.

Checks:
  1. schema: top-level keys, rule fields, types, enums, threshold logic
  2. rule IDs: CPR-01, CPR-02, ... sequential with no gaps
  3. parameters: every *_param a rule uses is declared; every declared
     parameter has value null and its printed_as text is on its page
  4. quotes: every verbatim_quote (and each " [...] " segment) appears on
     its stated page, in pdftotext plain OR -layout text
  5. coverage: every numbered clause and appendix row label found in the PDF
     appears in rules or excluded; nothing references a clause not in the PDF

Usage:
  verify_quotes.py [--pdf data/contract-rules.pdf] [--rules outputs/rules.json]
  verify_quotes.py --list-clauses      # print clause inventory and exit

Exit 0 = all checks pass (warnings allowed); 1 = errors; 2 = cannot run.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata

RULE_TYPES = {"procurement_route", "advertising", "approval", "exception",
              "documentation", "contract_terms", "anti-avoidance"}
SCOPES = {"all", "goods_services", "works", "concession", "light_touch"}
EVIDENCE = {"spend_data", "contract_notices", "procurement_portal",
            "approval_records", "decision_records", "waiver_records",
            "contract_file", "contract_register"}
RULE_KEYS = {"rule_id", "clause", "page", "type", "scope", "condition",
             "threshold_low", "threshold_low_inclusive", "threshold_low_param",
             "threshold_low_text", "threshold_high", "threshold_high_inclusive",
             "threshold_high_param", "threshold_high_text", "required_action",
             "approver", "evidence_source", "verbatim_quote"}
OPTIONAL_RULE_KEYS = {"page_end"}
TOP_KEYS = {"source", "parameters", "rules", "excluded", "notes"}
ELISION = " [...] "
CLAUSE_RE = re.compile(r"^\d+(\.\d+)+$")
APPENDIX_ID_RE = re.compile(r"^App([A-Z])-[A-Za-z0-9]+$")
APPENDIX_PAGE_RE = re.compile(r"Contract Rules - Appendix ([A-Z])")
ROW_LABEL_RE = re.compile(r"^[A-Z]\d?$")
PARAM_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def normalise(text):
    """Make PDF text and quotes comparable without changing wording."""
    text = unicodedata.normalize("NFKC", text)
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'),
                 ("”", '"'), ("–", "-"), ("—", "-"),
                 (" ", " "), ("", " "), ("•", " ")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def pdf_pages(pdf, layout):
    cmd = ["pdftotext"] + (["-layout"] if layout else []) + [pdf, "-"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def clause_inventory(plain_pages):
    """Numbered clauses and appendix row labels, as printed on their own line."""
    found = {}
    appendix = None
    for no, page in enumerate(plain_pages, 1):
        m = APPENDIX_PAGE_RE.search(page)
        if m:
            appendix = m.group(1)
        for line in page.splitlines():
            s = line.strip()
            if appendix is None and CLAUSE_RE.match(s):
                found.setdefault(s, no)
            elif appendix and ROW_LABEL_RE.match(s):
                found.setdefault(f"App{appendix}-{s}", no)
            elif appendix:
                found.setdefault(f"App{appendix}", no)
    return found


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def check_bound(r, where, rule, side, params):
    amt = rule.get(f"threshold_{side}")
    inc = rule.get(f"threshold_{side}_inclusive")
    par = rule.get(f"threshold_{side}_param")
    txt = rule.get(f"threshold_{side}_text")
    if amt is not None and not is_int(amt):
        r.err(where, f"threshold_{side} must be a GBP integer or null, got {amt!r}")
    if amt is not None and is_int(amt) and amt < 0:
        r.err(where, f"threshold_{side} is negative")
    if amt is not None and par is not None:
        r.err(where, f"threshold_{side} and threshold_{side}_param are both set; use one")
    if par is not None and par not in params:
        r.err(where, f"threshold_{side}_param {par!r} is not declared in parameters")
    bound_set = amt is not None or par is not None
    if bound_set:
        if not isinstance(inc, bool):
            r.err(where, f"threshold_{side}_inclusive must be true/false when the bound is set")
        if not isinstance(txt, str) or not txt.strip():
            r.err(where, f"threshold_{side}_text (the bound as printed) is required when the bound is set")
        elif normalise(txt) not in normalise(rule.get("verbatim_quote") or ""):
            r.err(where, f"threshold_{side}_text {txt!r} does not appear in verbatim_quote")
        elif amt is not None:
            printed = []
            for a, mil in re.findall(r"£\s?([\d,]+(?:\.\d+)?)\s?(million)?", txt):
                if mil:  # e.g. "£2.5million"
                    printed.append(round(float(a.replace(",", "")) * 1_000_000))
                elif "." not in a:  # pence amounts are skipped (see SKILL.md)
                    printed.append(int(a.replace(",", "")))
            if printed and amt not in printed:
                r.err(where, f"threshold_{side}={amt} does not match the amount printed in {txt!r}")
    else:
        if inc is not None or txt is not None:
            r.err(where, f"threshold_{side}_inclusive/_text must be null when there is no {side} bound")


def check_quote(r, where, quote, page, page_end, norm_pages):
    n = len(norm_pages["plain"])
    if not is_int(page) or not 1 <= page <= n:
        r.err(where, f"page {page!r} is not a page of the PDF (1-{n})")
        return
    last = page if page_end is None else page_end
    if page_end is not None and (not is_int(page_end) or not page <= page_end <= n):
        r.err(where, f"page_end {page_end!r} invalid")
        return
    if not isinstance(quote, str) or not quote.strip():
        r.err(where, "verbatim_quote is empty")
        return
    segments = [normalise(s) for s in quote.split(ELISION)]
    if any(not s for s in segments):
        r.err(where, "verbatim_quote has an empty segment around [...]")
        return
    for mode in ("plain", "layout"):
        texts = norm_pages[mode][page - 1:last]
        pos_page, pos, ok = 0, 0, True
        for seg in segments:
            while pos_page < len(texts):
                i = texts[pos_page].find(seg, pos)
                if i >= 0:
                    pos = i + len(seg)
                    break
                pos_page, pos = pos_page + 1, 0
            else:
                ok = False
                break
        if ok:
            return
    elsewhere = [i + 1 for i, t in enumerate(norm_pages["plain"]) if segments[0] in t]
    hint = f" (first segment found on page(s) {elsewhere})" if elsewhere else " (not found anywhere in the PDF)"
    span = f"page {page}" if last == page else f"pages {page}-{last}"
    r.err(where, f"verbatim_quote not found on {span}{hint}: {quote[:70]!r}")


def verify(doc, plain, layout):
    r = Report()
    norm = {"plain": [normalise(p) for p in plain], "layout": [normalise(p) for p in layout]}

    if not isinstance(doc, dict):
        r.err("top", "rules.json must be a JSON object with keys " + ", ".join(sorted(TOP_KEYS)))
        return r
    missing, extra = TOP_KEYS - doc.keys(), doc.keys() - TOP_KEYS
    if missing:
        r.err("top", f"missing keys {sorted(missing)}")
    if extra:
        r.err("top", f"unexpected keys {sorted(extra)}")
    params = doc.get("parameters") if isinstance(doc.get("parameters"), dict) else {}
    rules = doc.get("rules") if isinstance(doc.get("rules"), list) else []
    excluded = doc.get("excluded") if isinstance(doc.get("excluded"), list) else []
    notes = doc.get("notes") if isinstance(doc.get("notes"), list) else []
    for k, t in (("parameters", dict), ("rules", list), ("excluded", list), ("notes", list)):
        if k in doc and not isinstance(doc[k], t):
            r.err("top", f"{k} must be a {t.__name__}")

    # parameters
    for key, p in params.items():
        where = f"parameters.{key}"
        if not PARAM_KEY_RE.match(key):
            r.err(where, "key must be UPPER_SNAKE_CASE")
        if not isinstance(p, dict):
            r.err(where, "must be an object")
            continue
        for f in ("value", "printed_as", "defined_in", "page"):
            if f not in p:
                r.err(where, f"missing field {f!r}")
        if p.get("value") is not None:
            r.err(where, f"value must be null (the PDF does not print it); got {p.get('value')!r}")
        if isinstance(p.get("printed_as"), str) and is_int(p.get("page")):
            check_quote(r, where + ".printed_as", p["printed_as"], p["page"], None, norm)
        elif "page" in p:
            r.err(where, "printed_as must be a string and page an integer")

    # rules
    used_params = set()
    covered = {}
    for i, rule in enumerate(rules):
        rid = rule.get("rule_id") if isinstance(rule, dict) else None
        where = f"rules[{i}]" + (f" {rid}" if rid else "")
        if not isinstance(rule, dict):
            r.err(where, "must be an object")
            continue
        missing = RULE_KEYS - rule.keys()
        extra = rule.keys() - RULE_KEYS - OPTIONAL_RULE_KEYS
        if missing:
            r.err(where, f"missing fields {sorted(missing)}")
        if extra:
            r.err(where, f"unexpected fields {sorted(extra)}")
        expected = f"CPR-{i + 1:02d}"
        if rid != expected:
            r.err(where, f"rule_id must be {expected!r} (sequential, no gaps), got {rid!r}")
        if not isinstance(rule.get("clause"), str) or not rule["clause"]:
            r.err(where, "clause must be a non-empty string")
        else:
            covered.setdefault(rule["clause"], []).append("rules")
        if rule.get("type") not in RULE_TYPES:
            r.err(where, f"type {rule.get('type')!r} not in {sorted(RULE_TYPES)}")
        sc = rule.get("scope")
        if not isinstance(sc, list) or not sc or any(s not in SCOPES for s in sc):
            r.err(where, f"scope must be a non-empty list from {sorted(SCOPES)}")
        elif "all" in sc and len(sc) > 1:
            r.err(where, "scope 'all' cannot be combined with other scopes")
        if not isinstance(rule.get("condition"), str) or not rule["condition"].strip():
            r.err(where, "condition must be a non-empty string")
        ev = rule.get("evidence_source")
        if not isinstance(ev, list) or not ev or any(e not in EVIDENCE for e in ev):
            r.err(where, f"evidence_source must be a non-empty list from {sorted(EVIDENCE)}")
        for f in ("required_action", "approver"):
            if rule.get(f) is not None and (not isinstance(rule[f], str) or not rule[f].strip()):
                r.err(where, f"{f} must be a non-empty string or null")
        for side in ("low", "high"):
            check_bound(r, where, rule, side, params)
            if rule.get(f"threshold_{side}_param"):
                used_params.add(rule[f"threshold_{side}_param"])
        lo, hi = rule.get("threshold_low"), rule.get("threshold_high")
        if is_int(lo) and is_int(hi) and lo >= hi:
            r.err(where, f"threshold_low {lo} must be below threshold_high {hi}")
        testable = any(rule.get(f) is not None for f in (
            "threshold_low", "threshold_high", "threshold_low_param",
            "threshold_high_param", "required_action", "approver"))
        if not testable:
            r.err(where, "not testable: needs a threshold, required_action or approver")
        check_quote(r, where, rule.get("verbatim_quote"), rule.get("page"), rule.get("page_end"), norm)

    for key in params.keys() - used_params:
        r.warn(f"parameters.{key}", "declared but not used by any rule")

    # excluded
    for i, ex in enumerate(excluded):
        where = f"excluded[{i}]"
        if not isinstance(ex, dict) or set(ex.keys()) != {"clause", "page", "reason"}:
            r.err(where, "must be an object with exactly clause, page, reason")
            continue
        where += f" {ex['clause']}"
        if not isinstance(ex["clause"], str) or not ex["clause"]:
            r.err(where, "clause must be a non-empty string")
            continue
        covered.setdefault(ex["clause"], []).append("excluded")
        if not is_int(ex["page"]) or not 1 <= ex["page"] <= len(plain):
            r.err(where, f"page {ex['page']!r} is not a page of the PDF")
        reason = ex["reason"]
        if not isinstance(reason, str) or not reason.strip():
            r.err(where, "reason is empty")
        elif "\n" in reason or len(reason) > 200:
            r.err(where, "reason must be one line (no newlines, at most 200 characters)")

    # notes
    for i, n in enumerate(notes):
        where = f"notes[{i}]"
        if not isinstance(n, dict) or set(n.keys()) != {"clauses", "page", "issue"}:
            r.err(where, "must be an object with exactly clauses (list), page, issue")
            continue
        if not isinstance(n["clauses"], list) or not n["clauses"]:
            r.err(where, "clauses must be a non-empty list")
        if not is_int(n["page"]) or not 1 <= n["page"] <= len(plain):
            r.err(where, f"page {n['page']!r} is not a page of the PDF")
        if not isinstance(n["issue"], str) or not n["issue"].strip():
            r.err(where, "issue is empty")

    # coverage
    inventory = clause_inventory(plain)
    for clause, page in inventory.items():
        if CLAUSE_RE.match(clause) or "-" in clause:
            if clause not in covered:
                r.err(f"coverage {clause}", f"clause on page {page} is in neither rules nor excluded")
        else:  # bare appendix letter: need at least one AppX-* entry
            if not any(c.startswith(clause + "-") for c in covered):
                r.err(f"coverage {clause}", f"no rules or excluded entries for Appendix {clause[3:]} (page {page})")
    for clause, where_used in covered.items():
        if CLAUSE_RE.match(clause):
            if clause not in inventory:
                r.err(f"clause {clause}", "is not a numbered clause in the PDF")
        elif APPENDIX_ID_RE.match(clause):
            if f"App{APPENDIX_ID_RE.match(clause).group(1)}" not in inventory:
                r.err(f"clause {clause}", "refers to an appendix not found in the PDF")
        else:
            r.err(f"clause {clause}", "must be a clause number like 6.16 or an appendix ID like AppB-B1")
        if "rules" in where_used and "excluded" in where_used:
            r.warn(f"clause {clause}", "appears in both rules and excluded; check the exclusion covers only the untestable part")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", default="data/contract-rules.pdf")
    ap.add_argument("--rules", default="outputs/rules.json")
    ap.add_argument("--list-clauses", action="store_true", help="print the clause inventory and exit")
    a = ap.parse_args()

    if not shutil.which("pdftotext"):
        print("ERROR: pdftotext not found (install poppler)", file=sys.stderr)
        return 2
    try:
        plain, layout = pdf_pages(a.pdf, False), pdf_pages(a.pdf, True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: cannot read {a.pdf}: {e}", file=sys.stderr)
        return 2

    if a.list_clauses:
        inv = clause_inventory(plain)
        by_page = {}
        for c, p in inv.items():
            by_page.setdefault(p, []).append(c)
        for p in sorted(by_page):
            print(f"page {p}: {' '.join(by_page[p])}")
        print(f"{len(inv)} items ({len(plain)} pages)")
        return 0

    try:
        with open(a.rules, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot load {a.rules}: {e}", file=sys.stderr)
        return 2

    r = verify(doc, plain, layout)
    for w in r.warnings:
        print("WARN ", w)
    for e in r.errors:
        print("ERROR", e)
    n_rules = len(doc.get("rules", [])) if isinstance(doc, dict) else 0
    n_ex = len(doc.get("excluded", [])) if isinstance(doc, dict) else 0
    print(f"\n{n_rules} rules, {n_ex} excluded, {len(r.errors)} errors, {len(r.warnings)} warnings")
    print("RESULT:", "PASS" if not r.errors else "FAIL")
    return 0 if not r.errors else 1


if __name__ == "__main__":
    sys.exit(main())
