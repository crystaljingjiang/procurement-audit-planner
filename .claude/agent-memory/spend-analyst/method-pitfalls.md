# Method pitfalls and fixes (2026-10-14)

- Competition-triggering regex: rule text is "send invitations to quote ... to at least three", so "at least three ... quote" alone misses it (quote comes first). But a bare "invitation to tender" match wrongly catches the "publish details of every such invitation to tender" publication rule. Use: `send invitations? to (quote|tender)|at least (two|three|five|N)\b.{0,60}(quot|tender)|competitive tender`. A single-quote tier is not competition.
- Supplier normalisation: DELETE apostrophes (POTTINGER'S -> POTTINGERS) rather than turning them into spaces, or near-ratio misses become needed. Strip both `T/A` and `T/AS` suffixes.
- Fixed tag regexes over-match: RENT catches "Equipment Rentals", LEASE catches "Lease car costs"; COUNTY in the inter-authority regex catches non-public bodies with "County" in the name. Spec-fixed; report as limitations rather than silently change.
- Threshold inclusivity at 500,000 has a band gap in the rules (less than / above); derive inclusivity from low-bound rules first and flag inclusivity_conflict.
- Keep analyse.py terminal output to a one-line-per-test summary; the full JSON is large because split windows carry row_id lists.
- selfcheck.py must not type threshold figures either (rule 3): read the lowest competition-triggering threshold from analytics.json `thresholds` and derive 0.9*T from it. A prior version hardcoded them (fixed 2026-10-14).
