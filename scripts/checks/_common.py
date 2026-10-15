"""Shared helpers for the QA checks in scripts/checks/.

Every check prints `FAIL  <item>` lines (and `INFO  <line>` notes), then one
final line that run_checks.py parses:

    RESULT <check>: PASS (<n> checked)
    RESULT <check>: FAIL (<k> of <n> checked)

Exit 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACK_DOCS = ("planning-memo.md", "risk-control-matrix.md", "audit-program.md")
ROW_ID_RE = re.compile(r"[A-Za-z0-9_.\-]+\.xlsx:\d+")


def args(desc: str, extra=None):
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--outputs", default=str(REPO / "outputs"))
    ap.add_argument("--data", default=str(REPO / "data"))
    if extra:
        extra(ap)
    a = ap.parse_args()
    a.outputs, a.data = Path(a.outputs), Path(a.data)
    return a


class Result:
    def __init__(self, name: str):
        self.name, self.fails, self.n = name, [], 0

    def ok(self, n: int = 1):
        self.n += n

    def fail(self, item: str):
        self.n += 1
        self.fails.append(item)

    def info(self, line: str):
        print(f"INFO  {line}")

    def finish(self) -> int:
        for f in self.fails:
            print(f"FAIL  {f}")
        if self.fails:
            print(f"RESULT {self.name}: FAIL ({len(self.fails)} of {self.n} checked)")
            return 1
        print(f"RESULT {self.name}: PASS ({self.n} checked)")
        return 0


def load_json(p: Path, res: Result):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        res.fail(f"cannot read {p.name}: {e}")
        return None


def numeric_leaves(node, out: set):
    if isinstance(node, bool):
        return out
    if isinstance(node, (int, float)):
        out.add(float(node))
    elif isinstance(node, str):
        try:
            out.add(float(node.replace(",", "")))
        except ValueError:
            pass
    elif isinstance(node, dict):
        for v in node.values():
            numeric_leaves(v, out)
    elif isinstance(node, list):
        for v in node:
            numeric_leaves(v, out)
    return out


def md_table(text: str, first_header: str):
    """Rows (dicts) of the first markdown table whose header starts with `first_header`."""
    rows, header = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            if cells and cells[0] == first_header:
                header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return header, rows


def run(main):
    sys.exit(main())
