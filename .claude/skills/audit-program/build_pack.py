#!/usr/bin/env python3
"""Build the audit planning pack from the planner's judgments.

Usage:
  build_pack.py --gate [--outputs DIR]     # approval gate only
  build_pack.py [--outputs DIR] [--plan DIR/audit-plan.json]

All inputs are read from --outputs (default: outputs): rules.json,
analytics.json, history.json, risk-ratings.json, risk-register.md,
risk-register.state.json, auditor-comments.md, analytics-full/*.csv and,
outside --gate, audit-plan.json.

Gate (always first): the register must be a revision (>= 1) whose file still
matches the builder's state, every rated risk must have an auditor decision,
and every decision must have been applied in that revision. Approved scope =
risks decided Approve/Amend, not rejected, with proposed scope "in".

Pack build:
  * the plan must cover exactly the approved scope;
  * every control cites >= 1 rule; every control has >= 1 test; every test
    cites a rule or a metric and lists >= 1 PBC item;
  * every citation and {{$.path}} placeholder resolves; no typed figures and
    no accusatory words in prose;
  * every rule in rules.json is cited by an in-scope risk, a control or a test,
    or is listed in rules_not_tested with a reason (never both);
  * samples are drawn deterministically from analytics-full, sized by risk
    score, verified against spend-clean.csv and written to samples/<test>.csv;
  * renders planning-memo.md, risk-control-matrix.md, audit-program.md (ending
    with the PBC list) and pack-figures.json (every figure this script
    computed, plus every analytics/register figure it printed).

Exit 0 when the pack (or the gate) passes; exit 1 with FAIL lines otherwise,
and nothing is written.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "risk-assessment"))
from build_register import (PLACEHOLDER_RE, find_tags, fingerprint, fmt_value, history_label,  # noqa: E402
                            index_ids, parse_comments, resolve_path, split_placeholder, typed_figures)

# Sample size by register score (units: rows, groups or suppliers per test).
SAMPLE_SIZES = [(15, 25), (8, 15), (4, 10), (1, 5)]
SUPPLIER_PAYMENTS_DEFAULT = 3
ACCUSATORY = re.compile(r"\b(?<!anti-)(fraud\w*|corrupt\w*|theft|steal\w*|wrongdoing|illegal\w*|unlawful\w*|deliberate\w*|"
                        r"intentional\w*|dishonest\w*|misconduct|embezzl\w*|collusion|colluding|kickback\w*|"
                        r"rigg(?:ed|ing)|abuse\w*|guilty|breach(?:ed|es)? (?:by|of) (?:the )?supplier)\b", re.I)
ID_RE = {"control": re.compile(r"C-\d{2}-\d+$"), "test": re.compile(r"T-\d{2}-\d+$")}
UNIT_KEY = {"row": "row_id", "group": "row_ids", "supplier": "supplier_norm"}
NOTICE_FILES = {"high_value_suppliers.csv", "expired_notice_spend.csv", "spend_vs_award.csv", "near-matches.csv",
                "supplier-match.csv", "notices-clean.csv"}


class Fail(Exception):
    def __init__(self, msgs):
        self.msgs = msgs if isinstance(msgs, list) else [msgs]


def size_for(score: int) -> int:
    for lo, n in SAMPLE_SIZES:
        if score >= lo:
            return n
    return SAMPLE_SIZES[-1][1]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def load(p: Path, what: str):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Fail(f"cannot read {what} ({p}): {e}")


# --------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------
def gate(out: Path) -> dict:
    errs = []
    state_p, reg_p, com_p = out / "risk-register.state.json", out / "risk-register.md", out / "auditor-comments.md"
    for p in (state_p, reg_p, com_p, out / "risk-ratings.json"):
        if not p.exists():
            raise Fail(f"gate: {p} is missing; run the risk-assessor first")
    state = load(state_p, "register state")
    ratings = load(out / "risk-ratings.json", "risk ratings")
    if not state.get("revision", 0) >= 1:
        errs.append(f"gate: the register is revision {state.get('revision', 0)}, a draft; the auditor's decisions must be "
                    "applied in a revision (re-run the risk-assessor)")
    if hashlib.sha256(reg_p.read_bytes()).hexdigest() != state.get("register_sha256"):
        errs.append("gate: risk-register.md does not match the builder's state (edited by hand, or not rebuilt)")
    if "scores" not in state:
        errs.append("gate: register state has no scores; rebuild the register with the current build_register.py")
    decisions, _, _ = parse_comments(com_p)
    rated = list((state.get("scores") or state.get("risks") or {}).keys())
    undecided = [r for r in rated if not decisions.get(r, {}).get("decision")]
    if undecided:
        errs.append("gate: no auditor decision for " + ", ".join(undecided))
    applied = state.get("applied", {})
    unapplied = [r for r, d in decisions.items() if d["decision"] and [d["decision"], d["comment"]] != applied.get(r)]
    if unapplied:
        errs.append("gate: decisions recorded after the last revision are not applied yet: " + ", ".join(sorted(unapplied)))
    current = {r["risk_id"]: r for r in ratings.get("risks", [])}
    drift = [rid for rid, fp in (state.get("risks") or {}).items() if rid not in current or fingerprint(current[rid]) != fp]
    if drift:
        errs.append("gate: risk-ratings.json changed after the register was built: " + ", ".join(drift))
    if errs:
        raise Fail(errs)
    scope_in, scope_out = [], []
    for rid in rated:
        sc, d = state["scores"][rid], decisions[rid]
        r = current[rid]
        entry = {"risk_id": rid, "decision": d["decision"], "comment": d["comment"], **sc, "ratings": r}
        if d["decision"] in ("Approve", "Amend") and sc.get("status") != "rejected" and sc.get("scope") == "in":
            scope_in.append(entry)
        else:
            why = ("rejected by the auditor" if d["decision"] == "Reject" or sc.get("status") == "rejected"
                   else "approved as out of scope")
            scope_out.append({**entry, "why": why})
    return {"revision": state["revision"], "built": state.get("generated_at"), "in": scope_in, "out": scope_out}


# --------------------------------------------------------------------------
# Prose: citations, placeholders, language
# --------------------------------------------------------------------------
class Prose:
    def __init__(self, ctx):
        self.ctx = ctx
        self.errors: list[str] = []
        self.metrics: dict[str, int] = {}       # path -> footnote number (shared across the pack)
        self.from_analytics: dict[str, dict] = {}

    def resolve_tag(self, kind, ref):
        if kind == "rule":
            r = self.ctx["rules"].get(ref)
            return (True, None) if r else (False, f"rule {ref} not in rules.json")
        if kind == "history":
            return (True, None) if ref in self.ctx["hist"] else (False, f"history id {ref} not in history.json")
        ok, v, err = resolve_path(self.ctx["analytics"], ref)
        if ok:
            self.from_analytics.setdefault(ref, {"path": ref, "value": v if not isinstance(v, (dict, list)) else "(object)"})
        return ok, err

    def render(self, text, where: str, need=None):
        """Return (markdown, set of (kind, ref) resolved)."""
        if not isinstance(text, str) or not text.strip():
            self.errors.append(f"{where}: text missing")
            return "", set()
        for fig in typed_figures(text):
            self.errors.append(f"{where}: figure typed in prose '{fig}'; use a {{{{$.path}}}} placeholder")
        for m in ACCUSATORY.finditer(PLACEHOLDER_RE.sub(" ", text)):
            self.errors.append(f"{where}: '{m.group(0)}' is not indicator language")

        def ph(m):
            path, fmt = split_placeholder(m.group(1))
            ok, v, err = resolve_path(self.ctx["analytics"], path)
            if not ok:
                self.errors.append(f"{where}: placeholder {{{{{m.group(1)}}}}} unresolved: {err}")
                return "⟨unresolved⟩"
            try:
                s = fmt_value(v, fmt)
            except ValueError as e:
                self.errors.append(f"{where}: {e}")
                return "⟨unresolved⟩"
            self.from_analytics.setdefault(path, {"path": path, "value": v})
            self.from_analytics[path].setdefault("rendered", sorted(set()))
            self.from_analytics[path]["rendered"] = sorted(set(self.from_analytics[path]["rendered"]) | {s})
            return s
        out = PLACEHOLDER_RE.sub(ph, text)
        cited, parts, last = set(), [], 0
        for kind, ref, s, e in find_tags(out):
            parts.append(out[last:s])
            if e is None:
                self.errors.append(f"{where}: unterminated citation '[{kind}:{ref[:40]}'")
                last = len(out)
                break
            ok, err = self.resolve_tag(kind, ref)
            if not ok:
                self.errors.append(f"{where}: unresolved citation [{kind}:{ref}] ({err})")
            else:
                cited.add((kind, ref))
            if kind == "metric":
                n = self.metrics.setdefault(ref, len(self.metrics) + 1)
                parts.append(f"[A{n}]")
            else:
                parts.append(f"[{ref}]")
            last = e
        parts.append(out[last:])
        if need and not any(k in need for k, _ in cited):
            self.errors.append(f"{where}: must cite at least one {' or '.join(need)} that resolves")
        return "".join(parts), cited

    def sources_md(self):
        if not self.metrics:
            return []
        lines = ["", "## Sources", ""]
        for p, n in sorted(self.metrics.items(), key=lambda x: x[1]):
            v = self.from_analytics.get(p, {}).get("value")
            lines.append(f"- A{n}: `{p}` in analytics.json" + (f" = {fmt_value(v, None)}" if v not in (None, "(object)") else ""))
        return lines


# --------------------------------------------------------------------------
# Samples
# --------------------------------------------------------------------------
def apply_filter(df: pd.DataFrame, flt: dict, analytics, where: str, errs: list) -> pd.DataFrame:
    for col, cond in (flt or {}).items():
        if col not in df.columns:
            errs.append(f"{where}: filter column '{col}' not in source (columns: {', '.join(df.columns)})")
            continue

        def val(v):
            if isinstance(v, str) and v.startswith("$."):
                ok, x, err = resolve_path(analytics, v)
                if not ok:
                    errs.append(f"{where}: filter value {v}: {err}")
                return x
            return v
        if isinstance(cond, dict):
            for op, v in cond.items():
                v = val(v)
                ops = {">": df[col] > v, ">=": df[col] >= v, "<": df[col] < v, "<=": df[col] <= v, "!=": df[col] != v}
                if op not in ops:
                    errs.append(f"{where}: filter op '{op}' not one of {list(ops)}")
                    continue
                df = df[ops[op]]
        elif isinstance(cond, list):
            df = df[df[col].isin([val(v) for v in cond])]
        else:
            v = val(cond)
            df = df[df[col].astype(str) == str(v)] if df[col].dtype == object else df[df[col] == v]
    return df


def draw_sample(test, risk, full_dir: Path, spend: pd.DataFrame, analytics, errs: list):
    tid, rec = test["test_id"], test.get("sample")
    where = f"{tid}.sample"
    src = str(rec.get("source", ""))
    if "/" in src or not src.endswith(".csv") or not (full_dir / src).exists():
        errs.append(f"{where}: source '{src}' is not a file in analytics-full/")
        return None
    unit = rec.get("unit")
    if unit not in UNIT_KEY:
        errs.append(f"{where}: unit must be one of {list(UNIT_KEY)}")
        return None
    df = pd.read_csv(full_dir / src)
    if UNIT_KEY[unit] not in df.columns:
        errs.append(f"{where}: unit '{unit}' needs column '{UNIT_KEY[unit]}' in {src}")
        return None
    n_err = len(errs)
    df = apply_filter(df, rec.get("filter"), analytics, where, errs)
    sort = rec.get("sort") or []
    by, asc = [], []
    for s in sort:
        if s.get("by") not in df.columns:
            errs.append(f"{where}: sort column '{s.get('by')}' not in {src}")
        else:
            by.append(s["by"])
            asc.append(not s.get("desc", False))
    if len(errs) > n_err:
        return None
    tiebreak = [c for c in ("row_id", "supplier_norm", "window_start", "amount") if c in df.columns and c not in by]
    df = df.sort_values(by + tiebreak, ascending=asc + [True] * len(tiebreak), kind="mergesort")
    auto = size_for(risk["score"])
    n = rec.get("n", "auto")
    if n != "auto":
        if not isinstance(n, int) or n < auto:
            errs.append(f"{where}: n must be 'auto' or an integer >= {auto} (the size for score {risk['score']})")
            return None
    else:
        n = auto
    population = len(df)
    picked = df.head(n)
    rows = []   # (unit_key, row_id, source_amount, source_supplier)
    if unit == "row":
        for _, r in picked.iterrows():
            rows.append((r["row_id"], r["row_id"], r.get("Net amount"), r.get("Supplier name")))
    elif unit == "group":
        for i, (_, r) in enumerate(picked.iterrows(), start=1):
            try:
                ids = ast.literal_eval(r["row_ids"])
            except (ValueError, SyntaxError):
                errs.append(f"{where}: unreadable row_ids in {src}")
                return None
            key = f"G{i:03d}|{r.get('supplier_norm', 'group')}|{r.get('window_start', r.get('dates', ''))}"
            rows += [(key, rid, None, None) for rid in ids]
    else:
        k = rec.get("payments_per_supplier", SUPPLIER_PAYMENTS_DEFAULT)
        if not isinstance(k, int) or k < 1:
            errs.append(f"{where}: payments_per_supplier must be a positive integer")
            return None
        for s in picked["supplier_norm"]:
            pays = spend[spend["supplier_norm"] == s].sort_values(["Net amount", "row_id"], ascending=[False, True]).head(k)
            if pays.empty:
                errs.append(f"{where}: supplier {s} has no payments in spend-clean.csv")
            rows += [(s, rid, None, None) for rid in pays["row_id"]]
    # verify every transaction against spend-clean.csv
    idx = spend.set_index("row_id")
    out = []
    for key, rid, amt, sup in rows:
        if rid not in idx.index:
            errs.append(f"{where}: transaction {rid} is not in spend-clean.csv")
            continue
        row = idx.loc[rid]
        if amt is not None and round(float(row["Net amount"]), 2) != round(float(amt), 2):
            errs.append(f"{where}: {rid} amount {amt} differs from spend-clean.csv {row['Net amount']}")
        if sup is not None and str(row["Supplier name"]) != str(sup):
            errs.append(f"{where}: {rid} supplier differs from spend-clean.csv")
        out.append({"test_id": tid, "risk_id": risk["risk_id"], "sample_unit": key, "row_id": rid,
                    **{c: row[c] for c in spend.columns if c != "row_id"}})
    sample = pd.DataFrame(out)
    if not sample.empty and sample["row_id"].duplicated().any():
        sample = sample.drop_duplicates("row_id")
    return {"df": sample, "source": src, "unit": unit, "population": population, "n_target": n,
            "units_drawn": len(picked), "transactions": len(sample),
            "gbp": round(float(sample["Net amount"].sum()), 2) if not sample.empty else 0.0,
            "filter": rec.get("filter") or {}, "sort": sort,
            "payments_per_supplier": rec.get("payments_per_supplier", SUPPLIER_PAYMENTS_DEFAULT) if unit == "supplier" else None}


def recipe_words(s) -> str:
    flt = "; ".join(f"{k} {json.dumps(v) if isinstance(v, (dict, list)) else '= ' + str(v)}" for k, v in s["filter"].items()) or "none"
    srt = ", ".join(f"{x['by']} {'descending' if x.get('desc') else 'ascending'}" for x in s["sort"]) or "file order"
    unit = {"row": "transactions", "group": "groups (all payments in each)",
            "supplier": f"suppliers (largest {s['payments_per_supplier']} payments each)"}[s["unit"]]
    return f"`analytics-full/{s['source']}`; filter: {flt}; sort: {srt}; first {s['n_target']} {unit}"


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def build(out: Path, plan_path: Path):
    scope = gate(out)
    rules_doc = load(out / "rules.json", "rules")
    analytics = load(out / "analytics.json", "analytics")
    history = load(out / "history.json", "history")
    plan = load(plan_path, "audit plan")
    full_dir = out / "analytics-full"
    if not (full_dir / "spend-clean.csv").exists():
        raise Fail(f"{full_dir}/spend-clean.csv is missing")
    spend = pd.read_csv(full_dir / "spend-clean.csv")
    ctx = {"rules": {r["rule_id"]: r for r in rules_doc.get("rules", [])}, "analytics": analytics,
           "hist": index_ids(history, {})}
    P = Prose(ctx)
    errs: list[str] = []

    approved = {r["risk_id"]: r for r in scope["in"]}
    planned = {r.get("risk_id"): r for r in plan.get("risks", [])}
    for rid in sorted(set(approved) - set(planned)):
        errs.append(f"approved risk {rid} is missing from audit-plan.json")
    for rid in sorted(set(planned) - set(approved)):
        errs.append(f"audit-plan.json covers {rid}, which is not in the approved scope")

    memo = plan.get("memo") or {}
    memo_md = {k: P.render(memo.get(k), f"memo.{k}")[0] for k in ("objective", "approach", "limitations")}

    seen_ids, cited_rules = set(), set()
    for rid in sorted(approved):
        r = approved[rid]["ratings"]
        cited_rules |= set(r.get("rule_ids") or [])
        for t in [r.get(k, "") for k in ("title", "description", "proposed_focus", "scope_reason")] + \
                 [(r.get("likelihood") or {}).get("justification", ""), (r.get("impact") or {}).get("justification", "")]:
            cited_rules |= {ref for kind, ref, _, _ in find_tags(str(t)) if kind == "rule"}

    risks_out = []
    for rid in sorted(set(approved) & set(planned)):
        pr, ar = planned[rid], approved[rid]
        controls, tests = pr.get("controls") or [], pr.get("tests") or []
        if not controls:
            errs.append(f"{rid}: no expected controls")
        if not tests:
            errs.append(f"{rid}: no test steps")
        cids = set()
        cs_out = []
        for c in controls:
            cid = c.get("control_id", "?")
            if not ID_RE["control"].match(cid) or cid in seen_ids or not cid.startswith(f"C-{rid[2:]}-"):
                errs.append(f"{rid}: control id '{cid}' must be unique and look like C-{rid[2:]}-1")
            seen_ids.add(cid)
            cids.add(cid)
            md, cited = P.render(c.get("description"), f"{cid}.description", need={"rule"})
            rules = sorted(ref for k, ref in cited if k == "rule")
            cited_rules |= set(rules)
            cs_out.append({"control_id": cid, "md": md, "rules": rules, "tests": []})
        ts_out = []
        for t in tests:
            tid = t.get("test_id", "?")
            if not ID_RE["test"].match(tid) or tid in seen_ids or not tid.startswith(f"T-{rid[2:]}-"):
                errs.append(f"{rid}: test id '{tid}' must be unique and look like T-{rid[2:]}-1")
            seen_ids.add(tid)
            md, cited = P.render(t.get("step"), f"{tid}.step", need={"rule", "metric"})
            cited_rules |= {ref for k, ref in cited if k == "rule"}
            links = t.get("control_ids") or []
            if not links:
                errs.append(f"{tid}: control_ids is empty")
            for cid in links:
                if cid not in cids:
                    errs.append(f"{tid}: control {cid} is not a control of {rid}")
                else:
                    next(c for c in cs_out if c["control_id"] == cid)["tests"].append(tid)
            pbc = t.get("pbc") or []
            if not pbc:
                errs.append(f"{tid}: no PBC items")
            pbc_md = [P.render(x, f"{tid}.pbc[{i}]")[0] for i, x in enumerate(pbc)]
            smp = None
            if t.get("sample") is None:
                if len(str(t.get("no_sample_reason", "")).strip()) < 8:
                    errs.append(f"{tid}: sample is null; give no_sample_reason")
                no_sample = P.render(t.get("no_sample_reason"), f"{tid}.no_sample_reason")[0] if t.get("no_sample_reason") else ""
            else:
                no_sample = ""
                smp = draw_sample(t, ar, full_dir, spend, analytics, errs)
                if smp is not None and smp["transactions"] == 0:
                    errs.append(f"{tid}: the sample recipe selects no transactions")
            ts_out.append({"test_id": tid, "md": md, "controls": links, "pbc": pbc_md, "sample": smp,
                           "no_sample": no_sample})
        for c in cs_out:
            if not c["tests"]:
                errs.append(f"{c['control_id']}: no test covers this control")
        risks_out.append({"risk_id": rid, "approved": ar, "controls": cs_out, "tests": ts_out})

    # rule accounting
    all_rules = set(ctx["rules"])
    not_tested = {}
    for i, x in enumerate(plan.get("rules_not_tested") or []):
        rid = x.get("rule_id")
        if rid not in all_rules:
            errs.append(f"rules_not_tested[{i}]: {rid} is not in rules.json")
            continue
        if len(str(x.get("reason", "")).strip()) < 8:
            errs.append(f"rules_not_tested: {rid} needs a reason")
        not_tested[rid] = P.render(x.get("reason"), f"rules_not_tested.{rid}")[0]
    for rid in sorted(set(not_tested) & cited_rules):
        errs.append(f"{rid} is cited by the plan or an in-scope risk and also listed as not tested")
    unaccounted = sorted(all_rules - cited_rules - set(not_tested), key=lambda x: int(x.split("-")[1]))
    if unaccounted:
        errs.append("rules neither cited by an in-scope risk, control or test nor listed as not tested: " + ", ".join(unaccounted))

    errs += P.errors
    if errs:
        raise Fail(errs)
    return scope, plan, risks_out, not_tested, cited_rules, P, memo_md, spend


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def write_pack(out: Path, scope, plan, risks_out, not_tested, cited_rules, P: Prose, memo_md, analytics):
    gen = dt.datetime.now().isoformat(timespec="seconds")
    figs = {"generated_at": gen, "computed": [], "from_register": [], "from_analytics": []}

    def fig(name, value, where):
        figs["computed"].append({"name": name, "value": value, "where": where})
        return value

    n_in = fig("risks_in_scope", len(scope["in"]), ["planning-memo.md"])
    n_out = fig("risks_out_of_scope", len(scope["out"]), ["planning-memo.md"])
    for e in scope["in"] + scope["out"]:
        for k in ("L", "I", "score"):
            figs["from_register"].append({"name": f"{e['risk_id']}.{k}", "value": e.get(k),
                                          "source": "risk-register.state.json"})
    samples_dir = out / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    for old in samples_dir.glob("T-*.csv"):
        old.unlink()
    tot_tx = 0
    for r in risks_out:
        for t in r["tests"]:
            s = t["sample"]
            if s is None:
                continue
            s["df"].to_csv(samples_dir / f"{t['test_id']}.csv", index=False)
            base = f"sample.{t['test_id']}"
            fig(f"{base}.size_for_score", s["n_target"], ["planning-memo.md", "audit-program.md"])
            fig(f"{base}.population", s["population"], ["planning-memo.md", "audit-program.md"])
            fig(f"{base}.units_drawn", s["units_drawn"], ["planning-memo.md", "audit-program.md"])
            fig(f"{base}.transactions", s["transactions"], ["planning-memo.md", "audit-program.md"])
            fig(f"{base}.gbp", s["gbp"], ["planning-memo.md", "audit-program.md"])
            tot_tx += s["transactions"]
    fig("sample.transactions_total", tot_tx, ["planning-memo.md"])
    pbc_list = []
    for r in risks_out:
        for t in r["tests"]:
            for p in t["pbc"]:
                hit = next((x for x in pbc_list if x["text"] == p), None)
                if hit:
                    hit["tests"].append(t["test_id"])
                else:
                    pbc_list.append({"text": p, "tests": [t["test_id"]]})
    fig("pbc_items", len(pbc_list), ["audit-program.md"])
    fig("rules_total", len(cited_rules | set(not_tested)), ["risk-control-matrix.md"])
    fig("rules_cited", len(cited_rules), ["risk-control-matrix.md"])
    fig("rules_not_tested", len(not_tested), ["risk-control-matrix.md"])
    for lo, n in SAMPLE_SIZES:
        fig(f"sample_size_rule.score_{lo}_plus", n, ["planning-memo.md"])

    disclaimer = ("These are **risk indicators to investigate**, not findings of wrongdoing by the council, a "
                  "service or a supplier. A sampled transaction is selected because it carries an indicator, "
                  "not because anything is assumed to be wrong with it.")
    basis = (f"Basis: risk register revision {scope['revision']} (built {scope['built']}), auditor decisions in "
             f"`outputs/auditor-comments.md`, plan `outputs/audit-plan.json`. Built {gen} by "
             "`.claude/skills/audit-program/build_pack.py`.")

    # planning memo
    M = ["# Audit planning memo: procurement, West Berkshire Council", "", basis, "", disclaimer, "",
         "## Objective", "", memo_md["objective"], "", "## Scope", "",
         f"{n_in} risk(s) in scope, {n_out} out of scope, as decided by the auditor.", "",
         "| Risk | L | I | Score | Band | Decision | Tests | Sample transactions |", "|---|---|---|---|---|---|---|---|"]
    for r in risks_out:
        a = r["approved"]
        tx = fig(f"sample.{r['risk_id']}.transactions",
                 sum(t["sample"]["transactions"] for t in r["tests"] if t["sample"]), ["planning-memo.md"])
        title = P.render(a["ratings"]["title"], f"{r['risk_id']}.title")[0]
        M.append(f"| {r['risk_id']}: {title} | {a['L']} | {a['I']} | {a['score']}{' ‡' if '‡' in (a.get('flags') or []) else ''} | "
                 f"{a['band']} | {a['decision']} | {', '.join(t['test_id'] for t in r['tests'])} | {tx} |")
    if scope["out"]:
        M += ["", "Out of scope:", ""]
        M += [f"- {e['risk_id']}: {e['why']}" + (f" (\"{e['comment']}\")" if e["comment"] else "") for e in scope["out"]]
    M += ["", "## Approach", "", memo_md["approach"], "", "## Sampling", "",
          "Samples are targeted, not random: each test draws the highest-indicator items from the full flagged "
          "population in `outputs/analytics-full/`, sized by the risk's register score, and every transaction is "
          "checked against `spend-clean.csv`. Files: `outputs/samples/<test>.csv`.", "",
          "| Register score | Items per test |", "|---|---|"]
    prev = None
    for lo, n in SAMPLE_SIZES:
        M.append(f"| {lo}{'–' + str(prev - 1) if prev else '+'} | {n} |")
        prev = lo
    M += ["", "| Test | Source | Population | Drawn | Transactions | Value £ |", "|---|---|---|---|---|---|"]
    for r in risks_out:
        for t in r["tests"]:
            s = t["sample"]
            if s:
                M.append(f"| {t['test_id']} | {s['source']} | {s['population']:,} | {s['units_drawn']:,} | "
                         f"{s['transactions']:,} | {s['gbp']:,.2f} |")
            else:
                M.append(f"| {t['test_id']} | no transaction sample | – | – | – | – |")
    M.append(f"\nTotal sampled transactions: {tot_tx:,}.")
    auto_lim = ["The spend data covers payments over £500 only; split-purchase and duplicate indicators are lower bounds."]
    if any(t["sample"] and t["sample"]["source"] in NOTICE_FILES for r in risks_out for t in r["tests"]):
        auto_lim.append("Notice-based samples rest on Contracts Finder notices, which are not a contract register; "
                        "'no notice found' is checked against the council's own register in fieldwork.")
    M += ["", "## Limitations", "", memo_md["limitations"], ""] + [f"- {x}" for x in auto_lim]
    M += P.sources_md()
    (out / "planning-memo.md").write_text("\n".join(M) + "\n", encoding="utf-8")

    # risk-control matrix
    R = ["# Risk-control matrix: procurement, West Berkshire Council", "", basis, "", disclaimer, "",
         "| Risk | Score | Expected control | Rules | Tests |", "|---|---|---|---|---|"]
    for r in risks_out:
        a = r["approved"]
        for c in r["controls"]:
            R.append(f"| {r['risk_id']} | {a['score']} ({a['band']}) | {c['control_id']}: {c['md']} | "
                     f"{', '.join(c['rules'])} | {', '.join(c['tests'])} |")
    R += ["", "## Rule coverage", "",
          f"Every rule in `outputs/rules.json` is accounted for: {len(cited_rules)} cited by an in-scope risk, a control "
          f"or a test; {len(not_tested)} not tested, with the reason below.", "",
          "| Rule | Clause | Reason not tested |", "|---|---|---|"]
    rules = load(out / "rules.json", "rules")
    clause = {x["rule_id"]: x["clause"] for x in rules["rules"]}
    for rid in sorted(not_tested, key=lambda x: int(x.split("-")[1])):
        R.append(f"| {rid} | {clause.get(rid, '')} | {not_tested[rid]} |")
    R += P.sources_md()
    (out / "risk-control-matrix.md").write_text("\n".join(R) + "\n", encoding="utf-8")

    # audit program
    A = ["# Audit program: procurement, West Berkshire Council", "", basis, "", disclaimer]
    for r in risks_out:
        a = r["approved"]
        A += ["", f"## {r['risk_id']}: {P.render(a['ratings']['title'], r['risk_id'])[0]}", "",
              f"Score {a['score']} ({a['band']}); controls: "
              + "; ".join(f"{c['control_id']} {c['md']}" for c in r["controls"])]
        for t in r["tests"]:
            A += ["", f"### {t['test_id']} (tests {', '.join(t['controls'])})", "", t["md"], ""]
            s = t["sample"]
            if s:
                A.append(f"- **Sample:** {recipe_words(s)}. Population {s['population']:,}; drawn {s['units_drawn']:,}; "
                         f"{s['transactions']:,} transactions, £{s['gbp']:,.2f}. File: `outputs/samples/{t['test_id']}.csv`.")
            else:
                A.append(f"- **Sample:** none. {t['no_sample']}")
            A.append("- **PBC:** " + "; ".join(t["pbc"]))
    A += P.sources_md()
    A += ["", "## PBC list", "", "Documents and information to request from the council before fieldwork.", "",
          "| # | Item | For tests |", "|---|---|---|"]
    for i, p in enumerate(pbc_list, start=1):
        A.append(f"| {i} | {p['text']} | {', '.join(p['tests'])} |")
    (out / "audit-program.md").write_text("\n".join(A) + "\n", encoding="utf-8")

    figs["from_analytics"] = sorted(P.from_analytics.values(), key=lambda x: x["path"])
    (out / "pack-figures.json").write_text(json.dumps(figs, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return tot_tx, len(pbc_list)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", action="store_true", help="run only the approval gate")
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--plan", default=None)
    a = ap.parse_args()
    out = Path(a.outputs)
    try:
        if a.gate:
            s = gate(out)
            print(f"GATE OPEN: register revision {s['revision']}; in scope: "
                  f"{', '.join(e['risk_id'] for e in s['in']) or 'none'}; out of scope: "
                  f"{', '.join(e['risk_id'] + ' (' + e['why'] + ')' for e in s['out']) or 'none'}")
            return 0
        res = build(out, Path(a.plan) if a.plan else out / "audit-plan.json")
        analytics = load(out / "analytics.json", "analytics")
        tot, npbc = write_pack(out, *res[:7], analytics)
    except Fail as f:
        print("GATE CLOSED" if a.gate else "PACK NOT BUILT")
        for m in f.msgs:
            print(f"FAIL  {m}")
        print("Nothing written.")
        return 1
    scope = res[0]
    print(f"pack built: {len(scope['in'])} risk(s) in scope, {sum(len(r['tests']) for r in res[2])} test(s), "
          f"{tot} sampled transaction(s), {npbc} PBC item(s)")
    print(f"wrote {out}/planning-memo.md, risk-control-matrix.md, audit-program.md, pack-figures.json, samples/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
