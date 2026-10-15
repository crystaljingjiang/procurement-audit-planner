"""Re-derive one flagged item per test independently from spend-clean.csv."""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, "outputs", "analytics-full")
a = json.load(open(os.path.join(ROOT, "outputs", "analytics.json")))
s = pd.read_csv(os.path.join(FULL, "spend-clean.csv"), parse_dates=["pay_date"])
T = a["tests"]
f = a["population"]["annualisation_factor"]
ok_all = True


def check(name, cond, detail):
    global ok_all
    ok_all &= bool(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {detail}")


# 1 clustering: top row in the 25k band
TL = min(x["value"] for x in a["thresholds"] if x["competition_triggering"] and x["inclusive"])  # lowest competition threshold, from analytics.json
e = next(x for x in T["threshold_clustering"]["per_threshold"] if x["threshold"] == TL)
r = e["top20"][0]
row = s[s["row_id"] == r["row_id"]].iloc[0]
check("threshold_clustering", 0.9 * TL <= row["Net amount"] < TL and round(row["Net amount"], 2) == r["Net amount"],
      f"row_id {r['row_id']} amount {row['Net amount']} in [0.9T, T) for T={TL}")
band = s[(s["Net amount"] >= 0.9 * TL) & (s["Net amount"] < TL)]
check("threshold_clustering band count", len(band) == e["band_count"], f"recount {len(band)} vs {e['band_count']}")

# 2 split: top general-procurement window at 25k
w = next(x for x in T["split_purchases"]["per_threshold"] if x["threshold"] == TL)["headline_general_procurement"]["top20"][0]
ws = s[(s["supplier_norm"] == w["supplier_norm"]) & (s["pay_date"] >= w["window_start"]) & (s["pay_date"] <= w["window_end"])
       & (s["Net amount"] < TL)]
check("split_purchases", round(ws["Net amount"].sum(), 2) == w["total_gbp"] and len(ws) == w["n_payments"]
      and (pd.Timestamp(w["window_end"]) - pd.Timestamp(w["window_start"])).days < 30,
      f"row_ids {w['row_ids']} resum {round(ws['Net amount'].sum(), 2)} vs {w['total_gbp']}")

# 3 high value: top general-procurement supplier
h = T["high_value_suppliers"]["headline_general_procurement"]["top20"][0]
hs = s[s["supplier_norm"] == h["supplier_norm"]]
check("high_value_suppliers", round(hs["Net amount"].sum(), 2) == h["total_gbp"] and round(hs["Net amount"].sum() * f, 2) == h["annualised estimate"],
      f"supplier rows {len(hs)} first row_id {hs['row_id'].iloc[0]}; resum {round(hs['Net amount'].sum(), 2)}")

# 4 duplicates: top different_time group
d = T["duplicates"]["per_tier"]["different_time"]["top20"][0]
ds = s[s["row_id"].isin(d["row_ids"])]
check("duplicates", ds["supplier_norm"].nunique() == 1 and ds["Net amount"].nunique() == 1 and ds["Date"].nunique() > 1
      and ds["pay_date"].sort_values().diff().dt.days.max() <= 7,
      f"row_ids {d['row_ids']} amount {ds['Net amount'].iloc[0]}")

# 5 off_contract: top unmatched general-procurement supplier has no exact active notice name
o = T["off_contract"]["headline_general_procurement_no_notice_found"]["top20"][0]
n = pd.read_csv(os.path.join(FULL, "notices-clean.csv"))
active = set(n.loc[n["active"], "supplier_norm"].dropna())
os_ = s[s["supplier_norm"] == o["supplier_norm"]]
check("off_contract", o["supplier_norm"] not in active and round(os_["Net amount"].sum(), 2) == o["total_gbp"],
      f"supplier first row_id {os_['row_id'].iloc[0]}; no exact active-notice name")

# 6 expired notice spend
x = T["expired_notice_spend"]["top20"][0]
nx = n[n["supplier_norm"] == x["supplier_norm"]]
xs = s[s["supplier_norm"] == x["supplier_norm"]]
check("expired_notice_spend", nx["ended_before_window"].all() and round(xs["Net amount"].sum(), 2) == x["total_gbp"],
      f"notice {x['notice_id']} end {x['latest_end_date']}; first row_id {xs['row_id'].iloc[0]}")

# 7 spend vs award
v = T["spend_vs_award"]["top20"][0]
vs = s[s["supplier_norm"] == v["supplier_norm"]]
nv = n[n["Notice Identifier"] == v["notice_id"]].iloc[0]
yrs = (pd.Timestamp(nv["Contract end date"]) - pd.Timestamp(nv["Contract start date"])).days / 365.25
ratio = vs["Net amount"].sum() * f / (nv["Awarded Value"] / yrs)
check("spend_vs_award", abs(ratio - v["ratio"]) < 0.001, f"notice {v['notice_id']} ratio {round(ratio, 3)} vs {v['ratio']}; first row_id {vs['row_id'].iloc[0]}")

print("ALL PASS" if ok_all else "SOME FAILED")
