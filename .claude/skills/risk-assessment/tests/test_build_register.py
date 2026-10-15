#!/usr/bin/env python3
"""Tests for build_register.py on fixtures (subsets of the real outputs).

fixtures/risk-ratings.json holds one good risk (R-01) and one broken risk
(R-02: unresolvable citations, typed figures, non-adverse uplift, rubric
breaks, bad placeholder). Further cases mutate the good risk and walk the
auditor gate: decisions kept, revision applied, unrequested / unapplied
changes refused.

Run: .venv/bin/python .claude/skills/risk-assessment/tests/test_build_register.py
"""
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
BUILD = HERE.parent / "build_register.py"
RATINGS = json.loads((FIX / "risk-ratings.json").read_text())
results = []


def build(ratings: dict, out: Path):
    rp = out / "ratings.json"
    rp.write_text(json.dumps(ratings, ensure_ascii=False))
    p = subprocess.run([sys.executable, str(BUILD), "--ratings", str(rp), "--analytics", str(FIX / "analytics.json"),
                        "--history", str(FIX / "history.json"), "--rules", str(FIX / "rules.json"),
                        "--out-dir", str(out)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def check(name: str, cond: bool, detail: str = ""):
    results.append(cond)
    print(f"{'ok  ' if cond else 'FAIL'} {name}" + ("" if cond else f"\n     {detail[:1500]}"))


def read(out: Path, f: str) -> str:
    return (out / f).read_text()


def set_decision(out: Path, rid: str, decision: str, comment: str, other: str | None = None):
    p = out / "auditor-comments.md"
    lines = []
    for ln in p.read_text().splitlines():
        if ln.startswith(f"| {rid} |"):
            cells = ln.strip().strip("|").split("|")
            cells[-2], cells[-1] = f" {decision} ", f" {comment} "
            ln = "|" + "|".join(cells) + "|"
        lines.append(ln)
    text = "\n".join(lines)
    if other:
        text = re.sub(r"(## Other instructions\n\n)<!--.*?-->", lambda m: m.group(1) + other, text, flags=re.S)
    p.write_text(text)


def good_only():
    r = copy.deepcopy(RATINGS)
    r["risks"] = [r["risks"][0]]
    return r


def main() -> int:
    # 1. one good, one broken ------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        rc, log = build(RATINGS, out)
        reg = read(out, "risk-register.md")
        com = read(out, "auditor-comments.md")
        check("draft builds (exit 0)", rc == 0, log)
        check("good risk rated: L3 x I5 = 15, Extreme (Red)",
              "| R-01 |" in reg and "| 3 | 5 | 15 | Extreme | Extreme (Red) | in |" in reg, reg)
        check("placeholders filled from analytics", "£25,000 quotation threshold" in reg and "39 30-day windows" in reg
              and "£2,221,901" in reg and "{{" not in reg.split("## Risks excluded")[0], reg)
        check("financial impact computed from the £ band", "→ council £ band level 5" in reg, reg)
        check("broken risk dropped, not rated", "| R-02 |" not in reg.split("## Risks excluded")[0]
              and "**R-02**" in reg and "R-02" not in com.split("## Other")[0], reg)
        for reason in ["likelihood justification has no resolvable citation",
                       "impact justification has no resolvable citation",
                       "uplift cites AUD-11 whose opinion is not adverse",
                       "L4 needs signals from two different tests",
                       "placeholder {{$.tests.duplicates.per_tier.different_time.groups}} unresolved"]:
            check(f"R-02 reason: {reason}", reason in reg, reg)
        check("typed figures warned", "figure typed in prose '35'" in log and "figure typed in prose '£299k'" in log, log)
        check("good risk has no warnings", "WARN  R-01" not in log, log)
        check("conflicts marked in header: bands, CRR, financial, Medium label",
              all(s in reg for s in ["[DISC-03]", "[DISC-04]", "[DISC-02, DISC-09]", "[DISC-01]", "**Used:** Table 4"]), reg)
        check("register ends with 'Auditor decisions'", reg.rstrip().split("\n## ")[-1].startswith("Auditor decisions"), reg)
        check("comments template: R-01 row with blank decision",
              re.search(r"\| R-01 \|.*\| in \|\s*\|\s*\|$", com, re.M) is not None, com)

        # 2. decisions kept on rewrite; pending decision without revision refused
        set_decision(out, "R-01", "Amend", "likelihood 2: windows are recurring contract payments")
        rc, log = build(RATINGS, out)
        check("pending decision without a revision block is refused", rc == 1 and "no 'revision' block" in log, log)
        check("comments file untouched by the refused build",
              "likelihood 2: windows are recurring" in read(out, "auditor-comments.md"))

        # 3. revision that applies the Amend (R-02 removed from ratings -> it never was rated)
        rev = good_only()
        rev["risks"][0]["likelihood"].update(base_score=2, rubric_level="L2")
        rev["revision"] = {"number": 1, "summary": "Applies the auditor's decision on R-01.",
                           "changes": [{"risk_id": "R-01", "decision": "Amend", "change": "likelihood 3 → 2"}]}
        rc, log = build(rev, out)
        reg = read(out, "risk-register.md")
        state = json.loads(read(out, "risk-register.state.json"))
        check("revision 1 builds", rc == 0, log)
        check("revision header names the change", "**Revision 1" in reg and "R-01: likelihood 3 → 2" in reg, reg)
        check("auditor override marked on the risk", "Auditor override (revision 1)" in reg, reg)
        check("score recomputed: L2 x I5 = 10 ‡, Medium - High (Amber)", "| 2 | 5 | 10 ‡ | High | Medium - High (Amber) |" in reg, reg)
        check("decision kept in rewritten comments file",
              "| Amend | likelihood 2: windows are recurring contract payments |" in read(out, "auditor-comments.md"))
        check("state: revision 1, all decided", state["revision"] == 1 and state["all_decided"], str(state))

        # 3b. unchanged rebuild of the current revision keeps header, override and scores
        rc, log = build(rev, out)
        reg = read(out, "risk-register.md")
        state = json.loads(read(out, "risk-register.state.json"))
        check("unchanged rebuild of revision 1 allowed", rc == 0 and "**Revision 1" in reg, log)
        check("rebuild keeps the override mark and change list",
              "Auditor override (revision 1)" in reg and "R-01: likelihood 3 → 2" in reg, reg)
        check("state records scores", state["scores"]["R-01"]["score"] == 10 and state["scores"]["R-01"]["band_id"] == "BAND-MEDIUM-HIGH", str(state.get("scores")))
        bad = copy.deepcopy(rev)
        bad["risks"][0]["impact"]["score"] = 4
        rc, log = build(bad, out)
        check("changed content under the current revision number refused", rc == 1 and "is the current revision" in log, log)

        # 4. re-run of revision 1 content as revision 2 with an unrequested change
        rev2 = copy.deepcopy(rev)
        rev2["risks"][0]["impact"]["score"] = 4
        rev2["revision"] = {"number": 2, "changes": []}
        rc, log = build(rev2, out)
        check("unrequested change refused", rc == 1 and "changed without an auditor request" in log, log)

    # 5. unapplied Amend and unapplied Reject --------------------------------
    for dec, comment, msg in [("Amend", "impact 4", "nothing changed (decision left unapplied)"),
                              ("Reject", "covered by contract letting audit", "status is 'proposed' (decision left unapplied)")]:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            build(good_only(), out)
            set_decision(out, "R-01", dec, comment)
            same = good_only()
            same["revision"] = {"number": 1, "changes": [{"risk_id": "R-01", "decision": dec, "change": "none"}]}
            rc, log = build(same, out)
            check(f"unapplied {dec} refused", rc == 1 and msg in log, log)

    # 6. undecided risk at revision ------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        build(good_only(), out)
        r = good_only()
        r["revision"] = {"number": 1, "changes": []}
        rc, log = build(r, out)
        check("revision with an undecided risk refused", rc == 1 and "no auditor decision for R-01" in log, log)

    # 7. Approve + new risk requested in 'Other instructions' ------------------
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        build(good_only(), out)
        set_decision(out, "R-01", "Approve", "", other="Add a risk on duplicate payments in general procurement.")
        r = copy.deepcopy(RATINGS)
        dup = r["risks"][1] = copy.deepcopy(RATINGS["risks"][0])
        dup.update(risk_id="R-02", title="Same supplier and amount paid twice within a week")
        dup["likelihood"].update(justification="Repeat amounts in general procurement [metric:$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.groups].",
                                 signals=[{"metric": "$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.groups", "op": ">", "than": 0}])
        dup["impact"] = {"score": 3, "dimension": "DIM-FIN",
                         "financial_basis": "$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.gbp_beyond_first",
                         "justification": "Value beyond the first payment [metric:$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.gbp_beyond_first] [history:IMP-3-FIN]."}
        r["revision"] = {"number": 1, "changes": [{"risk_id": "R-02", "change": "added",
                                                   "requested_in": "Add a risk on duplicate payments in general procurement."}]}
        rc, log = build(r, out)
        reg = read(out, "risk-register.md")
        check("approved risk unchanged + requested new risk accepted", rc == 0 and "R-02: added at the auditor's request" in reg, log + reg)
        check("score 9 marked ‡ under the Figure 4 CRR criterion", "| 9 ‡ |" in reg and "‡ CRR-level under ESC-CRR-1" in reg, reg)

    # 8. rubric mutations on the good risk -----------------------------------
    def mutate(f):
        r = good_only()
        f(r["risks"][0])
        with tempfile.TemporaryDirectory() as d:
            rc, log = build(r, Path(d))
            return rc, log, read(Path(d), "risk-register.md")

    rc, log, reg = mutate(lambda x: x["likelihood"].update(uplift={"history_id": "AUD-12", "justification": "Limited Assurance [history:AUD-12]."}))
    check("uplift with adverse audit: L3 -> L4, stated", "Repeat finding: +1 likelihood (L3 → L4) because AUD-12 (Limited Assurance)" in reg
          and "| 4 | 5 | 20 |" in reg, reg)
    rc, log, reg = mutate(lambda x: x["likelihood"].update(uplift={"history_id": "AUD-01", "justification": "[history:AUD-01]"}))
    check("uplift with non-adverse audit drops the risk", "uplift cites AUD-01 whose opinion is not adverse" in reg, reg)
    rc, log, reg = mutate(lambda x: x["impact"].update(score=4, justification=x["impact"]["justification"].replace("IMP-5-FIN", "IMP-4-FIN")))
    check("impact score off the £ band drops the risk", "impact score 4 but the £ basis £2,221,901 falls in level 5" in reg, reg)
    rc, log, reg = mutate(lambda x: x["likelihood"].update(signals=[
        {"metric": "$.tests.threshold_clustering.per_threshold[?threshold==25000].band_by_tag.general_procurement.n", "op": ">", "than": 0}]))
    check("clustering at L3 without beating its comparator drops the risk", "needs a signal that beats its comparator" in reg, reg)
    rc, log, reg = mutate(lambda x: x["likelihood"].update(signals=[
        {"metric": "$.tests.threshold_clustering.per_threshold[?threshold==25000].band_count", "op": ">",
         "than": "$.tests.threshold_clustering.per_threshold[?threshold==25000].comparator_count"}]))
    check("a signal that does not hold drops the risk", "likelihood signal does not hold" in reg, reg)

    print(f"\n{sum(results)}/{len(results)} checks passed")
    print("ALL TESTS PASSED" if all(results) else "TESTS FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
