# Input-format quirks (2026-10-14)

- Spend workbooks: header row differs per file (Excel row 1 in some, row 2 in others, with a blank row above). Locate the row whose first cell is "Service"; never assume row 0. Date loads as datetime already.
- A monthly workbook can contain a stray row dated in the next month: compute months_covered from pay_date, not from file count.
- Expenditure category has some nulls; only Date, Net amount, Supplier name are asserted non-null.
- contracts.csv supplier column is literally named `Supplier [Name|Address|Ref type|Ref Number|Is SME|Is VCSE]` (not "Supplier"). Read with dtype=str, keep_default_na=False.
- contracts.csv Organisation Name has an upper-case variant of the council name; spec keeps exact names only, so log case-variant drops separately (cleaning-log + contracts.warnings) for the auditor.
- Published Date is ISO with offset: parse with format="ISO8601", utc=True.
