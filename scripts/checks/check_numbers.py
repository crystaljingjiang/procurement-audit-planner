#!/usr/bin/env python3
"""QA number check.

Every figure in planning-memo.md, risk-control-matrix.md and audit-program.md
that has three or more digits or a £ sign must equal a value in
analytics.json, pack-figures.json, rules.json or outputs/samples/*.csv.

A figure printed with d decimals matches a source value v when round(v, d)
equals it (so £2,221,901 matches 2221901.37, the builder's whole-pound
format). Percentages are compared as printed.

Skipped (not figures): row IDs (file.xlsx:row), rule/risk/control/test and
other IDs (CPR-11, R-02, C-01-1, T-02-1, IMP-5-FIN ...), dates and
timestamps, years, clause references (clause 6.16, App B row B1, 5.2.1),
page references (p14, page 14), metric paths ($.a.b[?x==1]) and inline code.

Usage: check_numbers.py [--outputs DIR]
"""
import re

import pandas as pd

from _common import PACK_DOCS, ROW_ID_RE, Result, args, load_json, numeric_leaves, run

SKIP_RES = [
    ROW_ID_RE,
    re.compile(r"`[^`]*`"),                                   # inline code (paths, file names)
    re.compile(r"\$\.[^\s;|,)]+"),                            # metric paths outside code
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][\d:.+]+)?"),      # dates, timestamps
    re.compile(r"\b(?:[A-Z]{1,5}-)+[A-Z0-9]*\d[A-Z0-9-]*\b"),  # IDs: CPR-11, T-02-1, IMP-5-FIN, BAND-...
    re.compile(r"\b(?:clause|section|§|para(?:graph)?)\s*\d+(?:\.\d+)*[a-z]?", re.I),
    re.compile(r"\bApp(?:endix)?\s+[A-Z]\b(?:\s+row\s+[A-Z]\d*)?", re.I),
    re.compile(r"\b(?:p|pp|page|pdf_page)\.?\s*\d+(?:\s*[-–]\s*\d+)?\b", re.I),
    re.compile(r"\b\d+(?:\.\d+){2,}\b"),                       # dotted clause numbers 5.2.1
    re.compile(r"\b[A-Za-z_]+\d+[A-Za-z_\d]*\b"),             # tokens mixing letters and digits (P02, v2, A1)
]
FIG_RE = re.compile(r"£\s?-?\d[\d,]*(?:\.\d+)?|-?\d[\d,]*(?:\.\d+)?%?")
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")


def figures(line: str):
    t = line
    for rx in SKIP_RES:
        t = rx.sub(" ", t)
    for m in FIG_RE.finditer(t):
        s = m.group(0)
        digits = re.sub(r"\D", "", s.split(".")[0])
        if not s.startswith("£") and len(re.sub(r"\D", "", s)) < 3:
            continue
        if not s.startswith("£") and YEAR_RE.match(s):
            continue
        num = s.replace("£", "").replace(",", "").replace("%", "").strip()
        dec = len(num.split(".")[1]) if "." in num else 0
        if digits == "" and not num:
            continue
        yield s, float(num), dec


def main() -> int:
    a = args(__doc__)
    res = Result("numbers")
    values = set()
    for f in ("analytics.json", "pack-figures.json", "rules.json"):
        p = a.outputs / f
        if not p.exists():
            res.fail(f"{f} is missing")
            continue
        doc = load_json(p, res)
        if doc is not None:
            numeric_leaves(doc, values)
    for p in sorted((a.outputs / "samples").glob("*.csv")):
        df = pd.read_csv(p)
        for c in df.select_dtypes("number").columns:
            values |= set(df[c].dropna().astype(float))
    rounded = {d: {round(v, d) for v in values} for d in range(0, 4)}
    n_figs = 0
    for doc in PACK_DOCS:
        p = a.outputs / doc
        if not p.exists():
            res.fail(f"{doc} is missing (pack not built)")
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            for s, x, dec in figures(line):
                n_figs += 1
                if round(x, min(dec, 3)) in rounded[min(dec, 3)]:
                    res.ok()
                else:
                    res.fail(f"{doc}:{i}: '{s}' is not a value in analytics.json, pack-figures.json, rules.json or samples/")
    res.info(f"figures checked: {n_figs}; source values: {len(values)}")
    return res.finish()


if __name__ == "__main__":
    run(main)
