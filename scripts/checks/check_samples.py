#!/usr/bin/env python3
"""QA sample check.

Every transaction in outputs/samples/*.csv, and every row ID printed in
audit-program.md, must exist
  1. in outputs/analytics-full/spend-clean.csv, and
  2. at its sheet row in the council's workbook (data/spend/<file>, sheet
     "Data to publish"; the row ID is <file>:<Excel row number>),
with the same supplier and amount in both (and, for sample rows, as printed
in the sample file).

Usage: check_samples.py [--outputs DIR] [--data DIR]
"""
import openpyxl
import pandas as pd

from _common import ROW_ID_RE, Result, args, run

SHEET = "Data to publish"


class Workbooks:
    def __init__(self, spend_dir):
        self.dir, self.cache = spend_dir, {}

    def row(self, row_id):
        """Return (supplier, amount) at the row, or an error string."""
        f, r = row_id.rsplit(":", 1)
        if f not in self.cache:
            p = self.dir / f
            if not p.exists():
                self.cache[f] = f"workbook {f} not in {self.dir}"
            else:
                ws = openpyxl.load_workbook(p, read_only=True, data_only=True)[SHEET]
                rows = list(ws.iter_rows(values_only=True))
                hdr = next((i for i, x in enumerate(rows) if x and x[0] == "Service"), None)
                if hdr is None:
                    self.cache[f] = f"no header row in {f}"
                else:
                    cols = {c: j for j, c in enumerate(rows[hdr]) if c}
                    self.cache[f] = (rows, cols)
        c = self.cache[f]
        if isinstance(c, str):
            return c
        rows, cols = c
        i = int(r) - 1
        if not 0 <= i < len(rows) or rows[i] is None:
            return f"row {r} is beyond the end of {f}"
        x = rows[i]
        try:
            return str(x[cols["Supplier name"]]), round(float(x[cols["Net amount"]]), 2)
        except (TypeError, ValueError, KeyError):
            return f"row {r} of {f} has no supplier/amount"


def main() -> int:
    a = args(__doc__)
    res = Result("samples")
    sc_p = a.outputs / "analytics-full" / "spend-clean.csv"
    if not sc_p.exists():
        res.fail("analytics-full/spend-clean.csv is missing")
        return res.finish()
    spend = pd.read_csv(sc_p).set_index("row_id")
    wb = Workbooks(a.data / "spend")

    def verify(rid, where, supplier=None, amount=None):
        if rid not in spend.index:
            res.fail(f"{where}: {rid} is not in spend-clean.csv")
            return
        s = spend.loc[rid]
        s_sup, s_amt = str(s["Supplier name"]), round(float(s["Net amount"]), 2)
        bad = []
        if supplier is not None and str(supplier) != s_sup:
            bad.append(f"supplier differs from spend-clean.csv ({supplier!r} vs {s_sup!r})")
        if amount is not None and round(float(amount), 2) != s_amt:
            bad.append(f"amount {amount} differs from spend-clean.csv {s_amt}")
        w = wb.row(rid)
        if isinstance(w, str):
            bad.append(w)
        else:
            if w[0] != s_sup:
                bad.append(f"workbook supplier {w[0]!r} differs from spend-clean.csv {s_sup!r}")
            if w[1] != s_amt:
                bad.append(f"workbook amount {w[1]} differs from spend-clean.csv {s_amt}")
        if bad:
            res.fail(f"{where}: {rid}: " + "; ".join(bad))
        else:
            res.ok()

    files = sorted((a.outputs / "samples").glob("*.csv"))
    if not files:
        res.fail("outputs/samples/ has no sample files (pack not built)")
    n_rows = 0
    for p in files:
        df = pd.read_csv(p)
        for col in ("row_id", "Supplier name", "Net amount"):
            if col not in df.columns:
                res.fail(f"{p.name}: column '{col}' missing")
        if not {"row_id", "Supplier name", "Net amount"} <= set(df.columns):
            continue
        for _, r in df.iterrows():
            n_rows += 1
            verify(r["row_id"], f"samples/{p.name}", r["Supplier name"], r["Net amount"])
    prog = a.outputs / "audit-program.md"
    ids = ROW_ID_RE.findall(prog.read_text(encoding="utf-8")) if prog.exists() else []
    if not prog.exists():
        res.fail("audit-program.md is missing (pack not built)")
    for rid in sorted(set(ids)):
        verify(rid, "audit-program.md")
    res.info(f"sample rows: {n_rows} in {len(files)} file(s); row IDs in audit-program.md: {len(set(ids))}")
    return res.finish()


if __name__ == "__main__":
    run(main)
