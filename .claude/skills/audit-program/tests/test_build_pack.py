#!/usr/bin/env python3
"""Tests for build_pack.py on a two-risk fixture (subsets of the real outputs).

Walks the gate (draft register -> closed; decisions recorded but not applied
-> closed; revision 1 -> open), builds the pack, checks determinism and the
sample verification, then confirms the build fails on: a missing approved
risk, a control with no rule citation, a rule neither cited nor listed as not
tested, a control with no test, a transaction absent from spend-clean.csv, a
typed figure, and accusatory wording.

Run: .venv/bin/python .claude/skills/audit-program/tests/test_build_pack.py
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
FIX = HERE / "fixtures"
PACK = HERE.parent / "build_pack.py"
REG = HERE.parents[1] / "risk-assessment" / "build_register.py"
PLAN = json.loads((FIX / "audit-plan.json").read_text())
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'ok  ' if cond else 'FAIL'} {name}" + ("" if cond else f"\n     {detail[:1500]}"))


def run(*args):
    p = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def register(out: Path, ratings: dict):
    (out / "risk-ratings.json").write_text(json.dumps(ratings, ensure_ascii=False))
    return run(REG, "--ratings", out / "risk-ratings.json", "--analytics", out / "analytics.json",
               "--history", out / "history.json", "--rules", out / "rules.json", "--out-dir", out)


def approve_all(out: Path):
    p = out / "auditor-comments.md"
    lines = []
    for ln in p.read_text().splitlines():
        if re.match(r"\| R-\d+ \|", ln):
            c = ln.strip().strip("|").split("|")
            c[-2] = " Approve "
            ln = "|" + "|".join(c) + "|"
        lines.append(ln)
    p.write_text("\n".join(lines))


def setup(out: Path):
    for f in ("analytics.json", "history.json", "rules.json"):
        shutil.copy(FIX / f, out / f)
    shutil.copytree(FIX / "analytics-full", out / "analytics-full")
    ratings = json.loads((FIX / "risk-ratings.json").read_text())
    rc, log = register(out, ratings)
    assert rc == 0, log
    return ratings


def pack(out: Path, plan: dict | None = None, gate=False):
    if gate:
        return run(PACK, "--gate", "--outputs", out)
    (out / "audit-plan.json").write_text(json.dumps(plan if plan is not None else PLAN, ensure_ascii=False))
    return run(PACK, "--outputs", out)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        ratings = setup(out)

        # ---- gate
        rc, log = pack(out, gate=True)
        check("gate closed on a draft register (revision 0)", rc == 1 and "revision 0, a draft" in log
              and "no auditor decision for R-01, R-02" in log, log)
        approve_all(out)
        rc, log = pack(out, gate=True)
        check("gate closed when decisions are recorded but not applied", rc == 1 and "not applied yet: R-01, R-02" in log, log)
        ratings["revision"] = {"number": 1, "summary": "Both approved.", "changes": []}
        rc, log = register(out, ratings)
        check("register revision 1 builds", rc == 0, log)
        rc, log = pack(out, gate=True)
        check("gate open after revision 1", rc == 0 and "GATE OPEN" in log and "in scope: R-01, R-02" in log, log)
        check("--gate alone writes nothing", not (out / "planning-memo.md").exists() and not (out / "samples").exists())

        # ---- good build
        rc, log = pack(out)
        check("pack builds", rc == 0 and "pack built: 2 risk(s) in scope, 2 test(s)" in log, log)
        memo, rcm, prog = [(out / f).read_text() for f in ("planning-memo.md", "risk-control-matrix.md", "audit-program.md")]
        figs = json.loads((out / "pack-figures.json").read_text())
        s1, s2 = pd.read_csv(out / "samples" / "T-01-1.csv"), pd.read_csv(out / "samples" / "T-02-1.csv")
        check("R-01 (score 15) samples 25 windows", s1["sample_unit"].nunique() == 25, str(s1["sample_unit"].nunique()))
        check("R-02 (score 9) samples 15 groups", s2["sample_unit"].nunique() == 15, str(s2["sample_unit"].nunique()))
        spend = pd.read_csv(out / "analytics-full" / "spend-clean.csv")
        check("every sampled transaction is in spend-clean.csv with the same amount",
              all(s.merge(spend[["row_id", "Net amount"]], on="row_id", suffixes=("", "_s"))
                  .eval("`Net amount` == `Net amount_s`").all() and len(s.merge(spend, on="row_id")) == len(s) for s in (s1, s2)))
        src = pd.read_csv(out / "analytics-full" / "split_purchases.csv").sort_values(["total_gbp", "supplier_norm"], ascending=[False, True])
        check("T-01-1 takes the 25 highest-value windows", set(s1["sample_unit"].str.split("|").str[1]) ==
              set(src.head(25)["supplier_norm"]))
        comp = {f["name"]: f["value"] for f in figs["computed"]}
        check("pack-figures lists computed figures", comp.get("sample.T-01-1.population") == 39 and comp.get("sample.T-02-1.population") == 35
              and comp.get("sample.transactions_total") == len(s1) + len(s2) and comp.get("risks_in_scope") == 2, json.dumps(comp)[:600])
        check("pack-figures lists analytics figures it printed",
              any(x["path"] == "$.population.months_covered" for x in figs["from_analytics"]), str(figs["from_analytics"])[:400])
        check("memo fills placeholders, no braces left", "3 months" in memo and "{{" not in memo + rcm + prog, memo[:800])
        check("RCM shows rule coverage with both not-tested rules", "CPR-05" in rcm and "CPR-55" in rcm and "4 cited" in rcm, rcm)
        check("audit program ends with the PBC list, shared item merged",
              prog.split("\n## ")[-1].startswith("PBC list") and "| T-01-1, T-02-1 |" in prog, prog[-900:])
        check("indicator disclaimer on every document", all("risk indicators to investigate" in x for x in (memo, rcm, prog)))
        first = {f: (out / "samples" / f).read_bytes() for f in ("T-01-1.csv", "T-02-1.csv")}
        rc, log = pack(out)
        check("samples are deterministic across builds",
              rc == 0 and all((out / "samples" / f).read_bytes() == b for f, b in first.items()), log)

        # ---- failures (each must fail and write nothing new)
        def fails(name, plan, needle, mutate_spend=False):
            stamp = (out / "planning-memo.md").stat().st_mtime_ns
            if mutate_spend:
                p = out / "analytics-full" / "spend-clean.csv"
                orig = p.read_text()
                sp = pd.read_csv(p)
                top = pd.read_csv(out / "samples" / "T-02-1.csv")["row_id"].iloc[0]
                sp[sp.row_id != top].to_csv(p, index=False)
            rc, log = pack(out, plan)
            if mutate_spend:
                p.write_text(orig)
            check(name, rc == 1 and needle in log and (out / "planning-memo.md").stat().st_mtime_ns == stamp, log)

        p = copy.deepcopy(PLAN); p["risks"] = [p["risks"][0]]
        fails("fails on a missing approved risk", p, "approved risk R-02 is missing from audit-plan.json")
        p = copy.deepcopy(PLAN); p["risks"][1]["controls"][0]["description"] = "Each payment is matched to a distinct approved invoice."
        fails("fails on an uncited control", p, "C-02-1.description: must cite at least one rule")
        p = copy.deepcopy(PLAN); p["rules_not_tested"] = p["rules_not_tested"][:1]
        fails("fails on an unaccounted rule", p, "nor listed as not tested: CPR-55")
        p = copy.deepcopy(PLAN); p["risks"][0]["controls"].append(
            {"control_id": "C-01-3", "description": "Contract values are recorded [rule:CPR-56]."})
        fails("fails on a control with no test", p, "C-01-3: no test covers this control")
        fails("fails when a sampled transaction is not in spend-clean.csv", PLAN, "is not in spend-clean.csv", mutate_spend=True)
        p = copy.deepcopy(PLAN); p["memo"]["approach"] += " About 39 windows were flagged."
        fails("fails on a typed figure", p, "figure typed in prose '39'")
        p = copy.deepcopy(PLAN); p["memo"]["objective"] += " Identify fraudulent suppliers."
        fails("fails on accusatory wording", p, "'fraudulent' is not indicator language")
        p = copy.deepcopy(PLAN); p["rules_not_tested"].append({"rule_id": "CPR-11", "reason": "Not tested in this plan at all."})
        fails("fails when a rule is both cited and listed as not tested", p, "CPR-11 is cited by the plan")

        # ---- gate re-closes when the register is edited by hand
        reg = out / "risk-register.md"
        reg.write_text(reg.read_text() + "\nedited\n")
        rc, log = pack(out, gate=True)
        check("gate closed when the register was edited by hand", rc == 1 and "does not match the builder's state" in log, log)

    print(f"\n{sum(results)}/{len(results)} checks passed")
    print("ALL TESTS PASSED" if all(results) else "TESTS FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
