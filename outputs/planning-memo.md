# Audit planning memo: procurement, West Berkshire Council

Basis: risk register revision 1 (built 2026-10-14T16:42:30), auditor decisions in `outputs/auditor-comments.md`, plan `outputs/audit-plan.json`. Built 2026-10-14T17:15:49 by `.claude/skills/audit-program/build_pack.py`.

These are **risk indicators to investigate**, not findings of wrongdoing by the council, a service or a supplier. A sampled transaction is selected because it carries an indicator, not because anything is assumed to be wrong with it.

## Objective

Conclude on whether the council's controls over the procurement route for the value of each requirement [CPR-11] [CPR-56], the recording of contracts [CPR-07], the approval of contract extensions and variations [CPR-63] [CPR-64] [CPR-65] and the evidencing of each purchase [CPR-30] operate as the Contract Procedure Rules require, for the risk indicators the auditor approved in the register. The audit investigates indicators; it does not presume that any payment, service or supplier is non-compliant.

## Scope

7 risk(s) in scope, 0 out of scope, as decided by the auditor.

| Risk | L | I | Score | Band | Decision | Tests | Sample transactions |
|---|---|---|---|---|---|---|---|
| R-01: Payments just below the £25,000 quotation threshold | 2 | 3 | 6 | Moderate | Approve | T-01-1 | 10 |
| R-02: Same-supplier payments within 30 days that together cross a competition threshold | 3 | 5 | 15 | Extreme (Red) | Approve | T-02-1, T-02-2 | 487 |
| R-03: High-value general procurement suppliers with no Contracts Finder notice found | 3 | 5 | 15 | Extreme (Red) | Approve | T-03-1, T-03-2, T-03-3 | 80 |
| R-04: Repeated same-amount payments to one supplier within 7 days | 3 | 3 | 9 ‡ | Medium - High (Amber) | Approve | T-04-1 | 39 |
| R-05: Spend with suppliers whose only published notices ended before the spend window | 2 | 4 | 8 | Medium - High (Amber) | Approve | T-05-1 | 13 |
| R-06: Annualised spend above the published award value for single-supplier notices | 2 | 5 | 10 ‡ | Medium - High (Amber) | Approve | T-06-1 | 28 |
| R-07: Implementation of agreed actions from prior procurement audits is not evidenced in the public papers | 1 | 2 | 2 | Low (Green) | Approve | T-07-1 | 0 |

## Approach

Targeted tests over the full published spend population of 8,534 payments [A1] totalling £66,778,105 [A2], rather than a random sample. Each test draws its sample from the analytics indicator files, sorted by the strength of the indicator (value, ratio or count) and sized by the risk's register score. Competition tests are limited to general procurement, as the approved risks are defined. The App C row F exemption covers only the social care services it lists (individual placements, packages and Shared Lives) [CPR-66]; no rule in rules.json exempts grants or education placements from competition (the grants clause sits in the rules' excluded list without a rule ID), so leaving those groups out of the competition tests is a scope decision for the auditor, not a rule-based exemption. A supplier with no Contracts Finder notice found is checked against the council's own contract register before any conclusion is drawn [A3]; suppliers below the publication threshold are never questioned on that basis.

## Sampling

Samples are targeted, not random: each test draws the highest-indicator items from the full flagged population in `outputs/analytics-full/`, sized by the risk's register score, and every transaction is checked against `spend-clean.csv`. Files: `outputs/samples/<test>.csv`.

| Register score | Items per test |
|---|---|
| 15+ | 25 |
| 8–14 | 15 |
| 4–7 | 10 |
| 1–3 | 5 |

| Test | Source | Population | Drawn | Transactions | Value £ |
|---|---|---|---|---|---|
| T-01-1 | threshold_clustering.csv | 10 | 10 | 10 | 239,427.82 |
| T-02-1 | split_purchases.csv | 39 | 39 | 429 | 2,221,901.37 |
| T-02-2 | split_purchases.csv | 2 | 2 | 58 | 3,509,528.75 |
| T-03-1 | high_value_suppliers.csv | 186 | 25 | 62 | 14,865,447.37 |
| T-03-2 | near-matches.csv | 6 | 6 | 18 | 239,360.31 |
| T-03-3 | no transaction sample | – | – | – | – |
| T-04-1 | duplicates.csv | 35 | 15 | 39 | 525,039.22 |
| T-05-1 | expired_notice_spend.csv | 8 | 8 | 13 | 188,394.86 |
| T-06-1 | spend_vs_award.csv | 12 | 12 | 28 | 795,139.63 |
| T-07-1 | no transaction sample | – | – | – | – |

Total sampled transactions: 657.

## Limitations

The data cover 3 months [A4]; supplier-level values are annualised estimates (factor 4) [A5], not actual annual spend. Only payments above the publication threshold are published [CPR-05], so split and duplicate results are a lower bound. Rows with a redacted supplier (2,015 rows) [A6] are excluded from every supplier-level test. The notice export is not a contract register [A3], and 6 notices whose buyer name is an upper-case variant of the council's name [A7] are excluded from the match set pending the auditor's decision. The published date is a payment-run timestamp, not an invoice date, so payment terms are not tested across the population; they are tested on the T-03-1 sample by comparing invoice dates from the council's records with payment dates [CPR-38]. No action tracker for agreed audit actions is published [GAP-01]. Award values in notices may be estimates or maxima, so spend above award is an indicator only. Open auditor decision: whether the excluded upper-case buyer-name notices join the match set; if they do, the samples for T-03-1, T-03-2, T-05-1 and T-06-1 could change. The statutory Threshold for goods and services is not set in the rules parameters [A8], so no split, clustering or supplier test runs at the Threshold tier, and steps that refer to the Threshold [CPR-12] [CPR-59] rely on the figure the council applied on each file.

- The spend data covers payments over £500 only; split-purchase and duplicate indicators are lower bounds.
- Notice-based samples rest on Contracts Finder notices, which are not a contract register; 'no notice found' is checked against the council's own register in fieldwork.

## Sources

- A1: `$.population.rows_after_exclusions` in analytics.json = 8,534
- A2: `$.population.total_gbp` in analytics.json = 66,778,104.78
- A3: `$.contracts.register_present` in analytics.json = False
- A4: `$.population.months_covered` in analytics.json = 3
- A5: `$.population.annualisation_factor` in analytics.json = 4
- A6: `$.population.excluded.redacted_supplier.rows` in analytics.json = 2,015
- A7: `$.contracts.rows_dropped_case_variant_of_council_name` in analytics.json = 6
- A8: `$.tests.high_value_suppliers.statutory_tier.skipped` in analytics.json = True
- A9: `$.tests.threshold_clustering.per_threshold[?threshold==25000].band_by_tag.general_procurement.n` in analytics.json = 10
- A10: `$.tests.split_purchases.per_threshold[?threshold==25000].headline_general_procurement.windows` in analytics.json = 39
- A11: `$.tests.split_purchases.per_threshold[?threshold==500000].headline_general_procurement.windows` in analytics.json = 2
- A12: `$.tests.off_contract.headline_general_procurement_no_notice_found.suppliers` in analytics.json = 186
- A13: `$.tests.off_contract.by_match_class.near_contain.suppliers` in analytics.json = 5
- A14: `$.tests.off_contract.by_match_class.near_ratio.suppliers` in analytics.json = 2
- A15: `$.contracts.notices` in analytics.json = 135
- A16: `$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.groups` in analytics.json = 35
- A17: `$.tests.expired_notice_spend.suppliers` in analytics.json = 8
- A18: `$.tests.spend_vs_award.flagged` in analytics.json = 12
