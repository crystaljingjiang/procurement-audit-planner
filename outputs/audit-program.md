# Audit program: procurement, West Berkshire Council

Basis: risk register revision 1 (built 2026-10-14T16:42:30), auditor decisions in `outputs/auditor-comments.md`, plan `outputs/audit-plan.json`. Built 2026-10-14T17:15:49 by `.claude/skills/audit-program/build_pack.py`.

These are **risk indicators to investigate**, not findings of wrongdoing by the council, a service or a supplier. A sampled transaction is selected because it carries an indicator, not because anything is assumed to be wrong with it.

## R-01: Payments just below the £25,000 quotation threshold

Score 6 (Moderate); controls: C-01-1 Officers establish the total value of the requirement, not of a single payment, and follow the quotation route for that value: at least one quote below the quotation threshold [CPR-55], and invitations to quote via the Procurement Portal to at least three sources at or above it [CPR-56] [CPR-57].; C-01-2 Written evidence of each purchase is held [CPR-30] and the progress of each procurement procedure is documented and kept [CPR-29].

### T-01-1 (tests C-01-1, C-01-2)

For each sampled general procurement payment in the band just below the quotation threshold [A9], establish the total value of the underlying requirement from the order and any related orders. Confirm whether that value reached the threshold; if it did, trace the invitations to quote via the Procurement Portal [CPR-56] [CPR-57]; if it did not, confirm at least one quote was sought [CPR-55]. Confirm written evidence of the purchase [CPR-30] and the procedure record [CPR-29] are held.

- **Sample:** `analytics-full/threshold_clustering.csv`; filter: threshold = $.tests.threshold_clustering.per_threshold[?threshold==25000].threshold; tag = general_procurement; sort: Net amount descending; first 10 transactions. Population 10; drawn 10; 10 transactions, £239,427.82. File: `outputs/samples/T-01-1.csv`.
- **PBC:** Purchase orders and invoices for each sampled payment; Quotation records and Procurement Portal invitations for each sampled requirement

## R-02: Same-supplier payments within 30 days that together cross a competition threshold

Score 15 (Extreme (Red)); controls: C-02-1 Requirements are not split or disaggregated to avoid the Procurement Legislation or the Contract Procedure Rules [CPR-11].; C-02-2 The procurement route follows the aggregated value of the requirement: invitations to quote at the quotation tier [CPR-56] [CPR-57], a full competitive tender via the Procurement Portal at the higher tiers [CPR-58] [CPR-59], with an electronic Invitation to Tender above the Threshold [CPR-12] and the resulting contract executed under seal [CPR-47].; C-02-3 Each contract rests on a decision within the Scheme of Delegation [CPR-02] and is approved at the level for its total contract value [CPR-51] [CPR-52] [CPR-53] [CPR-54], with awards over the Key Decision limit treated and recorded as Key Decisions [CPR-04].

### T-02-1 (tests C-02-1, C-02-2, C-02-3)

Every general procurement supplier window in the population is drawn, so windows that only just cross the threshold with few payments are tested as well as the highest-value ones. For each window that crosses the quotation threshold [A10], establish whether the payments sit under one let contract or call-off (which would explain the pattern) or are separate orders for one requirement. If separate orders, establish whether the requirement was split [CPR-11] and whether the route for the combined value was followed [CPR-56] [CPR-57]. Confirm the contract or orders were approved at the level for the total contract value [CPR-51] [CPR-52] and rest on a decision within the Scheme of Delegation [CPR-02].

- **Sample:** `analytics-full/split_purchases.csv`; filter: threshold = $.tests.split_purchases.per_threshold[?threshold==25000].threshold; tag = general_procurement; sort: total_gbp descending; first 39 groups (all payments in each). Population 39; drawn 39; 429 transactions, £2,221,901.37. File: `outputs/samples/T-02-1.csv`.
- **PBC:** Purchase orders and invoices for each sampled window; The contract, call-off or order covering each sampled window, with its approval record

### T-02-2 (tests C-02-1, C-02-2, C-02-3)

For each general procurement supplier window that crosses the tender tier [A11], establish whether the payments sit under one let contract. If they do, confirm that a full competitive tender was run [CPR-58] [CPR-59] with an electronic Invitation to Tender where above the Threshold [CPR-12] and the contract executed under seal where above the Threshold [CPR-47], applying the Threshold figure the council used on the file, that the award was approved at the level for its value [CPR-53] [CPR-54] and recorded as a Key Decision [CPR-04]. If they do not, establish whether the requirement was split [CPR-11].

- **Sample:** `analytics-full/split_purchases.csv`; filter: threshold = $.tests.split_purchases.per_threshold[?threshold==500000].threshold; tag = general_procurement; sort: total_gbp descending; first 25 groups (all payments in each). Population 2; drawn 2; 58 transactions, £3,509,528.75. File: `outputs/samples/T-02-2.csv`.
- **PBC:** Purchase orders and invoices for each sampled window; The contract, call-off or order covering each sampled window, with its approval record; Tender documents, evaluation record and Key Decision record for each contract let above the tender tier; The executed contract and its entry in the sealing register for each contract let above the tender tier

## R-03: High-value general procurement suppliers with no Contracts Finder notice found

Score 15 (Extreme (Red)); controls: C-03-1 The council keeps and publishes a register of contracts with value, duration and supplier [CPR-07]; every award is notified to the Service Lead for Commissioning and Procurement for recording on it [CPR-33], and contract information is reported to the relevant board monthly [CPR-08].; C-03-2 Contracts at or above the quotation threshold are let competitively and advertised as required [CPR-56] [CPR-09], evaluated against criteria notified in advance [CPR-16], awarded on best value [CPR-17], supported by a written procurement report kept for three years where above the Threshold [CPR-27] [CPR-28], and put in writing in an approved form [CPR-31] that includes the clause requiring payment of valid, undisputed invoices within the period the Rules set [CPR-38].; C-03-3 Any waiver of competition or exception to the Rules is justified on the permitted grounds [CPR-18], approved in advance [CPR-19] at the level for its value [CPR-20] [CPR-21] [CPR-22], fully documented [CPR-23], reported to the relevant board where required [CPR-24] and approved by the S151 Officer [CPR-25].; C-03-4 Purchases through a framework or other Purchasing Scheme have prior advice on entitlement and coverage [CPR-26] and, without further competition, prior written approval [CPR-62]; contracts excluded from competition under the Procurement Legislation or the Provider Selection Regime have the required approval or recorded decisions [CPR-60] [CPR-61] [CPR-67].

### T-03-1 (tests C-03-1, C-03-2, C-03-3, C-03-4)

For each sampled general procurement supplier at or above the quotation threshold with no Contracts Finder notice found [A12], check the notice gap against the council's contract register [CPR-07]; a missing notice alone is not a finding. Where a contract exists, confirm the competition route and advertising [CPR-56] [CPR-09], the evaluation record [CPR-16] [CPR-17], the procurement report where above the Threshold [CPR-27] and the written contract [CPR-31], including the payment-terms clause [CPR-38]; for the sampled payments, compare the invoice date with the payment date to establish whether payment was made within the period the clause requires. Where the supplier is used through a Purchasing Scheme, confirm the advice and approval [CPR-26] [CPR-62]. Where there is no contract, establish whether an approved, documented waiver, exception or exclusion covers the spend [CPR-19] [CPR-23] [CPR-60].

- **Sample:** `analytics-full/high_value_suppliers.csv`; filter: dominant_tag = general_procurement; match_class = none; sort: annualised estimate descending; first 25 suppliers (largest 3 payments each). Population 186; drawn 25; 62 transactions, £14,865,447.37. File: `outputs/samples/T-03-1.csv`.
- **PBC:** The council's contract register with values and end dates; The contract, framework call-off or approved waiver covering each sampled supplier; Tender or quotation documents and the evaluation record for each contract found; Purchase orders and invoices for each sampled payment

### T-03-2 (tests C-03-1)

Of the near-match candidates at or above the quotation threshold [A13] [A14], those in general procurement are drawn; any candidate whose dominant tag is a placement or a grant is outside R-03, and candidates below the threshold are never questioned. For each, confirm from the council's contract register [CPR-07] and the supplier's company record whether the spend supplier is the same entity as the notice supplier. Where it is, record the spend as covered by that notice; where it is not, take the supplier through the procedure in the preceding test.

- **Sample:** `analytics-full/near-matches.csv`; filter: dominant_tag = general_procurement; annualised_estimate {">=": "$.tests.off_contract.parameters.threshold"}; sort: annualised_estimate descending; first 25 suppliers (largest 3 payments each). Population 6; drawn 6; 18 transactions, £239,360.31. File: `outputs/samples/T-03-2.csv`.
- **PBC:** The council's contract register with values and end dates; Supplier master file record (legal name and Companies House number) for each sampled supplier

### T-03-3 (tests C-03-1)

Confirm that the council's contract register is published with value, duration and supplier [CPR-07], that awards are notified for recording on it [CPR-33], and that contract information was reported to the relevant board monthly during the spend window [CPR-08]. Confirm whether the register accounts for the notices in the export [A15].

- **Sample:** none. Design and existence test on the register and the board reports; no transactions are needed.
- **PBC:** The council's contract register with values and end dates; Monthly contract reports to the relevant board for the spend window

## R-04: Repeated same-amount payments to one supplier within 7 days

Score 9 (Medium - High (Amber)); controls: C-04-1 Each payment is supported by written evidence of a distinct purchase, an order and an invoice [CPR-30], and repeat invoices are checked before payment.; C-04-2 Published expenditure details reflect the payments made, one line per payment [CPR-05].

### T-04-1 (tests C-04-1, C-04-2)

For each sampled general procurement group of equal payments at different timestamps [A16], trace every payment to a distinct invoice and order [CPR-30] and to its line in the published spend data [CPR-05]. Where two payments trace to one invoice, establish whether the repeat was identified and recovered or credited. Establish how the pre-payment duplicate check works (matching fields and tolerances) and whether it flagged each sampled group before payment; where it did not, record why.

- **Sample:** `analytics-full/duplicates.csv`; filter: tier = different_time; tag = general_procurement; sort: gbp_beyond_first descending; first 15 groups (all payments in each). Population 35; drawn 15; 39 transactions, £525,039.22. File: `outputs/samples/T-04-1.csv`.
- **PBC:** Purchase orders and invoices for each sampled payment; Duplicate-payment exception reports, credit notes or recovery records for the sampled suppliers; Description or configuration of the pre-payment duplicate invoice check, and its exception output for the spend window

## R-05: Spend with suppliers whose only published notices ended before the spend window

Score 8 (Medium - High (Amber)); controls: C-05-1 Any extension of an existing contract that provides for it is approved by the S151 Officer before the original term ends [CPR-63].; C-05-2 New awards and extensions are notified for recording on the contract register, so end dates are current [CPR-33].

### T-05-1 (tests C-05-1, C-05-2)

For each sampled supplier whose only matched notices ended before the spend window [A17], check the end date against the council's contract register [CPR-07] and obtain the current contract, a new award recorded on the register [CPR-33] or the approved extension [CPR-63]. Where none is found, establish the procurement route for the spend [CPR-56] or an approved waiver [CPR-19].

- **Sample:** `analytics-full/expired_notice_spend.csv`; filter: dominant_tag = general_procurement; sort: total_gbp descending; first 15 suppliers (largest 3 payments each). Population 8; drawn 8; 13 transactions, £188,394.86. File: `outputs/samples/T-05-1.csv`.
- **PBC:** The council's contract register with values and end dates; The current contract, new award or approved extension for each sampled supplier; Purchase orders and invoices for each sampled payment

## R-06: Annualised spend above the published award value for single-supplier notices

Score 10 (Medium - High (Amber)); controls: C-06-1 Variations of scope are approved before they take effect: in writing by the Monitoring Officer and S151 Officer below the Threshold [CPR-64], and by the relevant board on their recommendation above it [CPR-65].; C-06-2 Spend against each contract is monitored against its value and an existing budgetary provision is confirmed before commitment [CPR-03].

### T-06-1 (tests C-06-1, C-06-2)

For each sampled supplier whose annualised estimate is at or above the flag ratio of the annual award value [A18], compare cumulative spend under the contract with the contract value on the council's register, noting that the award value may be an estimate or a maximum. Where spend exceeds the contract value, obtain the approved variation at the level for its value [CPR-64] [CPR-65] and confirm the budget provision for the additional spend [CPR-03].

- **Sample:** `analytics-full/spend_vs_award.csv`; filter: flag = True; sort: ratio descending; first 15 suppliers (largest 3 payments each). Population 12; drawn 12; 28 transactions, £795,139.63. File: `outputs/samples/T-06-1.csv`.
- **PBC:** The council's contract register with values and end dates; Contract spend-to-date reports and any approved variations for each sampled supplier; Purchase orders and invoices for each sampled payment

## R-07: Implementation of agreed actions from prior procurement audits is not evidenced in the public papers

Score 2 (Low (Green)); controls: C-07-1 Agreed actions from the contract letting audit [AUD-01] are recorded with owner, due date and status and tracked to implementation, so that weaknesses in documenting procurement procedures [CPR-29] are corrected; no tracker is published [GAP-01].

### T-07-1 (tests C-07-1)

Obtain the contract letting audit report [AUD-01] and the action tracker [GAP-01]; confirm the owner, due date and status of each agreed action and, for actions reported as implemented, obtain the evidence, including the procedure documentation required by [CPR-29].

- **Sample:** none. Document request only: the agreed actions are not in the payment data.
- **PBC:** The contract letting audit report and the action tracker showing owner, due date and status of each agreed action

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

## PBC list

Documents and information to request from the council before fieldwork.

| # | Item | For tests |
|---|---|---|
| 1 | Purchase orders and invoices for each sampled payment | T-01-1, T-03-1, T-04-1, T-05-1, T-06-1 |
| 2 | Quotation records and Procurement Portal invitations for each sampled requirement | T-01-1 |
| 3 | Purchase orders and invoices for each sampled window | T-02-1, T-02-2 |
| 4 | The contract, call-off or order covering each sampled window, with its approval record | T-02-1, T-02-2 |
| 5 | Tender documents, evaluation record and Key Decision record for each contract let above the tender tier | T-02-2 |
| 6 | The executed contract and its entry in the sealing register for each contract let above the tender tier | T-02-2 |
| 7 | The council's contract register with values and end dates | T-03-1, T-03-2, T-03-3, T-05-1, T-06-1 |
| 8 | The contract, framework call-off or approved waiver covering each sampled supplier | T-03-1 |
| 9 | Tender or quotation documents and the evaluation record for each contract found | T-03-1 |
| 10 | Supplier master file record (legal name and Companies House number) for each sampled supplier | T-03-2 |
| 11 | Monthly contract reports to the relevant board for the spend window | T-03-3 |
| 12 | Duplicate-payment exception reports, credit notes or recovery records for the sampled suppliers | T-04-1 |
| 13 | Description or configuration of the pre-payment duplicate invoice check, and its exception output for the spend window | T-04-1 |
| 14 | The current contract, new award or approved extension for each sampled supplier | T-05-1 |
| 15 | Contract spend-to-date reports and any approved variations for each sampled supplier | T-06-1 |
| 16 | The contract letting audit report and the action tracker showing owner, due date and status of each agreed action | T-07-1 |
