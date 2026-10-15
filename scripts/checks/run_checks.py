#!/usr/bin/env python3
"""Run all four QA checks and print one table and a verdict.

Usage: run_checks.py [--outputs DIR] [--data DIR] [--verbose]

Verdict: READY FOR SIGN-OFF when every check passes, otherwise BLOCKED.
Exit 0 when ready, 1 when blocked. The FAIL lines of each check are printed
in full under the table (with --verbose, the INFO lines too).
"""
import re
import subprocess
import sys
from pathlib import Path

from _common import args

CHECKS = ["check_quotes.py", "check_numbers.py", "check_trace.py", "check_samples.py"]
HERE = Path(__file__).resolve().parent


def main() -> int:
    a = args(__doc__, lambda ap: ap.add_argument("--verbose", action="store_true"))
    rows, details = [], []
    for c in CHECKS:
        p = subprocess.run([sys.executable, str(HERE / c), "--outputs", str(a.outputs), "--data", str(a.data)],
                           capture_output=True, text=True, cwd=HERE)
        out = p.stdout + p.stderr
        m = re.search(r"^RESULT (\w+): (PASS|FAIL) \((.+?)\)$", out, re.M)
        name = c.removeprefix("check_").removesuffix(".py")
        if m:
            rows.append((name, m.group(2), m.group(3)))
        else:
            rows.append((name, "FAIL", "check did not finish"))
            details.append(f"FAIL  {name}: " + (out.strip().splitlines() or ["no output"])[-1])
        details += [f"FAIL  {name}: {ln[6:]}" for ln in out.splitlines() if ln.startswith("FAIL  ")]
        if a.verbose:
            details += [f"INFO  {name}: {ln[6:]}" for ln in out.splitlines() if ln.startswith("INFO  ")]
    w = max(len(r[0]) for r in rows)
    print(f"| {'Check':<{w}} | Result | Detail")
    print(f"|{'-' * (w + 2)}|--------|--------")
    for name, r, d in rows:
        print(f"| {name:<{w}} | {r:<6} | {d}")
    ready = all(r == "PASS" for _, r, _ in rows)
    print()
    print("VERDICT: READY FOR SIGN-OFF" if ready else "VERDICT: BLOCKED")
    if details:
        print()
        print("\n".join(details))
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
