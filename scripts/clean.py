"""Clean spend workbooks and the Contracts Finder export.

Writes outputs/analytics-full/{spend-clean.csv, spend-excluded.csv,
notices-clean.csv, cleaning-log.json}. Stops (exit 1) on malformed input.
"""
import glob
import json
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs", "analytics-full")
os.makedirs(OUT, exist_ok=True)

EXPECTED = ["Service", "Expenditure category", "Narrative", "Date",
            "Net amount", "Supplier name"]
SHEET = "Data to publish"
COUNCIL_NAMES = {"West Berkshire Council", "West Berkshire"}
NOTICE_DATE_FMT = "%d/%m/%Y"
SPEND_TEXT_DATE_FMT = "%m/%d/%y"
SUPPLIER_COL = "Supplier [Name|Address|Ref type|Ref Number|Is SME|Is VCSE]"

DROP_TOKENS = {"LTD", "LIMITED", "PLC", "LLP", "LLC", "INC", "CIC", "CIO", "UK", "THE"}

RE_REDACTED = re.compile(r"^\s*redacted\s*$", re.I)
RE_PENSION = re.compile(r"LGPS|PENSION|SUPERANNUATION", re.I)
RE_INTER_SUPPLIER = re.compile(
    r"\b(?:COUNCIL|BOROUGH|COUNTY|CNCL|NHS|POLICE|FIRE AUTHORITY|FIRE AND RESCUE|"
    r"HMRC|HM REVENUE|DEPARTMENT FOR|MINISTRY OF)\b", re.I)
RE_INTER_NARR = re.compile(r"JOINT ARRANGEMENTS", re.I)
RE_PRIVATE_CONTRACTORS = re.compile(r"^\s*Private Contractors\s*$", re.I)

RE_PLACEMENT_SERVICE = re.compile(r"^(Adult Social Care|Children's Social Care|Education)")
RE_PLACEMENT_NARR = re.compile(r"^\s*(Private Contractors|Other agencies|Voluntary Associations)\s*$", re.I)
RE_GRANT = re.compile(r"GRANT", re.I)
RE_AGENCY = re.compile(r"AGENCY", re.I)
RE_PREMISES = re.compile(r"RENT|RATES|WATER RATES|LEASE", re.I)


def stop(msg):
    print(f"STOP: {msg}")
    sys.exit(1)


def normalise_supplier(name):
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    s = str(name).upper()
    s = re.sub(r"['’`]", "", s)  # delete apostrophes: POTTINGER'S -> POTTINGERS, not POTTINGER S
    s = s.replace("&", " AND ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\bT/AS?\b.*$", " ", s)  # T/A and T/AS variants
    s = re.sub(r"\bTRADING AS\b.*$", " ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in DROP_TOKENS]
    return " ".join(toks)


def load_spend():
    files = sorted(glob.glob(os.path.join(DATA, "spend", "*.xlsx"))) + \
        sorted(glob.glob(os.path.join(DATA, "spend", "*.csv")))
    if not files:
        stop("no spend files in data/spend/")
    frames, header_rows = [], {}
    for f in files:
        base = os.path.basename(f)
        if f.endswith(".xlsx"):
            raw = pd.read_excel(f, sheet_name=SHEET, header=None)
        else:
            raw = pd.read_csv(f, header=None, dtype=str)
        hits = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "Service"].tolist()
        if not hits:
            stop(f"{base}: no row whose first cell is 'Service'")
        h = hits[0]
        header_rows[base] = int(h) + 1  # Excel row number
        if f.endswith(".xlsx"):
            df = pd.read_excel(f, sheet_name=SHEET, header=h)
        else:
            df = pd.read_csv(f, header=h)
        df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
        cols = [str(c).strip() for c in df.columns]
        if cols != EXPECTED:
            stop(f"{base}: columns {cols} != expected {EXPECTED}")
        df.columns = cols
        # drop fully blank trailing rows
        df = df.dropna(how="all")
        df["source_file"] = base
        # sheet row = excel row number: header excel row + 1 + position
        df["row_id"] = [f"{base}:{h + 2 + i}" for i in df.index]
        frames.append(df)
    spend = pd.concat(frames, ignore_index=True)
    return files, header_rows, spend


def parse_spend_dates(spend):
    d = spend["Date"]
    if pd.api.types.is_datetime64_any_dtype(d):
        parsed = d
    else:
        parsed = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns]")
        is_dt = d.apply(lambda v: isinstance(v, (pd.Timestamp,)) or hasattr(v, "year"))
        parsed[is_dt] = pd.to_datetime(d[is_dt])
        txt = d[~is_dt].astype(str).str.strip()
        parsed[~is_dt] = pd.to_datetime(txt.str.split(" ").str[0], format=SPEND_TEXT_DATE_FMT, errors="coerce")
    return parsed


def main():
    log = {"regexes": {}, "stops": []}
    files, header_rows, spend = load_spend()
    rows_raw = len(spend)
    spend["Date"] = parse_spend_dates(spend)
    spend["Net amount"] = pd.to_numeric(spend["Net amount"], errors="coerce")
    for col in ["Date", "Net amount", "Supplier name"]:
        n = int(spend[col].isna().sum())
        if n:
            stop(f"{n} rows with null/unparseable {col}")
    neg = spend[spend["Net amount"] < 0]
    if len(neg):
        log["negative_amount_rows"] = neg["row_id"].tolist()
        json.dump(log, open(os.path.join(OUT, "cleaning-log.json"), "w"), indent=1, default=str)
        stop(f"{len(neg)} negative amounts (row_ids logged in cleaning-log.json)")
    spend["pay_date"] = spend["Date"].dt.date
    spend["Date"] = spend["Date"].dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]
    spend["supplier_norm"] = spend["Supplier name"].map(normalise_supplier)
    spend["Narrative"] = spend["Narrative"].fillna("").astype(str)
    spend["Service"] = spend["Service"].fillna("").astype(str)

    # ---- exclusions (first match wins in this order)
    supp = spend["Supplier name"].astype(str)
    narr = spend["Narrative"]
    excl = pd.Series("", index=spend.index)
    m_red = supp.str.match(RE_REDACTED)
    excl[m_red] = "redacted_supplier"
    m_pen = (excl == "") & narr.str.contains(RE_PENSION)
    excl[m_pen] = "pension_statutory"
    m_int = (excl == "") & (supp.str.contains(RE_INTER_SUPPLIER) | narr.str.contains(RE_INTER_NARR)) \
        & ~narr.str.match(RE_PRIVATE_CONTRACTORS)
    excl[m_int] = "inter_authority"
    spend["exclusion"] = excl
    reasons = {
        "redacted_supplier": "supplier recorded as 'Redacted' (many payees under one label); unusable in supplier-level tests",
        "pension_statutory": "narrative indicates pension/LGPS/superannuation: statutory, not procurement",
        "inter_authority": "payee is another public body (council/NHS/police/fire/HMRC/government department) or joint arrangements; not procurement (Private Contractors narrative kept)",
    }
    log["regexes"]["exclusions"] = {
        "redacted_supplier": RE_REDACTED.pattern, "pension_statutory": RE_PENSION.pattern,
        "inter_authority_supplier": RE_INTER_SUPPLIER.pattern, "inter_authority_narrative": RE_INTER_NARR.pattern,
        "inter_authority_unless_narrative": RE_PRIVATE_CONTRACTORS.pattern}
    excluded = spend[spend["exclusion"] != ""].copy()
    clean = spend[spend["exclusion"] == ""].copy().drop(columns=["exclusion"])
    log["excluded"] = {}
    for k, r in reasons.items():
        sub = excluded[excluded["exclusion"] == k]
        log["excluded"][k] = {"rows": int(len(sub)), "gbp": round(float(sub["Net amount"].sum()), 2), "reason": r}

    # ---- tagging
    def tag(row):
        if RE_PLACEMENT_SERVICE.match(row["Service"]) and RE_PLACEMENT_NARR.match(row["Narrative"]):
            return "care_or_education_placement"
        if RE_GRANT.search(row["Narrative"]):
            return "grant"
        if RE_AGENCY.search(row["Narrative"]):
            return "agency_staff"
        if RE_PREMISES.search(row["Narrative"]):
            return "premises_non_procurement"
        return "general_procurement"
    clean["tag"] = clean.apply(tag, axis=1)
    log["regexes"]["tags"] = {
        "care_or_education_placement": {"service": RE_PLACEMENT_SERVICE.pattern, "narrative": RE_PLACEMENT_NARR.pattern},
        "grant": RE_GRANT.pattern, "agency_staff": RE_AGENCY.pattern,
        "premises_non_procurement": RE_PREMISES.pattern, "order": "first match wins"}

    months = pd.to_datetime(clean["pay_date"]).dt.to_period("M").nunique()
    log["population"] = {
        "files": [os.path.basename(f) for f in files], "header_excel_row": header_rows,
        "rows_raw": rows_raw, "rows_excluded": int(len(excluded)), "rows_after_exclusions": int(len(clean)),
        "date_min": str(min(clean["pay_date"])), "date_max": str(max(clean["pay_date"])),
        "months_covered": int(months),
        "rows_per_file_month": {f"{a}|{b}": int(n) for (a, b), n in
                                spend.assign(m=pd.to_datetime(spend["pay_date"]).dt.strftime("%Y-%m"))
                                .groupby(["source_file", "m"]).size().items()},
    }
    clean.to_csv(os.path.join(OUT, "spend-clean.csv"), index=False)
    excluded.to_csv(os.path.join(OUT, "spend-excluded.csv"), index=False)
    window_start = pd.Timestamp(min(spend["pay_date"]))

    # ---- contracts
    cpath = os.path.join(DATA, "contracts.csv")
    reg = os.path.join(DATA, "contract-register.csv")
    log["register_present"] = os.path.exists(reg)
    con = {"contracts_present": os.path.exists(cpath), "warnings": []}
    if con["contracts_present"]:
        c = pd.read_csv(cpath, dtype=str, keep_default_na=False)
        con["rows_in_file"] = int(len(c))
        orgs = c["Organisation Name"].str.strip()
        keep = orgs.isin(COUNCIL_NAMES)
        dropped = c[~keep]
        case_var = dropped[orgs[~keep].str.upper().isin({n.upper() for n in COUNCIL_NAMES})]
        con["rows_for_council"] = int(keep.sum())
        con["rows_dropped_other_buyers"] = int(len(dropped))
        con["org_names_kept"] = orgs[keep].value_counts().to_dict()
        con["org_names_dropped"] = orgs[~keep].value_counts().to_dict()
        con["rows_dropped_case_variant_of_council_name"] = int(len(case_var))
        if len(case_var):
            con["warnings"].append(
                f"{len(case_var)} notice rows dropped whose Organisation Name is a case variant of the council's name "
                f"({sorted(case_var['Organisation Name'].unique())}); spec keeps only exact 'West Berkshire Council'/'West Berkshire'. "
                "Auditor to decide whether to include them (would add notices to the match set).")
            case_var[["Notice Identifier", "Organisation Name", "Title"]].to_csv(
                os.path.join(OUT, "notices-dropped-case-variant.csv"), index=False)
        c = c[keep].copy()
        if len(c) < 20:
            con["warnings"].append("fewer than 20 council notices after filtering: treated as absent")
            con["treated_as_absent"] = True
        if con["rows_in_file"] == 1000:
            con["warnings"].append("file has exactly 1,000 rows: Contracts Finder export cap may have truncated it")
        for col in ["Contract start date", "Contract end date", "Awarded Date"]:
            vals = c[col].str.strip()
            parsed = pd.to_datetime(vals, format=NOTICE_DATE_FMT, errors="coerce")
            bad = (vals != "") & parsed.isna()
            if bad.any():
                stop(f"contracts.csv: {int(bad.sum())} unparseable {col} values (format {NOTICE_DATE_FMT})")
            c[col] = parsed
        c["Published Date"] = pd.to_datetime(c["Published Date"].str.strip(), format="ISO8601", utc=True)
        c["Awarded Value"] = pd.to_numeric(c["Awarded Value"].str.replace(",", ""), errors="raise")
        rows = []
        for _, r in c.iterrows():
            packed = r[SUPPLIER_COL].strip()
            if not packed:
                blocks = []
            else:
                blocks = [b.strip("[]") for b in packed.split("][")]
            for b in blocks:
                parts = b.split("|")
                name = parts[0].strip()
                ch = parts[3].strip() if len(parts) > 3 and parts[2].strip() == "COMPANIES_HOUSE" else ""
                rows.append({"Notice Identifier": r["Notice Identifier"], "Title": r["Title"],
                             "OJEU Procedure Type": r["OJEU Procedure Type"], "Awarded Value": r["Awarded Value"],
                             "Contract start date": r["Contract start date"], "Contract end date": r["Contract end date"],
                             "Awarded Date": r["Awarded Date"], "Published Date": r["Published Date"],
                             "suppliers_on_notice": len(blocks), "supplier_name": name,
                             "companies_house_no": ch, "supplier_norm": normalise_supplier(name)})
        n = pd.DataFrame(rows)
        n["active"] = n["Contract end date"].isna() | (n["Contract end date"] >= window_start)
        n["ended_before_window"] = ~n["active"]
        n.to_csv(os.path.join(OUT, "notices-clean.csv"), index=False)
        notice_active = c["Contract end date"].isna() | (c["Contract end date"] >= window_start)
        con.update({
            "notices": int(len(c)), "notices_without_supplier": int((c[SUPPLIER_COL].str.strip() == "").sum()),
            "notice_supplier_pairs": int(len(n)), "distinct_suppliers": int(n["supplier_norm"].nunique()),
            "active_in_window": int(notice_active.sum()), "ended_before_window": int((~notice_active).sum()),
            "active_notice_supplier_pairs": int(n["active"].sum()),
            "zero_value_awards": int((c["Awarded Value"] == 0).sum()),
            "rows_per_year": {str(k): int(v) for k, v in c["Published Date"].dt.year.value_counts().sort_index().items()},
            "published_range": [str(c["Published Date"].min().date()), str(c["Published Date"].max().date())],
            "window_start_used": str(window_start.date()),
        })
        ys = con["rows_per_year"]
        if ys:
            med = pd.Series(list(ys.values())).median()
            for y, v in ys.items():
                full_year = int(y) < pd.Timestamp.today().year
                if v < 0.5 * med:
                    tag = "" if full_year else " (current, partial year)"
                    con["warnings"].append(f"publication year {y}{tag} has {v} notices, under half the median per year: check export completeness")
    log["contracts"] = con
    json.dump(log, open(os.path.join(OUT, "cleaning-log.json"), "w"), indent=1, default=str)
    print("clean.py OK")
    print(json.dumps({"population": log["population"], "excluded": log["excluded"],
                      "contracts": {k: v for k, v in con.items() if k not in ("org_names_dropped",)}}, indent=1, default=str))


if __name__ == "__main__":
    main()
