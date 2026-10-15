#!/usr/bin/env python3
"""Verify outputs/history.json against the committee PDFs it cites.

Usage: verify_history.py [HISTORY_JSON] [--root REPO_ROOT]

HISTORY_JSON defaults to outputs/history.json. Source paths inside it are
resolved against REPO_ROOT (default: the repo containing this script).

Checks (each failure is printed as `FAIL [CODE] <where>: <detail>`)
  SCHEMA            top-level keys present; sections have the right types.
  DUP_ID            every `id` is unique across the file.
  NO_EVIDENCE       every evidence item (a dict with an `id`, outside `gaps`
                    and `discrepancies`) carries a `source` and a quote.
  BAD_SOURCE        `source.file` exists, is a PDF under data/committee/, and
                    `source.pdf_page` is an int within the PDF's page range.
  QUOTE_SHORT       a quote is under 8 characters after normalisation.
  QUOTE_NOT_FOUND   a quote is on no page of the cited PDF.
  QUOTE_WRONG_PAGE  a quote is in the PDF but not on the stated pdf_page.
  QUOTE_STRADDLES   a quote only matches across a page break.
  FRAGMENT          a `quote_fragments` entry (a table cell rebuilt from the
                    -layout text) is not on the stated page, or the fragments
                    are not stacked in one column on consecutive lines.
  CELL              a `cells` value is not on the stated page, or its leading
                    words are not inside the item's own quote (row mis-assembled).
  SCORED            an item outside `scoring_method` carries a score/rating
                    field (the findings-analyst records, never scores).
  DISCREPANCY       a discrepancy has fewer than two citations.
  GAP               a gap lacks `item`, a `reason` of 8+ chars, or `searched`.

Quotes match after light normalisation (whitespace collapsed; curly quotes,
dashes and NBSP unified) against EITHER `pdftotext` plain or `-layout` text
of the stated page. `pdf_page` is the physical page (1 = first page of the
file), not the number printed in the footer.

Exit 0 and print ALL CHECKS PASSED when clean; exit 1 otherwise.
Requires `pdftotext` (poppler) on PATH.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOP_KEYS = {
    "generated_at": str,
    "sources": list,
    "audits_completed": list,
    "follow_ups": list,
    "advisory_reviews": list,
    "agreed_actions": list,
    "risk_themes": list,
    "strategic_risk_register": dict,
    "scoring_method": dict,
    "discrepancies": list,
    "gaps": list,
}
NON_EVIDENCE_SECTIONS = {"gaps", "discrepancies", "sources"}
SCORE_KEYS = {"score", "likelihood", "impact", "rating", "risk_score", "rag",
              "risk_rating", "priority"}
QUOTE_MIN = 8
FRAG_MAX_LINE_GAP = 4      # lines between consecutive fragments of one cell
FRAG_MAX_COL_DRIFT = 6     # columns a wrapped cell may drift left/right

GLYPHS = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ", "•": " ",
    "": " ",
})


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(GLYPHS)).strip()


def pdftotext(pdf: Path, layout: bool) -> list[str]:
    cmd = ["pdftotext"] + (["-layout"] if layout else []) + [str(pdf), "-"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


class Pdf:
    def __init__(self, path: Path):
        self.raw_layout = [p.translate(GLYPHS) for p in pdftotext(path, True)]
        plain = pdftotext(path, False)
        self.plain = [norm(p) for p in plain]
        self.layout = [norm(p) for p in self.raw_layout]
        self.n = len(self.plain)

    def pages_with(self, q: str) -> list[int]:
        return [i + 1 for i in range(self.n) if q in self.plain[i] or q in self.layout[i]]

    def joined(self) -> str:
        return " ".join(self.plain) + " \x00 " + " ".join(self.layout)


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.pdfs: dict[str, Pdf] = {}
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.n_quotes = 0

    def fail(self, code: str, where: str, detail: str) -> None:
        self.errors.append(f"[{code}] {where}: {detail}")

    def pdf(self, rel: str) -> Pdf | None:
        if rel not in self.pdfs:
            path = (self.root / rel)
            if not path.is_file():
                return None
            self.pdfs[rel] = Pdf(path)
        return self.pdfs[rel]

    # -- source ---------------------------------------------------------
    def check_source(self, where: str, src) -> tuple[Pdf | None, int | None]:
        if not isinstance(src, dict):
            self.fail("BAD_SOURCE", where, "source missing or not an object")
            return None, None
        rel, page = src.get("file"), src.get("pdf_page")
        if not isinstance(rel, str) or not rel.startswith("data/committee/") or not rel.endswith(".pdf"):
            self.fail("BAD_SOURCE", where, f"source.file {rel!r} is not a data/committee/*.pdf path")
            return None, None
        pdf = self.pdf(rel)
        if pdf is None:
            self.fail("BAD_SOURCE", where, f"source.file {rel} does not exist")
            return None, None
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= pdf.n:
            self.fail("BAD_SOURCE", where, f"pdf_page {page!r} not in 1..{pdf.n} for {rel}")
            return pdf, None
        return pdf, page

    # -- quotes ---------------------------------------------------------
    def check_quote(self, where: str, quote: str, pdf: Pdf, page: int) -> None:
        self.n_quotes += 1
        q = norm(quote)
        if len(q) < QUOTE_MIN:
            self.fail("QUOTE_SHORT", where, f"{quote!r} is under {QUOTE_MIN} chars; quote the whole row or sentence")
            return
        hits = pdf.pages_with(q)
        if page in hits:
            if len(hits) > 1:
                self.warnings.append(f"{where}: quote also on page(s) {[h for h in hits if h != page]}")
            return
        if hits:
            self.fail("QUOTE_WRONG_PAGE", where, f"pdf_page is {page} but quote is on page(s) {hits}: {quote[:70]!r}")
        elif q in pdf.joined():
            self.fail("QUOTE_STRADDLES", where, f"quote crosses a page break; split it: {quote[:70]!r}")
        else:
            self.fail("QUOTE_NOT_FOUND", where, f"not in PDF text: {quote[:70]!r}")

    def check_fragments(self, where: str, frags, pdf: Pdf, page: int) -> None:
        if not isinstance(frags, list) or not frags or not all(isinstance(f, str) and f.strip() for f in frags):
            self.fail("FRAGMENT", where, "quote_fragments must be a non-empty list of strings")
            return
        self.n_quotes += 1
        lines = pdf.raw_layout[page - 1].split("\n")
        # all (line, col) positions for each fragment on the stated page
        positions = []
        for f in frags:
            pat = re.compile(r"\s+".join(re.escape(t) for t in norm(f).split(" ")))
            hits = [(i, m.start()) for i, ln in enumerate(lines) for m in pat.finditer(ln)]
            if not hits:
                elsewhere = [p for p in range(1, pdf.n + 1) if p != page and norm(f) in pdf.layout[p - 1]]
                extra = f" (found on page(s) {elsewhere})" if elsewhere else ""
                self.fail("FRAGMENT", where, f"fragment {f!r} not on page {page} layout text{extra}")
                return
            positions.append(hits)
        if len(frags) > 1 and len(" ".join(frags)) < QUOTE_MIN:
            self.fail("QUOTE_SHORT", where, "fragments together are under 8 chars")
        # need a chain: lines strictly increasing, small gaps, columns aligned
        def chain(k: int, prev: tuple[int, int] | None, col0: int | None) -> bool:
            if k == len(positions):
                return True
            for ln, col in positions[k]:
                if prev is not None and not (prev[0] < ln <= prev[0] + FRAG_MAX_LINE_GAP):
                    continue
                if col0 is not None and abs(col - col0) > FRAG_MAX_COL_DRIFT:
                    continue
                if chain(k + 1, (ln, col), col if col0 is None else col0):
                    return True
            return False
        if not chain(0, None, None):
            self.fail("FRAGMENT", where, f"fragments are on page {page} but not stacked in one column: {frags}")

    def check_cells(self, where: str, cells, quote, pdf: Pdf, page: int) -> None:
        if not isinstance(cells, list):
            self.fail("CELL", where, "cells must be a list")
            return
        q = norm(quote) if isinstance(quote, str) else ""
        for c in cells:
            cn = norm(str(c))
            if cn not in pdf.plain[page - 1] and cn not in pdf.layout[page - 1]:
                self.fail("CELL", where, f"cell {c!r} not on page {page}")
                continue
            lead = " ".join(cn.split(" ")[:2])
            if lead not in q:
                self.fail("CELL", where, f"cell {c!r} does not start inside the row quote {q[:70]!r}")

    # -- walking --------------------------------------------------------
    def evidence(self, where: str, d: dict) -> None:
        """A dict that must carry source + quote."""
        quote_keys = [k for k in d if k.endswith("quote") and isinstance(d[k], str)]
        has_frags = "quote_fragments" in d
        if not quote_keys and not has_frags:
            self.fail("NO_EVIDENCE", where, "no quote or quote_fragments")
        if "source" not in d:
            self.fail("NO_EVIDENCE", where, "no source")
            return
        pdf, page = self.check_source(where, d["source"])
        if pdf is None or page is None:
            return
        for k in quote_keys:
            self.check_quote(f"{where}.{k}" if k != "quote" else where, d[k], pdf, page)
        if has_frags:
            self.check_fragments(where, d["quote_fragments"], pdf, page)
        if "cells" in d:
            self.check_cells(where, d["cells"], d.get("quote"), pdf, page)

    def walk(self, node, path: str, section: str, ids: dict) -> None:
        if isinstance(node, list):
            for i, x in enumerate(node):
                self.walk(x, f"{path}[{i}]", section, ids)
            return
        if not isinstance(node, dict):
            return
        where = node.get("id") if isinstance(node.get("id"), str) else path
        if "id" in node:
            if node["id"] in ids:
                self.fail("DUP_ID", where, f"also used at {ids[node['id']]}")
            ids.setdefault(node["id"], path)
        if section != "scoring_method":
            bad = SCORE_KEYS & set(node)
            if bad:
                self.fail("SCORED", where, f"has scoring field(s) {sorted(bad)}; record, never score")
        is_evidence = (
            section not in NON_EVIDENCE_SECTIONS
            and ("id" in node or "source" in node
                 or any(k.endswith("quote") for k in node) or "quote_fragments" in node)
        )
        if section == "discrepancies" and "citations" not in node and ("source" in node or "quote" in node):
            is_evidence = True  # a citation inside a discrepancy
        if is_evidence:
            self.evidence(where, node)
        for k, v in node.items():
            if isinstance(v, (dict, list)) and k != "source":
                self.walk(v, f"{path}.{k}", section, ids)

    def run(self, doc) -> None:
        if not isinstance(doc, dict):
            self.fail("SCHEMA", "<root>", "history.json must be an object")
            return
        for k, typ in TOP_KEYS.items():
            if k not in doc:
                self.fail("SCHEMA", "<root>", f"missing top-level key '{k}'")
            elif not isinstance(doc[k], typ):
                self.fail("SCHEMA", k, f"must be {typ.__name__}")
        ids: dict[str, str] = {}
        for k, v in doc.items():
            if k in ("generated_at", "notes", "method"):
                continue
            if k == "discrepancies" and isinstance(v, list):
                for i, d in enumerate(v):
                    did = d.get("id", f"discrepancies[{i}]") if isinstance(d, dict) else f"discrepancies[{i}]"
                    cites = d.get("citations") if isinstance(d, dict) else None
                    if not isinstance(cites, list) or len(cites) < 2:
                        self.fail("DISCREPANCY", did, "needs at least two citations, each with source + quote")
                    if isinstance(d, dict) and not str(d.get("description", "")).strip():
                        self.fail("DISCREPANCY", did, "description missing")
            if k == "gaps" and isinstance(v, list):
                for i, g in enumerate(v):
                    gid = g.get("id", f"gaps[{i}]") if isinstance(g, dict) else f"gaps[{i}]"
                    if not isinstance(g, dict) or not str(g.get("item", "")).strip():
                        self.fail("GAP", gid, "item missing")
                        continue
                    if len(str(g.get("reason", "")).strip()) < 8:
                        self.fail("GAP", gid, "reason missing or too short")
                    if not isinstance(g.get("searched"), list) or not g["searched"]:
                        self.fail("GAP", gid, "searched must list the files looked in")
            if k == "sources" and isinstance(v, list):
                for i, s in enumerate(v):
                    f = s.get("file") if isinstance(s, dict) else None
                    if not isinstance(f, str) or not (self.root / f).is_file():
                        self.fail("BAD_SOURCE", f"sources[{i}]", f"file {f!r} does not exist")
            self.walk(v, k, k, ids)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("history", nargs="?", default="outputs/history.json")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()
    if not shutil.which("pdftotext"):
        print("ERROR: pdftotext (poppler) not on PATH")
        return 1
    root = Path(args.root)
    hist = Path(args.history)
    if not hist.is_absolute() and not hist.exists():
        hist = root / hist
    try:
        doc = json.loads(hist.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read {hist}: {e}")
        return 1

    c = Checker(root)
    c.run(doc)
    print(f"{hist}: {c.n_quotes} quote(s) checked across {len(c.pdfs)} PDF(s)")
    for w in c.warnings:
        print(f"WARN  {w}")
    for e in c.errors:
        print(f"FAIL  {e}")
    if c.errors:
        print(f"\n{len(c.errors)} failure(s), {len(c.warnings)} warning(s)")
        return 1
    print(f"\nALL CHECKS PASSED ({c.n_quotes} quotes, {len(c.warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
