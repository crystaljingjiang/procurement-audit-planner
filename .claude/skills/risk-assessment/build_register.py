#!/usr/bin/env python3
"""Build outputs/risk-register.md from the risk-assessor's judgments.

Usage:
  build_register.py [--ratings outputs/risk-ratings.json] [--analytics outputs/analytics.json]
                    [--history outputs/history.json] [--rules outputs/rules.json] [--out-dir outputs]

The agent writes judgments only (risk-ratings.json). This script:
  * resolves every citation: [rule:CPR-NN] in rules.json, [metric:$.path] in
    analytics.json, [history:ID] in history.json;
  * fills every {{$.path}} / {{$.path|fmt}} placeholder from analytics.json
    (fmt: gbp, gbp2, int, num, ratio, raw);
  * checks the likelihood rubric (signals evaluated here, not by the agent),
    the repeat-finding uplift (cited audit must have an adverse opinion) and,
    for financial impact, the council's £ band;
  * computes score = L x I, the Figure 1 matrix label and the Table 4 band
    from history.json, and marks the conflicts inside the scoring method;
  * drops any risk whose likelihood or impact justification has no resolvable
    citation (or that breaks a rubric rule), listing it with the reason;
  * warns on figures typed in prose;
  * writes risk-register.md, auditor-comments.md (decisions kept across
    rewrites) and risk-register.state.json (what the gate and the next
    revision compare against);
  * on a revision, applies the auditor-decision checks: every pending decision
    applied, nothing changed that the auditor did not ask for.

Exit 0 when the register was written (dropped risks are listed, not fatal);
exit 1 on a fatal error, with nothing written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

ADVERSE_OPINIONS = ("limited assurance", "no assurance", "weak", "unsatisfactory", "minimal assurance")
DECISIONS = ("Approve", "Amend", "Reject")
FIN_DIM = "FIN"
FALLBACK_LABELS = ["Very low", "Low", "Medium", "High", "Very high"]
# Tests whose likelihood signal at L3+ must beat the test's own comparator
# (a count in the band alone does not show clustering).
COMPARATOR_REQUIRED = {"threshold_clustering": "comparator"}
PROSE_ID_RE = re.compile(r"\b(?:CPR|AUD|FU|ADV|RT|LIK|IMP|MX|BAND|ESC|SM|DISC|GAP|APP|APT|DIM|TOL|R|T)-[A-Za-z0-9-]*\b|\bL[1-5]\b")
NUMBER_RE = re.compile(r"£\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?|\d[\d,]*(?:\.\d+)?\s?%|\b\d[\d,]*(?:\.\d+)?\b")
TAG_START_RE = re.compile(r"\[(rule|metric|history):")
PLACEHOLDER_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")


class Fatal(Exception):
    pass


# --------------------------------------------------------------------------
# JSON path: $.a.b, ['key with space'], [0], [?key==value]
# --------------------------------------------------------------------------
PATH_TOKEN = re.compile(
    r"\.([A-Za-z_][\w-]*)"
    r"|\[(\d+)\]"
    r"|\['([^']+)'\]"
    r"|\[\?\s*([\w ]+?)\s*==\s*(?:'([^']*)'|(-?[\d.]+))\s*\]"
)


def resolve_path(doc, path: str):
    """Return (ok, value, error)."""
    path = path.strip()
    if not path.startswith("$"):
        return False, None, f"path must start with $: {path}"
    pos, node = 1, doc
    while pos < len(path):
        m = PATH_TOKEN.match(path, pos)
        if not m:
            return False, None, f"cannot parse path at '{path[pos:]}'"
        key, idx, qkey, fkey, fstr, fnum = m.groups()
        if key is not None or qkey is not None:
            k = key if key is not None else qkey
            if not isinstance(node, dict) or k not in node:
                return False, None, f"no key '{k}' at '{path[:pos]}'"
            node = node[k]
        elif idx is not None:
            if not isinstance(node, list) or int(idx) >= len(node):
                return False, None, f"no index [{idx}] at '{path[:pos]}'"
            node = node[int(idx)]
        else:
            if not isinstance(node, list):
                return False, None, f"filter on non-list at '{path[:pos]}'"
            want = fstr if fstr is not None else float(fnum)
            hits = []
            for el in node:
                if isinstance(el, dict) and fkey in el:
                    v = el[fkey]
                    if (isinstance(want, float) and isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == want) \
                            or (isinstance(want, str) and str(v) == want):
                        hits.append(el)
            if len(hits) != 1:
                return False, None, f"filter [?{fkey}=={fstr if fstr is not None else fnum}] matched {len(hits)} items"
            node = hits[0]
        pos = m.end()
    return True, node, None


def fmt_value(v, fmt: str | None) -> str:
    if fmt in (None, "num"):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return str(v)
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
    if fmt == "raw":
        return str(v)
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise ValueError(f"format '{fmt}' needs a number, got {type(v).__name__}")
    if fmt == "gbp":
        return f"£{v:,.0f}"
    if fmt == "gbp2":
        return f"£{v:,.2f}"
    if fmt == "int":
        return f"{v:,.0f}"
    if fmt == "ratio":
        return f"{v:,.2f}"
    raise ValueError(f"unknown format '{fmt}'")


# --------------------------------------------------------------------------
# Text: citation tags (brackets may nest inside metric paths) and placeholders
# --------------------------------------------------------------------------
def find_tags(text: str):
    """Yield (kind, ref, start, end); end is None when unterminated."""
    out, i = [], 0
    while True:
        m = TAG_START_RE.search(text, i)
        if not m:
            return out
        depth, j = 1, m.end()
        while j < len(text) and depth:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
            j += 1
        if depth:
            out.append((m.group(1), text[m.end():].strip(), m.start(), None))
            return out
        out.append((m.group(1), text[m.end():j - 1].strip(), m.start(), j))
        i = j


def split_placeholder(inner: str):
    if "|" in inner:
        p, f = inner.rsplit("|", 1)
        if re.fullmatch(r"\s*\w+\s*", f):
            return p.strip(), f.strip()
    return inner.strip(), None


def typed_figures(text: str) -> list[str]:
    t = PLACEHOLDER_RE.sub(" ", text)
    for kind, ref, s, e in reversed(find_tags(t)):
        t = t[:s] + " " + (t[e:] if e else "")
    t = PROSE_ID_RE.sub(" ", t)
    return [m.group(0).strip() for m in NUMBER_RE.finditer(t)]


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------
def load_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Fatal(f"cannot read {what} at {path}: {e}")


def index_ids(node, out: dict, path="$"):
    if isinstance(node, dict):
        if isinstance(node.get("id"), str):
            out.setdefault(node["id"], node)
        for k, v in node.items():
            index_ids(v, out, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            index_ids(v, out, f"{path}[{i}]")
    return out


def history_label(item: dict) -> str:
    for k in ("audit_title", "review_title", "theme", "label", "band", "topic", "category", "criterion", "item"):
        if item.get(k):
            lab = str(item[k])
            break
    else:
        lab = item.get("id", "")
    ops = [item.get(k) for k in ("opinion", "opinion_report", "opinion_implementation") if item.get(k)]
    if item.get("id", "").startswith("IMP-"):
        lab = f"{item.get('score')} {item.get('label')} – {item.get('dimension')}: {item.get('text')}"
    if ops:
        lab += " – " + " / ".join(ops)
    if item.get("period"):
        lab += f" ({item['period']})"
    return lab


# --------------------------------------------------------------------------
# Scoring method from history.json
# --------------------------------------------------------------------------
def parse_range(s: str):
    s = s.replace("–", "-")
    m = re.match(r"\s*up to\s*(\d+)", s, re.I)
    if m:
        return None, int(m.group(1))
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)\s*$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"\s*(\d+)\s*\+?\s*$", s)
    if m:
        return int(m.group(1)), None
    return None


def money(tok: str, unit: str) -> float:
    return float(tok) * (1_000 if unit.lower() == "k" else 1_000_000)


class Method:
    def __init__(self, history: dict, hist_ids: dict):
        sm = history.get("scoring_method") or {}
        self.notes: list[str] = []          # header lines
        self.conflicts: list[dict] = []
        self.read_ids: set[str] = set()
        self.discs = history.get("discrepancies") or []
        self.fallback = not (sm.get("present") and sm.get("likelihood_scale") and sm.get("matrix") and sm.get("bands"))
        if self.fallback:
            self.l_labels = {i + 1: lab for i, lab in enumerate(FALLBACK_LABELS)}
            self.i_labels = dict(self.l_labels)
            self.notes.append("**Fallback scale.** history.json reports no usable council scoring method "
                              f"({sm.get('reason', 'scoring_method.present is false or incomplete')}). Likelihood and impact use "
                              "1–5 Very low…Very high; score = L × I; no council bands apply.")
            self.fin_bands = []
            return
        self.l_labels = {x["score"]: x["label"] for x in sm["likelihood_scale"]}
        self.read_ids |= {x["id"] for x in sm["likelihood_scale"]}
        self.i_labels, self.fin_bands = {}, []
        for x in sm.get("impact_scale", []):
            self.i_labels.setdefault(x["score"], x["label"])
            self.read_ids.add(x["id"])
        self.matrix = {}
        for row in sm["matrix"]:
            self.read_ids.add(row["id"])
            self.matrix[row["impact"]] = row
        self.bands = []
        for b in sm["bands"]:
            r = parse_range(str(b.get("score_range", "")))
            if r is None:
                raise Fatal(f"cannot parse score_range {b.get('score_range')!r} of {b['id']} in history.json")
            self.bands.append({**b, "lo": r[0], "hi": r[1]})
            self.read_ids.add(b["id"])
        if set(self.l_labels) != {1, 2, 3, 4, 5} or set(self.matrix) != {1, 2, 3, 4, 5}:
            raise Fatal("history.json likelihood scale or matrix does not cover 1-5")
        # matrix arithmetic vs printed scores; every cell inside a Table 4 band
        for i in range(1, 6):
            for l in range(1, 6):
                printed = self.matrix[i]["scores_as_printed"][l - 1]
                if int(printed) != l * i:
                    raise Fatal(f"Figure 1 prints {printed} at L{l} x I{i}; L x I = {l * i}")
                if self.band_for(l * i) is None:
                    raise Fatal(f"score {l * i} (L{l} x I{i}) falls in no Table 4 band")
        self._detect_conflicts(sm, hist_ids)

    def disc_for(self, ids: set[str], min_overlap: int = 1) -> list[str]:
        return [d["id"] for d in self.discs if len(ids & set(d.get("affects") or [])) >= min_overlap]

    def band_for(self, score: int):
        for b in self.bands:
            if (b["lo"] is None or score >= b["lo"]) and (b["hi"] is None or score <= b["hi"]):
                return b
        return None

    def _detect_conflicts(self, sm: dict, hist_ids: dict):
        # C1: matrix label vs Table 4 band name, and matrix label spanning two bands
        pairs, label_bands = {}, {}
        for i in range(1, 6):
            for l in range(1, 6):
                lab = self.matrix[i]["bands_by_likelihood"][l - 1]
                b = self.band_for(l * i)
                label_bands.setdefault(lab, set()).add(b["band"])
                if lab.lower() != b["band"].lower():
                    pairs.setdefault((lab, b["band"]), []).append(f"L{l}xI{i}")
        if pairs:
            ids = {b["id"] for b in self.bands if any(b["band"] == tb for (_, tb) in pairs)}
            names = "; ".join(f"Figure 1 '{a}' = Table 4 '{b}'" for (a, b) in pairs)
            self.conflicts.append({
                "key": "band-names", "discs": self.disc_for(ids),
                "text": f"Band names differ between the matrix and Table 4 ({names}). **Used:** Table 4 band and RAG as "
                        f"the band; the Figure 1 name is shown as 'matrix label'."})
        split = {lab: bs for lab, bs in label_bands.items() if len(bs) > 1}
        if split:
            raise Fatal(f"matrix labels map to more than one Table 4 band: {split}; resolve with the auditor")
        # C2: Corporate Risk Register entry criterion
        self.crr_alt = None
        crr_band = next((b for b in self.bands if "corporate risk register" in str(b.get("escalation", "")).lower()), None)
        for e in sm.get("escalation", []) or []:
            m = re.search(r"score\s*(\d+)\s*or above", str(e.get("criterion", "")), re.I)
            if m and crr_band and crr_band["lo"] is not None and int(m.group(1)) != crr_band["lo"]:
                self.crr_alt = {"id": e["id"], "min": int(m.group(1)), "band": crr_band}
                self.read_ids |= {e["id"]}
                self.conflicts.append({
                    "key": "crr", "discs": self.disc_for({e["id"], crr_band["id"]}),
                    "text": f"Corporate Risk Register entry is printed as Table 4 '{crr_band['band']}' "
                            f"({crr_band['score_range']}) [{crr_band['id']}] and as 'score {m.group(1)} or above' [{e['id']}]. "
                            f"**Used:** Table 4 for the band and escalation. **Marked:** risks scoring "
                            f"{m.group(1)} or above but below {crr_band['lo']} carry ‡ (CRR-level under {e['id']})."})
        # C3: financial impact ranges
        fin = sorted((x for x in sm.get("impact_scale", []) if x["id"].endswith("-" + FIN_DIM)), key=lambda x: x["score"])
        pct = {}
        for x in fin:
            text = x.get("text", "")
            amts = [money(n, u) for n, u in re.findall(r"(\d+(?:\.\d+)?)\s*([kKmM])\b", text)]
            pcts = [float(p) for p in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
            if len(amts) == 2:
                lo, hi = amts
            elif len(amts) == 1 and (">" in text):
                lo, hi = amts[0], None
            elif len(amts) == 1:
                lo, hi = 0.0, amts[0]
            else:
                raise Fatal(f"cannot read a £ range from {x['id']}: {text!r}")
            self.fin_bands.append({"score": x["score"], "id": x["id"], "lo": lo, "hi": hi})
            if len(pcts) == 2:
                pct[x["score"]] = pcts
        shared = [(a["id"], b["id"]) for a, b in zip(self.fin_bands, self.fin_bands[1:]) if a["hi"] is not None and b["lo"] <= a["hi"]]
        pct_overlap = [(s1, s2) for s1 in pct for s2 in pct if s2 == s1 + 1 and pct[s2][0] < pct[s1][1]]
        if shared or pct_overlap:
            ids = {x["id"] for x in fin}
            bits = []  # a discrepancy must touch two FIN levels to be about the ranges
            if shared:
                bits.append("£ ranges of adjacent levels share their end points")
            if pct_overlap:
                bits.append("% of budget ranges overlap (" + ", ".join(
                    f"level {a} up to {pct[a][1]}% vs level {b} from {pct[b][0]}%" for a, b in pct_overlap) + ")")
            self.conflicts.append({
                "key": "fin", "discs": self.disc_for(ids, min_overlap=2),
                "text": "Financial impact ranges conflict: " + "; ".join(bits) + ". **Used:** the £ ranges; a value on a "
                        "shared end point takes the higher level. **Not used:** the % ranges (no annual budget figure is "
                        "in the papers). The £ basis is value exposed to the indicator, not a loss."})
        # C4: numbering of impact labels in prose vs the table
        for note in [sm.get("overview")] + list(sm.get("method_notes") or []):
            if not isinstance(note, dict):
                continue
            for lab, n in re.findall(r"\b(Negligible|Minor|Medium|Major|Critical)(?:\s+impact)?\s*\((\d)\)", note.get("quote", "")):
                table_n = next((s for s, l in self.i_labels.items() if l.lower() == lab.lower()), None)
                if table_n is not None and int(n) != table_n:
                    self.conflicts.append({
                        "key": f"label-{lab}", "discs": self.disc_for({note['id']}),
                        "text": f"'{lab} ({n})' in {note['id']} conflicts with Table 1 / Figure 1, which place {lab} at {table_n}. "
                                f"**Used:** {lab} = {table_n}. **Marked:** the prose numbering is not used."})
        handled = {d for c in self.conflicts for d in c["discs"]}
        for d in self.discs:
            hit = self.read_ids & set(d.get("affects") or [])
            if hit and d["id"] not in handled:
                self.conflicts.append({"key": d["id"], "discs": [d["id"]],
                                       "text": f"{d['id']} touches inputs this build reads ({', '.join(sorted(hit))}) and is "
                                               f"**not resolved by the builder**: {d.get('description', '')}"})

    def fin_level(self, v: float):
        hits = [b for b in self.fin_bands if v >= b["lo"] and (b["hi"] is None or v <= b["hi"])]
        if not hits:
            return None, False
        return max(b["score"] for b in hits), len(hits) > 1


# --------------------------------------------------------------------------
# Risk evaluation
# --------------------------------------------------------------------------
class Ctx:
    def __init__(self, analytics, rules, history):
        self.analytics = analytics
        self.rules = {r["rule_id"]: r for r in rules.get("rules", [])}
        self.hist = index_ids(history, {})


def resolve_tag(ctx: Ctx, kind: str, ref: str):
    if kind == "rule":
        r = ctx.rules.get(ref)
        return (True, f"{ref} (clause {r['clause']}): {r['condition']}", None) if r else (False, None, f"rule {ref} not in rules.json")
    if kind == "history":
        h = ctx.hist.get(ref)
        return (True, f"{ref}: {history_label(h)}", None) if h else (False, None, f"history id {ref} not in history.json")
    ok, v, err = resolve_path(ctx.analytics, ref)
    if not ok:
        return False, None, f"metric {ref}: {err}"
    if isinstance(v, (dict, list)):
        return True, f"`{ref}` (object)", None
    return True, f"`{ref}` = {fmt_value(v, None)}", None


class RiskEval:
    def __init__(self, ctx: Ctx, method: Method, risk: dict, overrides: set[str]):
        self.ctx, self.method, self.r = ctx, method, risk
        self.rid = risk.get("risk_id", "?")
        self.errors: list[str] = []      # -> dropped
        self.warnings: list[str] = []
        self.overridden = self.rid in overrides
        self.metric_notes: dict[str, int] = {}
        self.evidence: list[str] = []
        self.flags: list[str] = []

    def rule_break(self, msg: str):
        if self.overridden:
            self.warnings.append(f"auditor override departs from the rubric: {msg}")
        else:
            self.errors.append(msg)

    def render(self, text: str, field: str) -> tuple[str, int]:
        """Fill placeholders, check tags; return (markdown, n_resolved_citations)."""
        if not isinstance(text, str):
            return "", 0
        for fig in typed_figures(text):
            self.warnings.append(f"{field}: figure typed in prose '{fig}'; use a {{{{$.path}}}} placeholder")

        def ph(m):
            path, fmt = split_placeholder(m.group(1))
            ok, v, err = resolve_path(self.ctx.analytics, path)
            if not ok:
                self.errors.append(f"{field}: placeholder {{{{{m.group(1)}}}}} unresolved: {err}")
                return "⟨unresolved⟩"
            try:
                return fmt_value(v, fmt)
            except ValueError as e:
                self.errors.append(f"{field}: placeholder {{{{{m.group(1)}}}}}: {e}")
                return "⟨unresolved⟩"
        out = PLACEHOLDER_RE.sub(ph, text)
        n_ok, parts, last = 0, [], 0
        for kind, ref, s, e in find_tags(out):
            parts.append(out[last:s])
            if e is None:
                self.warnings.append(f"{field}: unterminated citation '[{kind}:{ref[:40]}'")
                parts.append(out[s:])
                last = len(out)
                break
            ok, desc, err = resolve_tag(self.ctx, kind, ref)
            if ok:
                n_ok += 1
                if desc not in self.evidence:
                    self.evidence.append(desc)
                if kind == "metric":
                    n = self.metric_notes.setdefault(ref, len(self.metric_notes) + 1)
                    parts.append(f"[M{n}]")
                else:
                    parts.append(f"[{ref}]")
            else:
                self.warnings.append(f"{field}: unresolved citation [{kind}:{ref}] ({err})")
                parts.append(f"[{kind}:{ref} ⚠ unresolved]")
            last = e
        parts.append(out[last:])
        return "".join(parts), n_ok

    def signal(self, s: dict):
        def val(x):
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                return True, x, None
            if isinstance(x, str):
                ok, v, err = resolve_path(self.ctx.analytics, x)
                if ok and isinstance(v, (int, float)) and not isinstance(v, bool):
                    return True, v, None
                return False, None, err or f"{x} is not a number"
            return False, None, f"bad operand {x!r}"
        ok1, a, e1 = val(s.get("metric"))
        ok2, b, e2 = val(s.get("than"))
        op = s.get("op")
        if not (ok1 and ok2) or op not in (">", ">=", "<", "<=", "=="):
            return False, f"signal {s} unresolved: {e1 or e2 or 'bad op'}"
        held = {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b, "==": a == b}[op]
        return held, f"{s.get('metric')} {op} {s.get('than')} → {fmt_value(a, None)} {op} {fmt_value(b, None)}"

    def run(self):
        r, m = self.r, self.method
        out = {"risk_id": self.rid, "status": r.get("status", "proposed")}
        out["title"], _ = self.render(r.get("title", ""), "title")
        out["description"], _ = self.render(r.get("description", ""), "description")
        for rid in r.get("rule_ids", []) or []:
            if rid not in self.ctx.rules:
                self.warnings.append(f"rule_ids: {rid} not in rules.json")
        # ---- likelihood
        L = r.get("likelihood") or {}
        base = L.get("base_score")
        if not isinstance(base, int) or not 1 <= base <= 5:
            self.errors.append(f"likelihood.base_score {base!r} not an integer 1-5")
            base = None
        if base and L.get("rubric_level") != f"L{base}":
            self.errors.append(f"likelihood.rubric_level {L.get('rubric_level')!r} does not match base_score {base}")
        out["l_just"], n_l = self.render(L.get("justification", ""), "likelihood.justification")
        if n_l == 0:
            self.errors.append("likelihood justification has no resolvable citation")
        true_sigs, sig_lines = [], []
        for s in L.get("signals", []) or []:
            held, line = self.signal(s)
            sig_lines.append(("✓ " if held else "✗ ") + line)
            if held:
                true_sigs.append(s)
            else:
                self.rule_break(f"likelihood signal does not hold: {line}")
        out["signals"] = sig_lines
        if base:
            tests = {re.match(r"\$\.tests\.(\w+)", str(s.get("metric", ""))).group(1)
                     for s in true_sigs if re.match(r"\$\.tests\.(\w+)", str(s.get("metric", "")))}
            gp = [s for s in true_sigs if "general_procurement" in str(s.get("metric", ""))]
            if base >= 2 and not true_sigs:
                self.rule_break(f"L{base} needs at least one signal that holds")
            if base >= 3 and not gp:
                self.rule_break(f"L{base} needs a signal on the general_procurement population")
            if base >= 3:
                for t, needle in COMPARATOR_REQUIRED.items():
                    if t in tests and not any(needle in str(s.get("than", "")) for s in true_sigs
                                              if str(s.get("metric", "")).startswith(f"$.tests.{t}")):
                        self.rule_break(f"L{base} on {t} needs a signal that beats its {needle}")
            if base >= 4 and len(tests) < 2:
                self.rule_break(f"L{base} needs signals from two different tests (has {sorted(tests) or 'none'})")
            if base == 5 and "[history:" not in L.get("justification", ""):
                self.rule_break("L5 needs a history item recording the condition as having occurred")
        up = L.get("uplift")
        final_l = base
        out["uplift"] = None
        if up and base:
            hid = up.get("history_id")
            item = self.ctx.hist.get(hid)
            ops = [str(item.get(k, "")) for k in ("opinion", "opinion_report", "opinion_implementation")] if item else []
            adverse = [o for o in ops if o.strip().lower().startswith(ADVERSE_OPINIONS)]
            if not item or not (hid.startswith("AUD-") or hid.startswith("FU-")):
                self.rule_break(f"uplift cites {hid!r}, which is not an audit or follow-up in history.json")
            elif not adverse:
                self.rule_break(f"uplift cites {hid} whose opinion is not adverse ({' / '.join(o for o in ops if o) or 'none'})")
            else:
                final_l = min(5, base + 1)
                txt, n_u = self.render(up.get("justification", ""), "likelihood.uplift.justification")
                if n_u == 0:
                    self.warnings.append("uplift justification has no resolvable citation")
                out["uplift"] = f"Repeat finding: +1 likelihood (L{base} → L{final_l}) because {hid} ({adverse[0]}). {txt}"
        # ---- impact
        I = r.get("impact") or {}
        isc = I.get("score")
        if not isinstance(isc, int) or not 1 <= isc <= 5:
            self.errors.append(f"impact.score {isc!r} not an integer 1-5")
            isc = None
        dim = str(I.get("dimension", "")).replace("DIM-", "")
        out["i_just"], n_i = self.render(I.get("justification", ""), "impact.justification")
        if n_i == 0:
            self.errors.append("impact justification has no resolvable citation")
        if isc and not m.fallback:
            want = f"IMP-{isc}-{dim}"
            if want not in self.ctx.hist:
                self.errors.append(f"impact dimension {I.get('dimension')!r} has no council definition {want}")
            elif f"[history:{want}]" not in I.get("justification", ""):
                self.rule_break(f"impact justification must cite the council definition [history:{want}]")
        out["fin"] = None
        if isc and dim == FIN_DIM and not m.fallback:
            basis = I.get("financial_basis")
            ok, v, err = resolve_path(self.ctx.analytics, basis or "")
            if not ok or not isinstance(v, (int, float)):
                self.errors.append(f"financial impact needs a numeric financial_basis path ({err or 'not a number'})")
            else:
                lvl, boundary = m.fin_level(float(v))
                n = self.metric_notes.setdefault(basis, len(self.metric_notes) + 1)
                desc = f"`{basis}` = {fmt_value(v, None)}"
                if desc not in self.evidence:
                    self.evidence.append(desc)
                out["fin"] = f"£ basis {fmt_value(v, 'gbp')} [M{n}] → council £ band level {lvl}" + \
                             (" (on a shared end point: higher level used)" if boundary else "")
                if lvl != isc:
                    self.rule_break(f"impact score {isc} but the £ basis {fmt_value(v, 'gbp')} falls in level {lvl}")
        # ---- other prose
        out["focus"], _ = self.render(r.get("proposed_focus", ""), "proposed_focus")
        out["scope"] = r.get("proposed_scope", "")
        if out["scope"] not in ("in", "out"):
            self.errors.append(f"proposed_scope {out['scope']!r} must be 'in' or 'out'")
        out["scope_reason"], _ = self.render(r.get("scope_reason", ""), "scope_reason")
        for t in r.get("evidence", []) or []:
            self.render(t, "evidence")
        # ---- score
        if base and isc and final_l:
            score = final_l * isc
            out.update(L=final_l, L_base=base, I=isc, score=score,
                       l_label=m.l_labels[final_l], i_label=m.i_labels.get(isc, ""))
            if m.fallback:
                out.update(matrix_label="n/a", band="n/a (fallback scale)")
            else:
                b = m.band_for(score)
                out["matrix_label"] = m.matrix[isc]["bands_by_likelihood"][final_l - 1]
                out["band"] = f"{b['band']} ({b['rag']})" if b.get("rag") and b["rag"] != "not printed" else b["band"]
                out["band_id"] = b["id"]
                if m.crr_alt and m.crr_alt["min"] <= score < (m.crr_alt["band"]["lo"] or 0):
                    self.flags.append("‡")
        out["metric_notes"] = self.metric_notes
        out["evidence"] = self.evidence
        out["flags"] = self.flags
        return out


# --------------------------------------------------------------------------
# Auditor comments file
# --------------------------------------------------------------------------
def parse_comments(path: Path):
    """Return (decisions{rid: {decision, comment, risk}}, other_instructions_text, orphans_text)."""
    if not path.exists():
        return {}, "", ""
    text = path.read_text(encoding="utf-8")
    decisions, header = {}, None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            header = None if not line.strip() else header
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if "Risk ID" in cells and "Decision" in cells:
            header = cells
            continue
        if header and len(cells) == len(header) and re.fullmatch(r"R-\d+", cells[0]):
            row = dict(zip(header, cells))
            d = row.get("Decision", "").strip().strip("*").strip()
            if d and d.capitalize() not in DECISIONS:
                raise Fatal(f"auditor-comments.md: {cells[0]} decision '{d}' must be one of {DECISIONS} or blank")
            decisions[cells[0]] = {"decision": d.capitalize() if d else "", "comment": row.get("Comment", "").strip(),
                                   "risk": row.get("Risk", "")}
    other = re.search(r"^## Other instructions\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return decisions, (other.group(1).strip() if other else ""), text


def write_comments(path: Path, rows, decisions, other, revision, generated, dropped_ids):
    lines = [
        "# Auditor decisions: procurement risk register",
        "",
        f"Register: `outputs/risk-register.md` · revision {revision} · built {generated}",
        "",
        "Put **Approve**, **Amend** or **Reject** in Decision for every row. For Amend, say exactly what to change "
        "in Comment (e.g. \"likelihood 2: the clustering is below its comparator\"). Give a reason for Reject. Do not "
        "use the `|` character in a cell. The planner cannot start until every row has a decision and the register "
        "has been re-issued as a revision that applies them.",
        "",
        "| Risk ID | Risk | L | I | Score | Band | Proposed scope | Decision | Comment |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    seen = set()
    for o in rows:
        d = decisions.get(o["risk_id"], {})
        seen.add(o["risk_id"])
        title = re.sub(r"\s*\|\s*", " / ", re.sub(r"\[[^\]]*\]", "", o["title"])).strip()
        lines.append(f"| {o['risk_id']} | {title} | {o.get('L', '')} | {o.get('I', '')} | {o.get('score', '')} | "
                     f"{o.get('band', '')} | {o['scope']} | {d.get('decision', '')} | {d.get('comment', '')} |")
    lines += ["", "## Other instructions", "",
              other or "<!-- Instructions not tied to one row, e.g. \"add a risk on ...\". The risk-assessor quotes "
                       "the line it acts on. -->", ""]
    orphans = {k: v for k, v in decisions.items() if k not in seen and (v["decision"] or v["comment"])}
    if orphans:
        lines += ["## Decisions for risks no longer in the register", "",
                  "Kept so nothing you wrote is lost. "
                  + (f"Dropped by the builder this run: {', '.join(sorted(dropped_ids))}." if dropped_ids else ""), "",
                  "| Risk ID | Risk | Decision | Comment |", "|---|---|---|---|"]
        for k, v in sorted(orphans.items()):
            lines.append(f"| {k} | {v['risk']} | {v['decision']} | {v['comment']} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# Revision checks
# --------------------------------------------------------------------------
def citations_of(risk: dict) -> list[str]:
    texts = []

    def walk(x):
        if isinstance(x, str):
            texts.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(risk)
    return sorted({f"{k}:{r}" for t in texts for k, r, _, _ in find_tags(t)})


def fingerprint(risk: dict) -> dict:
    L, I = risk.get("likelihood") or {}, risk.get("impact") or {}
    return {
        "title": risk.get("title"), "status": risk.get("status", "proposed"),
        "likelihood": L.get("base_score"), "uplift": (L.get("uplift") or {}).get("history_id"),
        "impact": I.get("score"), "dimension": I.get("dimension"),
        "scope": risk.get("proposed_scope"), "focus": risk.get("proposed_focus"),
        "citations": citations_of(risk),
    }


def diff_fp(a: dict, b: dict) -> list[str]:
    out = []
    for k in a:
        if a[k] != b.get(k):
            if k == "citations":
                add, rem = sorted(set(b[k]) - set(a[k])), sorted(set(a[k]) - set(b[k]))
                out.append("citations " + ", ".join([f"+{x}" for x in add] + [f"-{x}" for x in rem]))
            elif k in ("title", "focus"):
                out.append(f"{k} reworded")
            else:
                out.append(f"{k} {a[k]} → {b.get(k)}")
    return out


def check_revision(ratings, prev, decisions, other_text):
    """Return (revision_no, changes{rid: [diffs]}, overrides set, pending dict) or raise Fatal."""
    rev = ratings.get("revision")
    applied = (prev or {}).get("applied", {})
    pending = {rid: d for rid, d in decisions.items()
               if d["decision"] and [d["decision"], d["comment"]] != applied.get(rid)}
    new = {r["risk_id"]: r for r in ratings["risks"]}
    if not rev:
        if pending:
            raise Fatal("auditor decisions are recorded for " + ", ".join(sorted(pending))
                        + " but risk-ratings.json has no 'revision' block; apply them in a revision")
        if prev and prev.get("revision", 0) > 0:
            raise Fatal(f"the register is already at revision {prev['revision']}; any further change needs a revision block")
        return 0, {}, set(), pending
    if not prev:
        raise Fatal("risk-ratings.json has a revision block but there is no previous build (risk-register.state.json)")
    if rev.get("number") == prev.get("revision", 0) > 0:
        # Rebuild of the current revision (e.g. after a builder update): allowed
        # only when nothing has changed since it was issued.
        same = set(prev.get("risks", {})) == set(new) and all(
            fingerprint(new[rid]) == fp for rid, fp in prev.get("risks", {}).items())
        if pending or not same:
            raise Fatal(f"revision.number {rev['number']} is the current revision; new decisions or changes need "
                        f"revision {rev['number'] + 1}")
        kept = prev.get("revision_overrides", {})
        return rev["number"], prev.get("revision_changes", {}), set(kept), kept
    want = prev.get("revision", 0) + 1
    if rev.get("number") != want:
        raise Fatal(f"revision.number is {rev.get('number')!r}; expected {want}")
    errs = []
    old = prev.get("risks", {})
    undecided = [rid for rid in old if not decisions.get(rid, {}).get("decision")]
    if undecided:
        errs.append("no auditor decision for " + ", ".join(sorted(undecided)))
    listed = {}
    for c in rev.get("changes", []) or []:
        listed.setdefault(c.get("risk_id"), []).append(c)
    changes = {}
    for rid in sorted(set(old) | set(new)):
        if rid in old and rid not in new:
            errs.append(f"{rid} was removed; risks are never deleted, set status 'rejected'")
            continue
        fp_new = fingerprint(new[rid])
        if rid not in old:
            req = [c.get("requested_in", "") for c in listed.get(rid, [])]
            if not any(q and q.strip() in other_text for q in req):
                errs.append(f"{rid} is new but no revision change quotes an auditor instruction from 'Other instructions'")
            changes[rid] = ["added at the auditor's request"]
            continue
        d = diff_fp(old[rid], fp_new)
        dec = pending.get(rid, {}).get("decision")
        if d:
            changes[rid] = d
        if dec == "Approve" and d:
            errs.append(f"{rid} approved by the auditor but changed: {'; '.join(d)}")
        elif dec == "Amend" and not d:
            errs.append(f"{rid}: auditor asked to amend ('{pending[rid]['comment']}') but nothing changed (decision left unapplied)")
        elif dec == "Reject" and fp_new["status"] != "rejected":
            errs.append(f"{rid}: auditor rejected it but its status is '{fp_new['status']}' (decision left unapplied)")
        elif dec is None and d:
            errs.append(f"{rid} changed without an auditor request: {'; '.join(d)}")
        if dec in ("Amend", "Reject") and rid not in listed:
            errs.append(f"{rid}: {dec} applied but not listed in revision.changes")
    for rid, cs in listed.items():
        if rid in old and pending.get(rid, {}).get("decision") not in ("Amend", "Reject"):
            errs.append(f"revision.changes lists {rid} but the auditor did not ask to amend or reject it")
    if errs:
        raise Fatal("revision check failed:\n  - " + "\n  - ".join(errs))
    overrides = {rid for rid, d in pending.items() if d["decision"] in ("Amend", "Reject")}
    return want, changes, overrides, pending


# --------------------------------------------------------------------------
# Register
# --------------------------------------------------------------------------
def render_register(meta, method: Method, built, dropped, rejected, warnings, decisions, rev_info):
    rev, changes, pending, ratings_rev = rev_info
    L = []
    L.append("# Procurement risk register: West Berkshire Council")
    L.append("")
    if rev == 0:
        L.append(f"**Revision 0: draft for auditor review.** Built {meta['generated']} by "
                 "`.claude/skills/risk-assessment/build_register.py` from `outputs/risk-ratings.json`.")
    else:
        L.append(f"**Revision {rev}: applies the auditor's decisions.** Built {meta['generated']}.")
        if ratings_rev.get("summary"):
            L.append("")
            L.append(ratings_rev["summary"])
        L.append("")
        L.append("Changed in this revision:")
        L.append("")
        if changes:
            for rid, d in sorted(changes.items()):
                dec = pending.get(rid, {})
                why = f" (auditor: {dec['decision']}, \"{dec['comment']}\")" if dec else ""
                L.append(f"- {rid}: {'; '.join(d)}{why}")
        else:
            L.append("- nothing; every risk was approved as drafted")
    L.append("")
    L.append("Inputs: " + " · ".join(f"`{k}` sha256 {v}" for k, v in meta["inputs"].items()))
    L.append("")
    L.append("These are **risk indicators to investigate**, not findings of wrongdoing by the council, a service or a supplier.")
    L.append("")
    L.append("## Method")
    L.append("")
    if method.fallback:
        L += [f"- {n}" for n in method.notes]
    else:
        L.append("- Council 5×5 method from the Risk Management Strategy 2024–2027 as recorded in history.json: "
                 "likelihood LIK-1…5, impact IMP-n-DIM (Table 1), matrix MX-I1…5 (Figure 1), bands BAND-* (Table 4).")
        L.append("- Score = likelihood × impact, checked against the scores printed in Figure 1. "
                 "Band and RAG from Table 4; 'matrix label' is the Figure 1 cell name.")
    L.append("- Likelihood follows the rubric in `.claude/skills/risk-assessment/SKILL.md`; each signal is evaluated "
             "here from analytics.json. A repeat finding (a cited audit or follow-up with an adverse opinion) adds one "
             "point, capped at 5, and is stated on the risk.")
    L.append("- Every figure is filled from analytics.json; [M*] marks a metric listed under the risk's evidence.")
    if method.conflicts:
        L.append("")
        L.append("**Conflicts inside the council's scoring method** (one value used, the other marked; nothing resolved silently):")
        L.append("")
        for c in method.conflicts:
            refs = f" [{', '.join(c['discs'])}]" if c["discs"] else ""
            L.append(f"- {c['text']}{refs}")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append("| ID | Risk | L | I | Score | Matrix label | Band | Scope |")
    L.append("|---|---|---|---|---|---|---|---|")
    for o in built:
        fl = " ".join(o["flags"])
        L.append(f"| {o['risk_id']} | {o['title']} | {o['L']} | {o['I']} | {o['score']}{(' ' + fl) if fl else ''} | "
                 f"{o['matrix_label']} | {o['band']} | {o['scope']} |")
    if any(o["flags"] for o in built) and method.crr_alt:
        L.append("")
        L.append(f"‡ CRR-level under {method.crr_alt['id']} ('score {method.crr_alt['min']} or above'), not under Table 4. See Method.")
    for o in built:
        L.append("")
        L.append(f"## {o['risk_id']}: {o['title']}")
        L.append("")
        if o.get("override"):
            L.append(f"> **Auditor override (revision {rev}):** {o['override']}")
            L.append("")
        if o["description"]:
            L.append(o["description"])
            L.append("")
        upl = f" (base L{o['L_base']} + repeat finding)" if o["L"] != o["L_base"] else ""
        L.append(f"- **Likelihood {o['L']} – {o['l_label']}{upl}.** {o['l_just']}")
        if o["signals"]:
            L.append("  - Signals: " + "; ".join(o["signals"]))
        if o["uplift"]:
            L.append(f"  - {o['uplift']}")
        L.append(f"- **Impact {o['I']} – {o['i_label']}.** {o['i_just']}")
        if o["fin"]:
            L.append(f"  - {o['fin']}")
        L.append(f"- **Score {o['score']}**: matrix label {o['matrix_label']}; band {o['band']}"
                 + (f"; ‡ CRR-level under {method.crr_alt['id']}" if "‡" in o["flags"] else "") + ".")
        L.append("- **Evidence:**")
        notes = {v: k for k, v in o["metric_notes"].items()}
        for e in o["evidence"]:
            mref = next((f"M{n} " for n, p in notes.items() if e.startswith(f"`{p}`")), "")
            L.append(f"  - {mref}{e}")
        L.append(f"- **Proposed focus:** {o['focus']}")
        L.append(f"- **Proposed scope:** {o['scope']}" + (f". {o['scope_reason']}" if o["scope_reason"] else ""))
    if rejected:
        L += ["", "## Rejected by the auditor", ""]
        for o in rejected:
            L.append(f"- {o['risk_id']}: {o['title']}. {o.get('override', '')}")
    L += ["", "## Risks excluded by the builder", ""]
    if dropped:
        L.append("Not rated: each lacked a resolvable citation or broke a rubric rule. The risk-assessor must fix or withdraw them.")
        L.append("")
        for rid, title, errs in dropped:
            L.append(f"- **{rid}** {title}: " + "; ".join(errs))
    else:
        L.append("None.")
    if warnings:
        L += ["", "## Build notes", ""]
        L += [f"- {w}" for w in warnings]
    L += ["", "## Auditor decisions", "",
          "Record a decision for every risk in `outputs/auditor-comments.md` (Approve, Amend or Reject, with a comment "
          "for Amend and Reject), then ask for the risk-assessor to be re-run. It re-issues this register as the next "
          "revision, applying exactly what you asked and nothing else. The audit program is not built until every "
          "risk is decided and applied.", "",
          "| Risk ID | Decision recorded | Comment |", "|---|---|---|"]
    for o in built + rejected:
        d = decisions.get(o["risk_id"], {})
        L.append(f"| {o['risk_id']} | {d.get('decision') or '_pending_'} | {d.get('comment', '')} |")
    L.append("")
    return "\n".join(L)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ratings", default="outputs/risk-ratings.json")
    ap.add_argument("--analytics", default="outputs/analytics.json")
    ap.add_argument("--history", default="outputs/history.json")
    ap.add_argument("--rules", default="outputs/rules.json")
    ap.add_argument("--out-dir", default="outputs")
    a = ap.parse_args()
    out = Path(a.out_dir)
    paths = {"ratings": Path(a.ratings), "analytics": Path(a.analytics), "history": Path(a.history), "rules": Path(a.rules)}
    try:
        ratings = load_json(paths["ratings"], "risk ratings")
        analytics = load_json(paths["analytics"], "analytics")
        history = load_json(paths["history"], "history")
        rules = load_json(paths["rules"], "rules")
        if not isinstance(ratings.get("risks"), list) or not ratings["risks"]:
            raise Fatal("risk-ratings.json has no 'risks' list")
        ids = [r.get("risk_id") for r in ratings["risks"]]
        bad = [i for i in ids if not isinstance(i, str) or not re.fullmatch(r"R-\d{2,}", i)]
        if bad or len(set(ids)) != len(ids):
            raise Fatal(f"risk_ids must be unique and look like R-01: {ids}")
        ctx = Ctx(analytics, rules, history)
        method = Method(history, ctx.hist)

        state_path, comments_path = out / "risk-register.state.json", out / "auditor-comments.md"
        prev = json.loads(state_path.read_text()) if state_path.exists() else None
        decisions, other_text, _ = parse_comments(comments_path)
        rev, changes, overrides, pending = check_revision(ratings, prev, decisions, other_text)

        built, rejected, dropped, warnings = [], [], [], []
        for r in ratings["risks"]:
            ev = RiskEval(ctx, method, r, overrides)
            o = ev.run()
            warnings += [f"{ev.rid}: {w}" for w in ev.warnings]
            if ev.errors:
                dropped.append((ev.rid, o["title"], ev.errors))
                continue
            if r["risk_id"] in overrides:
                d = pending[r["risk_id"]]
                o["override"] = f"{d['decision']}: \"{d['comment']}\". Changed: {'; '.join(changes.get(r['risk_id'], []))}."
            (rejected if o["status"] == "rejected" else built).append(o)
    except Fatal as e:
        print(f"FATAL {e}")
        print("Nothing written.")
        return 1

    generated = dt.datetime.now().isoformat(timespec="seconds")
    meta = {"generated": generated, "inputs": {str(p): sha(p) for k, p in paths.items()}}
    out.mkdir(parents=True, exist_ok=True)
    reg = render_register(meta, method, built, dropped, rejected, warnings, decisions,
                          (rev, changes, pending, ratings.get("revision") or {}))
    (out / "risk-register.md").write_text(reg, encoding="utf-8")
    write_comments(comments_path, built + rejected, decisions, other_text, rev, generated, {d[0] for d in dropped})
    applied = dict((prev or {}).get("applied", {}))
    if rev > 0:
        applied.update({rid: [d["decision"], d["comment"]] for rid, d in decisions.items() if d["decision"]})
    rated = {o["risk_id"] for o in built + rejected}
    state = {
        "revision": rev, "generated_at": generated,
        "risks": {r["risk_id"]: fingerprint(r) for r in ratings["risks"] if r["risk_id"] in rated},
        "dropped": [d[0] for d in dropped],
        "applied": applied,
        "revision_changes": changes if rev > 0 else {},
        "revision_overrides": {rid: pending[rid] for rid in overrides} if rev > 0 else {},
        "scores": {o["risk_id"]: {k: o.get(k) for k in ("L", "L_base", "I", "score", "matrix_label", "band", "band_id", "flags", "scope", "status")}
                   for o in built + rejected},
        "all_decided": all(decisions.get(rid, {}).get("decision") for rid in rated),
        "register_sha256": hashlib.sha256(reg.encode()).hexdigest(),
    }
    state_path.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"revision {rev}: {len(built)} rated, {len(rejected)} rejected, {len(dropped)} dropped, {len(warnings)} warning(s)")
    for rid, _, errs in dropped:
        print(f"DROPPED {rid}: " + "; ".join(errs))
    for w in warnings:
        print(f"WARN  {w}")
    for c in method.conflicts:
        print(f"CONFLICT {c['key']}: {', '.join(c['discs']) or '-'}")
    print(f"wrote {out / 'risk-register.md'}, {comments_path}, {state_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
