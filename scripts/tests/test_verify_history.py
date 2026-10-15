#!/usr/bin/env python3
"""Test scripts/verify_history.py on fixtures with known content.

history-good.json : real quotes from data/committee/*.pdf -> must pass.
history-bad.json  : the good file plus planted errors -> every planted
                    (code, id) pair below must be reported, and nothing
                    from the good items may fail.

Run: .venv/bin/python scripts/tests/test_verify_history.py
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY = HERE.parent / "verify_history.py"

PLANTED = {
    ("SCHEMA", "<root>"),               # advisory_reviews removed
    ("QUOTE_NOT_FOUND", "AUD-01"),      # opinion altered in the quote
    ("CELL", "AUD-01"),                 #   ... so the cells no longer sit in it
    ("CELL", "AUD-03"),                 # opinion taken from another row
    ("SCORED", "AUD-04"),               # carries a rating
    ("BAD_SOURCE", "AUD-05"),           # pdf_page 9 of a 2-page PDF
    ("BAD_SOURCE", "AUD-06"),           # file does not exist
    ("QUOTE_WRONG_PAGE", "FU-01"),      # page 2 quote cited as page 1
    ("QUOTE_SHORT", "FU-02"),           # one-word quote
    ("QUOTE_STRADDLES", "FU-03"),       # crosses the page 1/2 break
    ("NO_EVIDENCE", "RT-02"),           # no quote at all
    ("DUP_ID", "RT-01"),                # id reused
    ("FRAGMENT", "IMP-4-MIX"),          # fragments from two different columns
    ("FRAGMENT", "IMP-5-FIN"),          # fragments on the wrong page
    ("DISCREPANCY", "DISC-03"),         # one citation only
    ("GAP", "GAP-02"),                  # no reason
}
ALLOWED_EXTRA = {("CELL", "FU-01")}     # side effect of the wrong page


def run(name: str) -> tuple[int, set[tuple[str, str]], str]:
    p = subprocess.run([sys.executable, str(VERIFY), str(HERE / "fixtures" / name)],
                       capture_output=True, text=True)
    found = set(re.findall(r"^FAIL  \[(\w+)\] ([^:]+):", p.stdout, re.MULTILINE))
    return p.returncode, found, p.stdout


def main() -> int:
    ok = True
    rc, found, out = run("history-good.json")
    if rc != 0 or found:
        print("FAIL good fixture did not pass:\n" + out)
        ok = False
    else:
        print("ok   good fixture passes")

    rc, found, out = run("history-bad.json")
    if rc != 1:
        print(f"FAIL bad fixture exit code {rc}, expected 1")
        ok = False
    for miss in sorted(PLANTED - found):
        print(f"FAIL planted error not caught: {miss}")
        ok = False
    for extra in sorted(found - PLANTED - ALLOWED_EXTRA):
        print(f"FAIL unexpected failure (false positive): {extra}")
        ok = False
    caught = len(PLANTED & found)
    print(f"{'ok  ' if caught == len(PLANTED) else 'FAIL'} {caught}/{len(PLANTED)} planted errors caught")
    print("\nALL TESTS PASSED" if ok else "\nTESTS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
