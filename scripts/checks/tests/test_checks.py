#!/usr/bin/env python3
"""Tests for scripts/checks/*.py.

A. Current outputs: quotes must pass; numbers, trace and samples must report
   the pack as not built (until the agent team has run).
B. Fixture pack: the two-risk audit-program fixture is built end to end in a
   temp dir (register draft -> decisions -> revision 1 -> pack) with a closed
   challenges.md. The three pack checks pass, then each planted error
   must be caught:
     numbers: a figure no source contains;
     samples: a sampled transaction missing from spend-clean.csv, an amount
              altered in a sample file, a row ID in audit-program.md that is
              beyond the workbook;
     trace:   an unaccounted rule, an open challenge, an uncited challenge,
              a High risk rejected with no reason;
     quotes:  a register excerpt that differs from rules.json.
C. run_checks.py prints the table and BLOCKED for a failing pack, READY FOR
   SIGN-OFF for a clean one.

Run: .venv/bin/python scripts/checks/tests/test_checks.py
"""
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CHECKS = HERE.parent
REPO = CHECKS.parents[1]
AP_TESTS = REPO / ".claude/skills/audit-program/tests"
sys.path.insert(0, str(AP_TESTS))
import test_build_pack as tbp  # noqa: E402

results = []
CHALLENGES = """# Challenges: procurement audit planning pack

Pack versions reviewed: v1. Rounds: 1. Status: all rows closed.

| # | Round | Type | Risk | Challenge | Citation | Ask | Planner response | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | sample | R-01 | Sample sorted by value only | [metric:$.tests.split_purchases.per_threshold[?threshold==25000].headline_general_procurement.windows] | Keep value order | RESPONSE #1: declined | declined |
| 2 | 1 | rating | R-02 | Duplicates rated medium | [history:IMP-3-FIN] | Auditor to confirm | RESPONSE #2: for the auditor | for the auditor |
"""


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'ok  ' if cond else 'FAIL'} {name}" + ("" if cond else f"\n     {detail[:1800]}"))


def run(script, outputs, data=REPO / "data"):
    p = subprocess.run([sys.executable, str(CHECKS / script), "--outputs", str(outputs), "--data", str(data)],
                       capture_output=True, text=True, cwd=CHECKS)
    return p.returncode, p.stdout + p.stderr


def fails(log):
    return [ln[6:] for ln in log.splitlines() if ln.startswith("FAIL  ")]


def build_fixture_pack(out: Path):
    ratings = tbp.setup(out)
    tbp.approve_all(out)
    ratings["revision"] = {"number": 1, "summary": "Both approved.", "changes": []}
    rc, log = tbp.register(out, ratings)
    assert rc == 0, log
    rc, log = tbp.pack(out)
    assert rc == 0, log
    (out / "challenges.md").write_text(CHALLENGES)
    return ratings


def main() -> int:
    # ---------------- A. current outputs
    rc, log = run("check_quotes.py", REPO / "outputs")
    check("A quotes passes on current outputs", rc == 0 and "RESULT quotes: PASS" in log, log)
    for c in ("check_numbers.py", "check_trace.py", "check_samples.py"):
        rc, log = run(c, REPO / "outputs")
        built = (REPO / "outputs" / "planning-memo.md").exists()
        if built:
            check(f"A {c} runs on current outputs", "RESULT" in log, log)
        else:
            check(f"A {c} reports the pack as not built", rc == 1 and "pack not built" in log, log)

    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        build_fixture_pack(out)

        # ---------------- B. clean fixture
        for c in ("check_numbers.py", "check_trace.py", "check_samples.py"):
            rc, log = run(c, out)
            check(f"B {c} passes on the clean fixture pack", rc == 0, log)
        rc, log = run("check_numbers.py", out)
        n = int(re.search(r"figures checked: (\d+)", log).group(1))
        check("B numbers actually checked figures in the pack", n >= 10, log)

        # planted bad figure
        memo = out / "planning-memo.md"
        orig_memo = memo.read_text()
        memo.write_text(orig_memo + "\nThe flagged windows total £123,456,789 across 4,321 payments.\n")
        rc, log = run("check_numbers.py", out)
        f = fails(log)
        check("B numbers catches the planted figures (and only those)",
              rc == 1 and len(f) == 2 and "'£123,456,789'" in f[0] and "'4,321'" in f[1], log)
        memo.write_text(orig_memo)

        # planted missing row: remove a sampled transaction from spend-clean.csv
        sc = out / "analytics-full" / "spend-clean.csv"
        orig_sc = sc.read_text()
        s1 = pd.read_csv(out / "samples" / "T-01-1.csv")
        gone = s1["row_id"].iloc[0]
        df = pd.read_csv(sc)
        df[df.row_id != gone].to_csv(sc, index=False)
        rc, log = run("check_samples.py", out)
        f = fails(log)
        check("B samples catches the planted missing row (and only that)",
              rc == 1 and len(f) == 1 and f"{gone} is not in spend-clean.csv" in f[0], log)
        sc.write_text(orig_sc)

        # altered amount in a sample file
        p = out / "samples" / "T-02-1.csv"
        orig = p.read_text()
        s2 = pd.read_csv(p)
        s2.loc[0, "Net amount"] = s2.loc[0, "Net amount"] + 100
        s2.to_csv(p, index=False)
        rc, log = run("check_samples.py", out)
        check("B samples catches an altered amount", rc == 1 and "differs from spend-clean.csv" in log, log)
        p.write_text(orig)

        # row ID in the audit program beyond the workbook
        prog = out / "audit-program.md"
        orig_prog = prog.read_text()
        prog.write_text(orig_prog + "\nSee Over500_2026_P02_-_published.xlsx:99999.\n")
        rc, log = run("check_samples.py", out)
        check("B samples catches a row ID that is not in spend-clean or the workbook",
              rc == 1 and "Over500_2026_P02_-_published.xlsx:99999 is not in spend-clean.csv" in log, log)
        prog.write_text(orig_prog)

        # trace: unaccounted rule
        plan_p = out / "audit-plan.json"
        orig_plan = plan_p.read_text()
        plan = json.loads(orig_plan)
        plan["rules_not_tested"] = [x for x in plan["rules_not_tested"] if x["rule_id"] != "CPR-55"]
        plan_p.write_text(json.dumps(plan))
        rc, log = run("check_trace.py", out)
        check("B trace catches an unaccounted rule", rc == 1 and "CPR-55 is cited by no rated risk" in log, log)
        plan_p.write_text(orig_plan)

        # trace: open and uncited challenges
        cp = out / "challenges.md"
        cp.write_text(CHALLENGES.replace("| declined |", "| open |").replace(
            "[history:IMP-3-FIN]", "the auditor should look"))
        rc, log = run("check_trace.py", out)
        check("B trace catches an open challenge", rc == 1 and "challenge #1 is not closed" in log, log)
        check("B trace catches a challenge with no evidence", "challenge #2 cites no evidence" in log, log)
        cp.unlink()
        rc, log = run("check_trace.py", out)
        check("B trace catches a missing challenges.md", rc == 1 and "challenges.md is missing" in log, log)
        cp.write_text(CHALLENGES)

        # run_checks on the clean fixture: quotes fails here only because the
        # fixture rules.json is a subset; check the table and the pack verdict
        p = subprocess.run([sys.executable, str(CHECKS / "run_checks.py"), "--outputs", str(out)],
                           capture_output=True, text=True, cwd=CHECKS)
        table = p.stdout
        check("C run_checks prints one table with four checks",
              all(re.search(rf"^\| {c}\s+\| (PASS|FAIL)", table, re.M) for c in ("quotes", "numbers", "trace", "samples")), table)
        check("C pack checks pass in the table", all(re.search(rf"^\| {c}\s+\| PASS", table, re.M)
                                                    for c in ("numbers", "trace", "samples")), table)
        check("C verdict BLOCKED while any check fails (fixture rules subset fails the PDF verifier)",
              p.returncode == 1 and "VERDICT: BLOCKED" in table, table)

    # READY path: full rules.json, every rule accounted for in the plan
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        build_fixture_pack(out)
        shutil.copy(REPO / "outputs" / "rules.json", out / "rules.json")
        plan = json.loads((out / "audit-plan.json").read_text())
        cited = {"CPR-11", "CPR-30", "CPR-56", "CPR-57"}
        ids = [r["rule_id"] for r in json.loads((out / "rules.json").read_text())["rules"]]
        plan["rules_not_tested"] = [{"rule_id": i, "reason": "Outside this two-risk fixture plan."} for i in ids if i not in cited]
        (out / "audit-plan.json").write_text(json.dumps(plan))
        p = subprocess.run([sys.executable, str(CHECKS / "run_checks.py"), "--outputs", str(out)],
                           capture_output=True, text=True, cwd=CHECKS)
        check("C verdict READY FOR SIGN-OFF when all four checks pass",
              p.returncode == 0 and "VERDICT: READY FOR SIGN-OFF" in p.stdout and "FAIL" not in p.stdout, p.stdout)

    # trace: High risk rejected with no reason
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        ratings = tbp.setup(out)
        com = out / "auditor-comments.md"
        lines = []
        for ln in com.read_text().splitlines():
            if re.match(r"\| R-0[12] \|", ln):
                c = ln.strip().strip("|").split("|")
                c[-2] = " Approve " if ln.startswith("| R-01") else " Reject "
                ln = "|" + "|".join(c) + "|"
            lines.append(ln)
        com.write_text("\n".join(lines))
        r2 = copy.deepcopy(ratings)
        r2["risks"][1]["status"] = "rejected"
        r2["revision"] = {"number": 1, "changes": [{"risk_id": "R-02", "decision": "Reject", "change": "rejected"}]}
        rc, log = tbp.register(out, r2)
        assert rc == 0, log
        plan = copy.deepcopy(tbp.PLAN)
        plan["risks"] = [plan["risks"][0]]
        plan["rules_not_tested"].append({"rule_id": "CPR-30", "reason": "Only tested under R-02, rejected by the auditor."})
        rc, log = tbp.pack(out, plan)
        assert rc == 0, log
        (out / "challenges.md").write_text(CHALLENGES)
        rc, log = run("check_trace.py", out)
        check("B trace catches a High risk (score 9) out of scope with no reason",
              rc == 1 and "R-02 (score 9) is out of scope with no recorded reason" in log, log)

    # quotes: planted excerpt mismatch (real rules.json + real register)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        shutil.copy(REPO / "outputs" / "rules.json", out / "rules.json")
        reg = (REPO / "outputs" / "risk-register.md").read_text()
        bad = re.sub(r"(CPR-56 \(clause App B row B1\): )goods or services", r"\1goods, works or services", reg, count=1)
        (out / "risk-register.md").write_text(bad)
        rc, log = run("check_quotes.py", out)
        f = fails(log)
        check("B quotes catches a register excerpt that differs from rules.json",
              rc == 1 and len(f) == 1 and "CPR-56 excerpt differs" in f[0], log)
        (out / "risk-register.md").write_text(reg.replace("(clause 6.16)", "(clause 6.17)", 1))
        rc, log = run("check_quotes.py", out)
        check("B quotes catches a wrong clause", rc == 1 and "CPR-11 clause '6.17'" in log, log)

    print(f"\n{sum(results)}/{len(results)} checks passed")
    print("ALL TESTS PASSED" if all(results) else "TESTS FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
