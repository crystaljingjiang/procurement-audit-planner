#!/usr/bin/env python3
"""QA traceability check.

1. Every rule in rules.json is cited by a rated risk (risk-ratings.json:
   rule_ids or a [rule:] tag), a control or a test (audit-plan.json), or is
   listed in rules_not_tested with a reason.
2. Every approved in-scope risk (per the build_pack gate) has a control that
   a test covers, and appears in risk-control-matrix.md and audit-program.md.
3. Every High risk (register score 8 or above: Figure 1 'High'/'Extreme',
   Table 4 'Medium - High'/'Extreme') is in scope, or its exclusion is
   recorded with a reason (a Reject with a comment, or an approved
   out-of-scope risk with a scope_reason) and listed in planning-memo.md.
4. challenges.md exists; every challenge row cites evidence ([rule:],
   [metric:], [history:] or a pack file) and none is open.

Usage: check_trace.py [--outputs DIR]
"""
import re
import sys
from pathlib import Path

from _common import REPO, Result, args, load_json, md_table, run

sys.path.insert(0, str(REPO / ".claude/skills/audit-program"))
sys.path.insert(0, str(REPO / ".claude/skills/risk-assessment"))
HIGH_SCORE = 8
CLOSED = ("resolved", "declined", "for the auditor")
EVIDENCE_RE = re.compile(r"\[(?:rule|metric|history):[^\]]+|\b(?:CPR|AUD|FU|RT|GAP|DISC|IMP|BAND|ESC)-[\w-]+|"
                         r"\b[\w-]+\.(?:md|json)\b|\bT-\d{2}-\d+\b|\bC-\d{2}-\d+\b")


def main() -> int:
    a = args(__doc__)
    res = Result("trace")
    from build_pack import Fail, gate  # noqa: E402
    from build_register import find_tags  # noqa: E402

    rules = load_json(a.outputs / "rules.json", res)
    ratings = load_json(a.outputs / "risk-ratings.json", res)
    plan = load_json(a.outputs / "audit-plan.json", res) if (a.outputs / "audit-plan.json").exists() else None
    if plan is None:
        res.fail("audit-plan.json is missing (pack not built)")
    try:
        scope = gate(a.outputs)
    except Fail as f:
        for m in f.msgs:
            res.fail(m)
        scope = None
    if rules is None or ratings is None:
        return res.finish()

    # 1. rules
    state = load_json(a.outputs / "risk-register.state.json", res) or {}
    rated = set((state.get("scores") or {}).keys())
    cited = set()

    def tags(x):
        if isinstance(x, str):
            cited.update(ref for k, ref, _, _ in find_tags(x) if k == "rule")
        elif isinstance(x, dict):
            for v in x.values():
                tags(v)
        elif isinstance(x, list):
            for v in x:
                tags(v)
    for r in ratings.get("risks", []):
        if r.get("risk_id") in rated:
            cited.update(r.get("rule_ids") or [])
            tags(r)
    not_tested = {}
    if plan:
        for pr in plan.get("risks", []):
            tags(pr.get("controls"))
            tags(pr.get("tests"))
        not_tested = {x.get("rule_id"): str(x.get("reason", "")).strip() for x in plan.get("rules_not_tested") or []}
    for r in rules.get("rules", []):
        rid = r["rule_id"]
        if rid in cited:
            res.ok()
        elif rid in not_tested and len(not_tested[rid]) >= 8:
            res.ok()
        elif rid in not_tested:
            res.fail(f"{rid} is listed as not tested without a reason")
        else:
            res.fail(f"{rid} is cited by no rated risk, control or test and is not listed as not tested")

    # 2. in-scope risks
    rcm = (a.outputs / "risk-control-matrix.md").read_text() if (a.outputs / "risk-control-matrix.md").exists() else None
    prog = (a.outputs / "audit-program.md").read_text() if (a.outputs / "audit-program.md").exists() else None
    memo = (a.outputs / "planning-memo.md").read_text() if (a.outputs / "planning-memo.md").exists() else None
    for name, doc in (("risk-control-matrix.md", rcm), ("audit-program.md", prog), ("planning-memo.md", memo)):
        if doc is None:
            res.fail(f"{name} is missing (pack not built)")
    if scope and plan:
        planned = {p.get("risk_id"): p for p in plan.get("risks", [])}
        for e in scope["in"]:
            rid = e["risk_id"]
            pr = planned.get(rid)
            if not pr:
                res.fail(f"{rid} is approved in scope but has no entry in audit-plan.json")
                continue
            covered = {cid for t in pr.get("tests") or [] for cid in t.get("control_ids") or []}
            ctrls = [c.get("control_id") for c in pr.get("controls") or []]
            if not any(c in covered for c in ctrls):
                res.fail(f"{rid} has no control covered by a test")
            else:
                res.ok()
            for c in ctrls:
                if c not in covered:
                    res.fail(f"{rid}: control {c} has no test")
            if rcm is not None:
                res.ok() if re.search(rf"^\| {rid} \|", rcm, re.M) else res.fail(f"{rid} is not in risk-control-matrix.md")
            if prog is not None:
                res.ok() if re.search(rf"^## {rid}:", prog, re.M) else res.fail(f"{rid} is not in audit-program.md")

    # 3. High risks
    if scope:
        in_ids = {e["risk_id"] for e in scope["in"]}
        for e in scope["out"]:
            if (e.get("score") or 0) < HIGH_SCORE:
                continue
            rid = e["risk_id"]
            reason = e["comment"] if e["why"].startswith("rejected") else str(e["ratings"].get("scope_reason", "")).strip()
            if not reason:
                res.fail(f"{rid} (score {e['score']}) is out of scope with no recorded reason")
            elif memo is not None and not re.search(rf"^- {rid}:", memo, re.M):
                res.fail(f"{rid} (score {e['score']}) is out of scope but not listed in planning-memo.md")
            else:
                res.ok()
        res.info(f"High risks (score >= {HIGH_SCORE}): " + ", ".join(
            f"{e['risk_id']} {'in' if e['risk_id'] in in_ids else 'out'}" for e in scope["in"] + scope["out"]
            if (e.get("score") or 0) >= HIGH_SCORE))

    # 4. challenges
    cp = a.outputs / "challenges.md"
    if not cp.exists():
        res.fail("challenges.md is missing")
    else:
        header, rows = md_table(cp.read_text(encoding="utf-8"), "#")
        if header is None:
            res.fail("challenges.md has no challenge table (header starting '| # |')")
        for r in rows:
            n = r.get("#", "?")
            cite = " ".join(r.get(k, "") for k in ("Citation", "Challenge"))
            if not EVIDENCE_RE.search(cite):
                res.fail(f"challenge #{n} cites no evidence")
            else:
                res.ok()
            status = r.get("Status", "").strip().lower()
            if not status.startswith(CLOSED):
                res.fail(f"challenge #{n} is not closed (status '{r.get('Status', '')}')")
            else:
                res.ok()
        res.info(f"challenges: {len(rows)}")
    return res.finish()


if __name__ == "__main__":
    run(main)
