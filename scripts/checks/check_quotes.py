#!/usr/bin/env python3
"""QA quote check.

1. Runs the extract-rules verifier (.claude/skills/extract-rules/verify_quotes.py)
   on outputs/rules.json against data/contract-rules.pdf: every verbatim_quote
   must be in the PDF on its stated page.
2. Every rule excerpt in outputs/risk-register.md, i.e. each evidence line
   `CPR-NN (clause X): <text>`, must name a rule in rules.json with that
   clause and exactly that condition text.

Usage: check_quotes.py [--outputs DIR] [--data DIR]
"""
import re
import subprocess
import sys

from _common import REPO, Result, args, load_json, run

EXCERPT_RE = re.compile(r"^\s*-\s+(?:M\d+\s+)?(CPR-\d+) \(clause (.+?)\): (.+?)\s*$", re.M)


def main() -> int:
    a = args(__doc__)
    res = Result("quotes")
    rules_p, pdf = a.outputs / "rules.json", a.data / "contract-rules.pdf"
    verifier = REPO / ".claude/skills/extract-rules/verify_quotes.py"
    if not pdf.exists():
        res.fail(f"{pdf} is missing")
    elif not rules_p.exists():
        res.fail(f"{rules_p} is missing")
    else:
        p = subprocess.run([sys.executable, str(verifier), str(rules_p), str(pdf)], capture_output=True, text=True)
        out = p.stdout + p.stderr
        fails = [ln[6:] for ln in out.splitlines() if ln.startswith("FAIL  ")]
        last = [ln for ln in out.splitlines() if ln.strip()][-1:] or ["(no output)"]
        res.info(f"extract-rules verifier: {last[0]}")
        if p.returncode != 0:
            for f in fails or [last[0]]:
                res.fail(f"rules.json vs PDF: {f}")
        else:
            m = re.search(r"\((\d+) rules", last[0])
            res.ok(int(m.group(1)) if m else 1)

    rules = load_json(rules_p, res) if rules_p.exists() else None
    reg_p = a.outputs / "risk-register.md"
    if rules is None:
        return res.finish()
    if not reg_p.exists():
        res.fail("risk-register.md is missing")
        return res.finish()
    by_id = {r["rule_id"]: r for r in rules.get("rules", [])}
    excerpts = EXCERPT_RE.findall(reg_p.read_text(encoding="utf-8"))
    if not excerpts:
        res.fail("risk-register.md has no rule excerpts to check (expected 'CPR-NN (clause X): ...' evidence lines)")
    for rid, clause, text in excerpts:
        r = by_id.get(rid)
        if r is None:
            res.fail(f"risk-register.md cites {rid}, which is not in rules.json")
        elif r["clause"] != clause:
            res.fail(f"risk-register.md: {rid} clause '{clause}' but rules.json has '{r['clause']}'")
        elif r["condition"] != text:
            res.fail(f"risk-register.md: {rid} excerpt differs from rules.json condition: {text[:80]!r}")
        else:
            res.ok()
    res.info(f"register rule excerpts checked: {len(excerpts)}")
    return res.finish()


if __name__ == "__main__":
    run(main)
