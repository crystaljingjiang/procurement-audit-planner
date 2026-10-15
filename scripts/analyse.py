"""Risk-indicator tests over the cleaned spend population.

Reads outputs/rules.json and outputs/analytics-full/{spend-clean.csv,
notices-clean.csv, cleaning-log.json}. Writes outputs/analytics.json and
full lists to outputs/analytics-full/. Every figure is computed here.
"""
import datetime as dt
import difflib
import json
import os
import re
import sys
from collections import Counter, defaultdict

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, "outputs", "analytics-full")
RULES = os.path.join(ROOT, "outputs", "rules.json")

CAVEAT = ("**contracts.csv holds published *notices*, not a contract register.** It holds "
          "awards published on Contracts Finder in roughly the last five years. A "
          "contract awarded earlier (e.g. long-running waste or highways contracts), "
          "one advertised only on Find a Tender, a framework call-off recorded under "
          "another buyer, or an exempt placement will have no notice here. **\"No "
          "notice found\" is therefore an indicator to check against the council's "
          "contract register, never evidence of off-contract spend.** Say so in every "
          "output that reports it.")
PUBLICATION_NOTE = ("Contracts Finder does not carry smaller awards; only suppliers at or above the "
                    "publication threshold are classed, and results must never be used to question smaller suppliers.")

GENERIC = set("""AND OF THE SERVICES SERVICE GROUP CARE COMPANY HOMES HOME HOUSE UNIVERSITY COUNCIL TRUST
SOLUTIONS CONSULTANCY CONSULTING ASSOCIATES PARTNERSHIP NETWORK CENTRE CENTER TRAVEL CARS COACHES TAXIS
CONSTRUCTION HEALTHCARE HEALTH SCHOOL SCHOOLS EDUCATION SUPPORT LIVING CHILDREN CHILDRENS SEN BERKSHIRE
WEST SOUTH NORTH EAST READING NEWBURY THATCHAM HUNGERFORD SOUTHERN SYSTEMS SOFTWARE HOUSING SECURITY
CLEANING FOSTERING COMMUNITY BUSINESS MANAGEMENT FACILITIES SUPPLIES CATERING TRANSPORT ENGINEERING HIRE
PROPERTY PROPERTIES VALLEY""".split())

# A threshold is competition-triggering when a rule citing it requires multiple
# quotes or a tender (App B rows B1/B2/C). A single quote (App B row A) is not competition.
RE_COMPETITION = re.compile(r"send invitations? to (?:quote|tender)|at least (?:two|three|five|\d+)\b.{0,60}(?:quot|tender)|competitive tender", re.I)
TAGS = ["general_procurement", "care_or_education_placement", "grant", "agency_staff", "premises_non_procurement"]
WINDOW_DAYS = 30
DUP_DAYS = 7
RATIO_FLAG = 1.25


def stop(msg):
    print(f"STOP: {msg}")
    sys.exit(1)


def r2(x):
    return round(float(x), 2)


# ---------------------------------------------------------------- thresholds
def derive_thresholds(rules):
    by_val = defaultdict(lambda: {"rule_ids": [], "low_incl": [], "high_incl": [], "actions": []})
    for r in rules["rules"]:
        if r.get("type") not in ("threshold", "approver", "anti-avoidance"):
            continue
        for side in ("low", "high"):
            v = r.get(f"threshold_{side}")
            if isinstance(v, (int, float)) and v is not None:
                d = by_val[int(v)]
                d["rule_ids"].append(r["rule_id"])
                d[f"{side}_incl"].append((r["rule_id"], r.get(f"threshold_{side}_inclusive")))
                d["actions"].append((r["rule_id"], r.get("required_action") or ""))
    out = []
    for v in sorted(by_val):
        d = by_val[v]
        # trigger_inclusive: an amount exactly equal to v belongs to the upper tier
        lows = [i for _, i in d["low_incl"] if i is not None]
        highs = [i for _, i in d["high_incl"] if i is not None]
        if lows:
            trig = Counter(lows).most_common(1)[0][0]
        elif highs:
            trig = not Counter(highs).most_common(1)[0][0]
        else:
            trig = True
        conflict = len(set(lows)) > 1 or (lows and highs and any(h == lows[0] for h in highs))
        comp_rules = sorted({rid for rid, a in d["actions"] if RE_COMPETITION.search(a)})
        quote_rules = sorted({rid for rid, a in d["actions"] if re.search(r"quot|tender", a, re.I)})
        out.append({"value": v, "inclusive": bool(trig),
                    "inclusive_meaning": "amount equal to value is in the upper tier" if trig else "only amounts above value are in the upper tier",
                    "competition_triggering": bool(comp_rules), "competition_rule_ids": comp_rules,
                    "quote_or_tender_rule_ids": quote_rules,
                    "rule_ids": sorted(set(d["rule_ids"])),
                    "bounds": {"as_low": d["low_incl"], "as_high": d["high_incl"]},
                    "inclusivity_conflict": bool(conflict)})
    return out


def below(amount, t):
    return amount < t["value"] if t["inclusive"] else amount <= t["value"]


def at_or_over(total, t):
    return total >= t["value"] if t["inclusive"] else total > t["value"]


# ---------------------------------------------------------------- matching
def distinctive(name):
    return {tok for tok in name.split() if tok not in GENERIC and len(tok) >= 3}


def build_matcher(spend_names, notice_names):
    sp_tok = {n: distinctive(n) for n in spend_names}
    no_tok = {n: distinctive(n) for n in notice_names}
    sp_count = Counter(t for s in sp_tok.values() for t in s)
    no_count = Counter(t for s in no_tok.values() for t in s)
    notice_set = set(notice_names)

    def match_supplier(name):
        if name in notice_set:
            return "exact", name, 1.0
        best, best_r = None, 0.0
        for n in notice_names:
            rr = difflib.SequenceMatcher(None, name, n).ratio()
            if rr > best_r:
                best, best_r = n, rr
        if best_r >= 0.85:
            return "near_ratio", best, round(best_r, 3)
        a = sp_tok.get(name, distinctive(name))
        for n in notice_names:
            b = no_tok[n]
            if not a or not b:
                continue
            small, large = (a, b) if len(a) <= len(b) else (b, a)
            if small <= large:
                if len(small) >= 2:
                    return "near_contain", n, round(difflib.SequenceMatcher(None, name, n).ratio(), 3)
                tok = next(iter(small))
                if sp_count[tok] == 1 and no_count[tok] == 1:
                    return "near_contain", n, round(difflib.SequenceMatcher(None, name, n).ratio(), 3)
        return "none", "", round(best_r, 3)
    return match_supplier


# ---------------------------------------------------------------- helpers
def row_view(df, cols=None):
    cols = cols or ["row_id", "Supplier name", "Net amount", "pay_date", "Service", "Narrative", "tag"]
    recs = df[cols].to_dict("records")
    for rec in recs:
        for k, v in rec.items():
            if isinstance(v, float):
                rec[k] = r2(v)
            elif not isinstance(v, (int, str, bool, list, type(None))):
                rec[k] = str(v)
    return recs


def tag_split(df, amount="Net amount"):
    g = df.groupby("tag")[amount].agg(["count", "sum"])
    return {t: {"n": int(g.loc[t, "count"]), "gbp": r2(g.loc[t, "sum"])} for t in g.index}


def main():
    if not os.path.exists(RULES):
        stop("outputs/rules.json missing")
    rules = json.load(open(RULES))
    log = json.load(open(os.path.join(FULL, "cleaning-log.json")))
    s = pd.read_csv(os.path.join(FULL, "spend-clean.csv"), parse_dates=["pay_date"])
    pop = log["population"]
    months = pop["months_covered"]
    factor = 12 / months
    win_start = s["pay_date"].min()

    rule_by_clause = {r["clause"]: r["rule_id"] for r in rules["rules"]}
    cite = {
        "anti_splitting": [r["rule_id"] for r in rules["rules"] if r.get("type") == "anti-avoidance"],
        "extension_app_c_row_d": [r["rule_id"] for r in rules["rules"] if r["clause"] == "App C row D"],
        "variation_app_c_row_e": [r["rule_id"] for r in rules["rules"] if r["clause"] == "App C row E"],
        "placements_app_c_row_f": [r["rule_id"] for r in rules["rules"] if r["clause"] == "App C row F"],
        "grants_as_contracts": "clause 1.6.2 (in rules.json excluded list; no rule_id)",
        "publication_over_500": [r["rule_id"] for r in rules["rules"] if r["clause"] == "5.1.1"],
    }

    thresholds = derive_thresholds(rules)
    comp = [t for t in thresholds if t["competition_triggering"]]
    if not comp:
        stop("no competition-triggering threshold derivable from rules.json")
    skipped = []
    for name, p in rules["parameters"].items():
        if p.get("value") is None:
            refs = sorted({r["rule_id"] for r in rules["rules"]
                           if name in (r.get("threshold_low_ref"), r.get("threshold_high_ref"))})
            skipped.append({"test": "all threshold tests", "tier": name, "rule_ids": refs,
                            "reason": f"{name} is null in rules.json parameters"})
    skipped.append({"test": "high_value_suppliers / off_contract", "tier": "statutory",
                    "reason": "STATUTORY_THRESHOLD_GOODS_SERVICES is null"})

    tests = {}

    # ------------------------------------------------ 1 threshold_clustering
    tc = {"parameters": {"band": "0.9*T <= amount < T (<= T where only amounts above T are in the upper tier)",
                         "comparator": "T <= amount < 1.1*T (T < amount <= 1.1*T if exclusive)",
                         "baseline": "0.5*T <= amount < 1.5*T"},
          "rule_ids": sorted({rid for t in thresholds for rid in t["rule_ids"]}), "per_threshold": []}
    all_band = []
    for t in thresholds:
        T = t["value"]
        a = s["Net amount"]
        if t["inclusive"]:
            band = (a >= 0.9 * T) & (a < T)
            compm = (a >= T) & (a < 1.1 * T)
        else:
            band = (a >= 0.9 * T) & (a <= T)
            compm = (a > T) & (a <= 1.1 * T)
        base = (a >= 0.5 * T) & (a < 1.5 * T)
        b = s[band]
        all_band.append(b.assign(threshold=T))
        conc = b.groupby("Supplier name")["Net amount"].agg(["count", "sum"]).sort_values(["count", "sum"], ascending=False).head(20)
        entry = {"threshold": T, "inclusive": t["inclusive"], "rule_ids": t["rule_ids"],
                 "band_count": int(band.sum()), "band_gbp": r2(b["Net amount"].sum()),
                 "comparator_count": int(compm.sum()), "comparator_gbp": r2(s.loc[compm, "Net amount"].sum()),
                 "baseline_count": int(base.sum()),
                 "band_share_of_baseline": round(int(band.sum()) / int(base.sum()), 4) if base.sum() else None,
                 "band_by_tag": tag_split(b) if len(b) else {},
                 "top20_suppliers_in_band": [{"supplier": i, "n": int(r["count"]), "gbp": r2(r["sum"])} for i, r in conc.iterrows()],
                 "top20": row_view(b.sort_values("Net amount", ascending=False).head(20))}
        if T <= s["Net amount"].min():
            entry["note"] = "band lies below the population floor (expenditure over £500 only): empty by construction"
        tc["per_threshold"].append(entry)
    pd.concat(all_band).to_csv(os.path.join(FULL, "threshold_clustering.csv"), index=False)
    tc["full_list"] = "outputs/analytics-full/threshold_clustering.csv"
    tests["threshold_clustering"] = tc

    # ------------------------------------------------ 2 split_purchases
    sp = {"parameters": {"window_days": WINDOW_DAYS, "window": "anchor payment date d, payments with d <= date < d + 30 days",
                         "min_payments": 2, "each_payment": "below T", "window_total": "at or over T",
                         "dedupe": "highest-total window per supplier per threshold",
                         "thresholds": [t["value"] for t in comp]},
          "rule_ids": sorted(set(cite["anti_splitting"] + [rid for t in comp for rid in t["competition_rule_ids"]])),
          "note": "population is expenditure over £500 only, so results are a lower bound; placement windows reported separately because periodic care fees legitimately recur",
          "per_threshold": []}
    sp_rows = []
    for t in comp:
        T = t["value"]
        cand = s[s["Net amount"].map(lambda x: below(x, t))]
        best = {}
        for sup, g in cand.groupby("supplier_norm"):
            if len(g) < 2:
                continue
            g = g.sort_values("pay_date")
            dates = g["pay_date"].tolist()
            for i, d in enumerate(dates):
                w = g[(g["pay_date"] >= d) & (g["pay_date"] < d + pd.Timedelta(days=WINDOW_DAYS))]
                if len(w) < 2:
                    continue
                tot = w["Net amount"].sum()
                if at_or_over(tot, t) and (sup not in best or tot > best[sup][0]):
                    best[sup] = (tot, w)
        wins = []
        for sup, (tot, w) in best.items():
            tags = w["tag"].unique().tolist()
            wins.append({"threshold": T, "supplier_norm": sup, "supplier": w["Supplier name"].iloc[0],
                         "window_start": str(w["pay_date"].min().date()), "window_end": str(w["pay_date"].max().date()),
                         "n_payments": int(len(w)), "total_gbp": r2(tot),
                         "distinct_amounts": int(w["Net amount"].nunique()),
                         "services": sorted(w["Service"].unique().tolist()),
                         "tag": tags[0] if len(tags) == 1 else "mixed:" + "+".join(sorted(tags)),
                         "row_ids": w["row_id"].tolist()})
        wdf = pd.DataFrame(wins)
        sp_rows.extend(wins)
        entry = {"threshold": T, "rule_ids": t["competition_rule_ids"] + cite["anti_splitting"], "windows": len(wins)}
        if len(wdf):
            entry.update({"distinct_suppliers": int(wdf["supplier_norm"].nunique()), "gbp": r2(wdf["total_gbp"].sum()),
                          "by_tag": {k: {"windows": int(len(v)), "gbp": r2(v["total_gbp"].sum())} for k, v in wdf.groupby("tag")}})
            gp = wdf[wdf["tag"] == "general_procurement"]
            pl = wdf[wdf["tag"] == "care_or_education_placement"]
            entry["headline_general_procurement"] = {"windows": int(len(gp)), "suppliers": int(gp["supplier_norm"].nunique()),
                                                     "gbp": r2(gp["total_gbp"].sum()),
                                                     "top20": gp.sort_values("total_gbp", ascending=False).head(20).to_dict("records")}
            entry["care_or_education_placement"] = {"windows": int(len(pl)), "gbp": r2(pl["total_gbp"].sum()),
                                                    "top20": pl.sort_values("total_gbp", ascending=False).head(20).to_dict("records")}
            entry["top20_all"] = wdf.sort_values("total_gbp", ascending=False).head(20).to_dict("records")
        sp["per_threshold"].append(entry)
    pd.DataFrame(sp_rows).to_csv(os.path.join(FULL, "split_purchases.csv"), index=False)
    sp["full_list"] = "outputs/analytics-full/split_purchases.csv"
    sp["thresholds_not_tested"] = [{"value": t["value"], "reason": "not competition-triggering (no rule citing it requires multiple quotes or a tender)"}
                                   for t in thresholds if not t["competition_triggering"]]
    tests["split_purchases"] = sp

    # ------------------------------------------------ 3 high_value_suppliers
    T_low = min(comp, key=lambda t: t["value"])
    agg = s.groupby("supplier_norm").agg(supplier=("Supplier name", lambda x: x.value_counts().index[0]),
                                          total_gbp=("Net amount", "sum"), n_payments=("row_id", "count"),
                                          services=("Service", lambda x: "; ".join(sorted(x.unique()))),
                                          narratives=("Narrative", lambda x: "; ".join(sorted(x.unique()))))
    agg["annualised_estimate"] = agg["total_gbp"] * factor
    tag_gbp = s.groupby(["supplier_norm", "tag"])["Net amount"].sum().unstack(fill_value=0)
    agg["dominant_tag"] = tag_gbp.idxmax(axis=1)
    agg["n_tags"] = (tag_gbp > 0).sum(axis=1)
    agg["spans_several_tags"] = agg["n_tags"] > 1
    hv = agg[agg["annualised_estimate"].map(lambda x: at_or_over(x, T_low))].copy()
    hv = hv.sort_values("annualised_estimate", ascending=False)

    def hv_table(df):
        out = df.head(20).reset_index()[["supplier_norm", "supplier", "annualised_estimate", "total_gbp", "n_payments",
                                         "services", "narratives", "dominant_tag", "spans_several_tags"]]
        out["annualised_estimate"] = out["annualised_estimate"].round(2)
        out["total_gbp"] = out["total_gbp"].round(2)
        return out.rename(columns={"annualised_estimate": "annualised estimate"}).to_dict("records")

    hvs = {"parameters": {"threshold": T_low["value"], "inclusive": T_low["inclusive"],
                          "annualisation": f"total x 12/{months} (annualised estimate)", "months_covered": months},
           "rule_ids": T_low["competition_rule_ids"],
           "statutory_tier": {"skipped": True, "reason": "STATUTORY_THRESHOLD_GOODS_SERVICES is null"},
           "suppliers": int(len(hv)), "total_gbp_in_window": r2(hv["total_gbp"].sum()),
           "annualised_estimate_gbp": r2(hv["annualised_estimate"].sum()),
           "by_dominant_tag": {k: {"suppliers": int(len(v)), "gbp_in_window": r2(v["total_gbp"].sum()),
                                   "annualised_estimate_gbp": r2(v["annualised_estimate"].sum()),
                                   "spanning_several_tags": int(v["spans_several_tags"].sum())}
                               for k, v in hv.groupby("dominant_tag")},
           "note": "population for which contract evidence is requested from the council during fieldwork (PBC list), whatever the notices say",
           "full_list": "outputs/analytics-full/high_value_suppliers.csv"}
    hvs["headline_general_procurement"] = {"suppliers": int((hv["dominant_tag"] == "general_procurement").sum()),
                                           "top20": hv_table(hv[hv["dominant_tag"] == "general_procurement"])}
    hvs["other_groups_top20"] = {k: hv_table(v) for k, v in hv.groupby("dominant_tag") if k != "general_procurement"}
    tests["high_value_suppliers"] = hvs

    # ------------------------------------------------ matching + off_contract
    con = log["contracts"]
    contracts_present = bool(con.get("contracts_present")) and not con.get("treated_as_absent")
    register_present = bool(log.get("register_present"))
    matching = {}
    if contracts_present:
        n = pd.read_csv(os.path.join(FULL, "notices-clean.csv"), parse_dates=["Contract start date", "Contract end date"])
        n["supplier_norm"] = n["supplier_norm"].fillna("")
        active = n[n["active"]]
        active_names = sorted(set(active["supplier_norm"]) - {""})
        matcher = build_matcher(sorted(agg.index), active_names)
        res = {name: matcher(name) for name in agg.index}
        agg["match_class"] = [res[k][0] for k in agg.index]
        agg["match_candidate"] = [res[k][1] for k in agg.index]
        agg["match_score"] = [res[k][2] for k in agg.index]
        sm = agg.reset_index()[["supplier_norm", "supplier", "total_gbp", "annualised_estimate", "dominant_tag",
                                "match_class", "match_candidate", "match_score"]]
        sm.to_csv(os.path.join(FULL, "supplier-match.csv"), index=False)
        near = sm[sm["match_class"].isin(["near_ratio", "near_contain"])]
        near.to_csv(os.path.join(FULL, "near-matches.csv"), index=False)
        vc = agg["match_class"].value_counts()
        matching = {c: int(vc.get(c, 0)) for c in ["exact", "near_ratio", "near_contain", "none"]}
        matching.update({"against": "active notice suppliers", "spend_suppliers": int(len(agg)),
                         "near_matches_file": "outputs/analytics-full/near-matches.csv",
                         "supplier_match_file": "outputs/analytics-full/supplier-match.csv",
                         "note": "near matches are candidates for the auditor to confirm and are never counted as matches"})

        hv2 = agg.loc[hv.index].copy()
        hv2.reset_index().rename(columns={"annualised_estimate": "annualised estimate"}).to_csv(
            os.path.join(FULL, "high_value_suppliers.csv"), index=False)
        un = hv2[hv2["match_class"] != "exact"]
        un_none = hv2[hv2["match_class"] == "none"]
        gp_un = hv2[(hv2["match_class"] == "none") & (hv2["dominant_tag"] == "general_procurement")].sort_values("annualised_estimate", ascending=False)
        tests["off_contract"] = {
            "parameters": {"threshold": T_low["value"], "population": "high_value_suppliers (annualised estimate at or above the lowest competition-triggering threshold)",
                           "match_set": "active Contracts Finder notices (end date on/after window start or blank)"},
            "rule_ids": T_low["competition_rule_ids"] + cite["placements_app_c_row_f"],
            "contracts_present": contracts_present, "register_present": register_present,
            "caveat": CAVEAT, "publication_note": PUBLICATION_NOTE,
            "by_match_class": {k: {"suppliers": int(len(v)), "annualised_estimate_gbp": r2(v["annualised_estimate"].sum()),
                                   "gbp_in_window": r2(v["total_gbp"].sum())} for k, v in hv2.groupby("match_class")},
            "no_notice_found_by_tag": {k: {"suppliers": int(len(v)), "annualised_estimate_gbp": r2(v["annualised_estimate"].sum())}
                                       for k, v in un_none.groupby("dominant_tag")},
            "headline_general_procurement_no_notice_found": {"suppliers": int(len(gp_un)),
                                                             "annualised_estimate_gbp": r2(gp_un["annualised_estimate"].sum()),
                                                             "top20": hv_table(gp_un)},
            "placement_note": "care/education placements may be exempt from competition under App C row F (individually chosen placements); reported separately",
            "full_list": "outputs/analytics-full/high_value_suppliers.csv (match_class column)"}

        # -------------------------------------------- 5 expired_notice_spend
        name_to_notices = defaultdict(list)
        for _, r in n.iterrows():
            if r["supplier_norm"]:
                name_to_notices[r["supplier_norm"]].append(r)
        exp_rows = []
        for sup in agg.index:
            ns = name_to_notices.get(sup)
            if not ns:
                continue
            if all(bool(r["ended_before_window"]) for r in ns):
                latest = max(ns, key=lambda r: r["Contract end date"])
                exp_rows.append({"supplier_norm": sup, "supplier": agg.loc[sup, "supplier"],
                                 "total_gbp": r2(agg.loc[sup, "total_gbp"]),
                                 "annualised estimate": r2(agg.loc[sup, "annualised_estimate"]),
                                 "n_payments": int(agg.loc[sup, "n_payments"]),
                                 "dominant_tag": agg.loc[sup, "dominant_tag"],
                                 "latest_end_date": str(latest["Contract end date"].date()),
                                 "notice_id": latest["Notice Identifier"], "notice_title": latest["Title"],
                                 "matched_notices": len(ns)})
        edf = pd.DataFrame(exp_rows)
        edf.to_csv(os.path.join(FULL, "expired_notice_spend.csv"), index=False)
        tests["expired_notice_spend"] = {
            "parameters": {"match": "exact normalised name against all council notices",
                           "condition": "every matched notice has Contract end date before the spend window start",
                           "window_start": str(win_start.date())},
            "rule_ids": cite["extension_app_c_row_d"],
            "suppliers": int(len(edf)),
            "gbp_in_window": r2(edf["total_gbp"].sum()) if len(edf) else 0,
            "annualised_estimate_gbp": r2(edf["annualised estimate"].sum()) if len(edf) else 0,
            "caveat": "Indicator of spend after notice expiry without an approved extension; a newer contract or extension may exist with no notice. " + CAVEAT,
            "top20": edf.sort_values("annualised estimate", ascending=False).head(20).to_dict("records") if len(edf) else [],
            "full_list": "outputs/analytics-full/expired_notice_spend.csv"}

        # -------------------------------------------- 6 spend_vs_award
        cand = active[(active["suppliers_on_notice"] == 1) & (active["Awarded Value"] > 0)]
        sva, unusable = [], []
        for sup in agg.index:
            if agg.loc[sup, "match_class"] != "exact":
                continue
            ns = cand[cand["supplier_norm"] == sup]
            if len(ns) != 1:
                continue
            r = ns.iloc[0]
            if pd.isna(r["Contract start date"]) or pd.isna(r["Contract end date"]):
                unusable.append({"supplier_norm": sup, "notice_id": r["Notice Identifier"], "reason": "missing start or end date"})
                continue
            years = (r["Contract end date"] - r["Contract start date"]).days / 365.25
            if years <= 0:
                unusable.append({"supplier_norm": sup, "notice_id": r["Notice Identifier"], "reason": "non-positive term"})
                continue
            rate = r["Awarded Value"] / years
            ann = agg.loc[sup, "annualised_estimate"]
            sva.append({"supplier_norm": sup, "supplier": agg.loc[sup, "supplier"], "notice_id": r["Notice Identifier"],
                        "notice_title": r["Title"], "awarded_value": r2(r["Awarded Value"]),
                        "contract_years": round(years, 3), "award_annual_rate": r2(rate),
                        "annualised estimate": r2(ann), "ratio": round(ann / rate, 3),
                        "flag": bool(ann / rate >= RATIO_FLAG)})
        vdf = pd.DataFrame(sva)
        vdf.to_csv(os.path.join(FULL, "spend_vs_award.csv"), index=False)
        fl = vdf[vdf["flag"]] if len(vdf) else vdf
        tests["spend_vs_award"] = {
            "parameters": {"ratio": "annualised estimate / (Awarded Value / contract years)", "flag_at": RATIO_FLAG,
                           "eligible": "exact match to exactly one active single-supplier notice with Awarded Value > 0"},
            "rule_ids": cite["variation_app_c_row_e"],
            "suppliers_compared": int(len(vdf)), "flagged": int(len(fl)),
            "flagged_annualised_estimate_gbp": r2(fl["annualised estimate"].sum()) if len(fl) else 0,
            "unusable_notices": unusable,
            "caveat": "Indicator of spend beyond the award without an approved variation; award values may be estimates or maxima, and the annualised estimate extrapolates three months.",
            "top20": vdf.sort_values("ratio", ascending=False).head(20).to_dict("records") if len(vdf) else [],
            "full_list": "outputs/analytics-full/spend_vs_award.csv"}
    else:
        reason = "no contracts.csv or contract register in data/"
        agg.loc[hv.index].reset_index().rename(columns={"annualised_estimate": "annualised estimate"}).to_csv(
            os.path.join(FULL, "high_value_suppliers.csv"), index=False)
        tests["off_contract"] = {"skipped": True, "reason": reason}
        skipped.append({"test": "off_contract", "reason": reason})
        for tname in ("expired_notice_spend", "spend_vs_award"):
            tests[tname] = {"skipped": True, "reason": "contracts.csv absent"}
            skipped.append({"test": tname, "reason": "contracts.csv absent"})

    # ------------------------------------------------ 4 duplicates
    dup_groups = []
    for (sup, amt), g in s.groupby(["supplier_norm", "Net amount"]):
        if len(g) < 2:
            continue
        g = g.sort_values(["pay_date", "Date"])
        cluster = [g.iloc[0]]
        clusters = []
        for i in range(1, len(g)):
            r = g.iloc[i]
            if (r["pay_date"] - cluster[-1]["pay_date"]).days <= DUP_DAYS:
                cluster.append(r)
            else:
                clusters.append(cluster)
                cluster = [r]
        clusters.append(cluster)
        for c in clusters:
            if len(c) < 2:
                continue
            ts = {r["Date"] for r in c}
            dup_groups.append({"supplier_norm": sup, "supplier": c[0]["Supplier name"], "amount": r2(amt),
                               "n_rows": len(c), "gbp_beyond_first": r2(amt * (len(c) - 1)),
                               "tier": "same_timestamp" if len(ts) == 1 else "different_time",
                               "dates": sorted({str(r["pay_date"].date()) for r in c}),
                               "tag": c[0]["tag"] if len({r["tag"] for r in c}) == 1 else "mixed",
                               "services": sorted({r["Service"] for r in c}),
                               "row_ids": [r["row_id"] for r in c]})
    ddf = pd.DataFrame(dup_groups)
    ddf.to_csv(os.path.join(FULL, "duplicates.csv"), index=False)
    dup = {"parameters": {"key": "same normalised supplier and amount to the penny", "max_gap_days": DUP_DAYS,
                          "grouping": "chain of payments each within 7 calendar days of the previous",
                          "tiers": {"same_timestamp": "every row shares one Date timestamp (typical of a batch of equal invoices)",
                                    "different_time": "rows at different timestamps (higher signal)"}},
           "rule_ids": cite["publication_over_500"],
           "note": "population is expenditure over £500 only, so this is a lower bound; redacted suppliers excluded",
           "full_list": "outputs/analytics-full/duplicates.csv", "per_tier": {}}
    for tier in ["different_time", "same_timestamp"]:
        d = ddf[ddf["tier"] == tier] if len(ddf) else ddf
        dup["per_tier"][tier] = {"groups": int(len(d)), "rows": int(d["n_rows"].sum()) if len(d) else 0,
                                 "gbp_beyond_first": r2(d["gbp_beyond_first"].sum()) if len(d) else 0,
                                 "by_tag": {k: {"groups": int(len(v)), "gbp_beyond_first": r2(v["gbp_beyond_first"].sum())}
                                            for k, v in d.groupby("tag")} if len(d) else {},
                                 "top20": d.sort_values("amount", ascending=False).head(20).to_dict("records") if len(d) else []}
    tests["duplicates"] = dup

    # ------------------------------------------------ population block
    tags = {}
    for t in TAGS:
        sub = s[s["tag"] == t]
        tags[t] = {"rows": int(len(sub)), "gbp": r2(sub["Net amount"].sum()), "suppliers": int(sub["supplier_norm"].nunique())}
    population = {"files": pop["files"], "header_excel_row": pop["header_excel_row"], "rows_raw": pop["rows_raw"],
                  "rows_after_exclusions": int(len(s)), "date_min": pop["date_min"], "date_max": pop["date_max"],
                  "months_covered": months, "annualisation_factor": factor, "total_gbp": r2(s["Net amount"].sum()),
                  "distinct_suppliers": int(s["supplier_norm"].nunique()),
                  "excluded": log["excluded"], "tags": tags, "tag_regexes": log["regexes"]["tags"],
                  "exclusion_regexes": log["regexes"]["exclusions"],
                  "rows_per_file_month": pop["rows_per_file_month"],
                  "limitations": ["population is expenditure over £500 only", "Date is a payment-run timestamp, not an invoice date; calendar dates used for window logic",
                                  "redacted-supplier rows excluded from all supplier-level tests",
                                  "Net amount assumed ex-VAT; rules.json notes a VAT-basis contradiction between 6.15 and App B",
                                  "tag regexes are fixed by spec: RENT also matches 'Equipment Rentals' and LEASE matches 'Lease car costs' (tagged premises_non_procurement)",
                                  "inter_authority supplier regex (COUNTY) also matches some non-public bodies with 'County' in the name; see spend-excluded.csv"],
                  "grants_note": "grants and transfer payments are kept and tagged, not excluded (clause 1.6.2, cited by clause number)"}
    contracts_block = {k: con.get(k) for k in ["contracts_present", "rows_in_file", "rows_for_council", "rows_dropped_other_buyers",
                                               "rows_dropped_case_variant_of_council_name", "org_names_kept", "notices",
                                               "notice_supplier_pairs", "distinct_suppliers", "active_in_window",
                                               "ended_before_window", "active_notice_supplier_pairs", "zero_value_awards",
                                               "rows_per_year", "published_range", "window_start_used", "warnings"]}
    contracts_block["register_present"] = register_present
    contracts_block["caveat"] = CAVEAT

    out = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
           "scripts": ["scripts/clean.py", "scripts/analyse.py"],
           "population": population,
           "thresholds": thresholds,
           "competition_triggering_definition": {"regex": RE_COMPETITION.pattern,
                                                 "meaning": "a rule citing the threshold requires multiple quotes or a tender; a single quote (App B row A) is not treated as competition"},
           "rule_citations": cite,
           "skipped": skipped, "contracts": contracts_block, "matching": matching,
           "tests": {k: tests[k] for k in ["threshold_clustering", "split_purchases", "high_value_suppliers", "duplicates",
                                            "off_contract", "expired_notice_spend", "spend_vs_award"]}}
    json.dump(out, open(os.path.join(ROOT, "outputs", "analytics.json"), "w"), indent=1, default=str)

    # terse summary only
    print("analyse.py OK")
    print("thresholds:", [(t["value"], t["inclusive"], t["competition_triggering"]) for t in thresholds])
    print("matching:", {k: matching.get(k) for k in ["exact", "near_ratio", "near_contain", "none"]})
    for e in tc["per_threshold"]:
        print("clustering", e["threshold"], e["band_count"], e["band_gbp"], "comparator", e["comparator_count"], "baseline", e["baseline_count"])
    for e in sp["per_threshold"]:
        print("split", e["threshold"], e["windows"], e.get("gbp"), "gp", {k: v for k, v in e.get("headline_general_procurement", {}).items() if k != "top20"},
              "placement", {k: v for k, v in e.get("care_or_education_placement", {}).items() if k != "top20"})
    print("high_value:", hvs["suppliers"], hvs["annualised_estimate_gbp"], "gp", hvs["headline_general_procurement"]["suppliers"])
    print("high_value by tag:", hvs["by_dominant_tag"])
    for k in ["off_contract", "expired_notice_spend", "spend_vs_award"]:
        print(k, {kk: vv for kk, vv in tests[k].items() if kk not in ("top20", "caveat", "publication_note", "parameters", "headline_general_procurement_no_notice_found", "unusable_notices")})
    if "off_contract" in tests and "headline_general_procurement_no_notice_found" in tests["off_contract"]:
        h = tests["off_contract"]["headline_general_procurement_no_notice_found"]
        print("off_contract gp no notice:", h["suppliers"], h["annualised_estimate_gbp"])
    for tier, v in dup["per_tier"].items():
        print("dup", tier, v["groups"], v["rows"], v["gbp_beyond_first"], v["by_tag"])


if __name__ == "__main__":
    main()
