# Risk-control matrix: procurement, West Berkshire Council

Basis: risk register revision 1 (built 2026-10-14T16:42:30), auditor decisions in `outputs/auditor-comments.md`, plan `outputs/audit-plan.json`. Built 2026-10-14T17:15:49 by `.claude/skills/audit-program/build_pack.py`.

These are **risk indicators to investigate**, not findings of wrongdoing by the council, a service or a supplier. A sampled transaction is selected because it carries an indicator, not because anything is assumed to be wrong with it.

| Risk | Score | Expected control | Rules | Tests |
|---|---|---|---|---|
| R-01 | 6 (Moderate) | C-01-1: Officers establish the total value of the requirement, not of a single payment, and follow the quotation route for that value: at least one quote below the quotation threshold [CPR-55], and invitations to quote via the Procurement Portal to at least three sources at or above it [CPR-56] [CPR-57]. | CPR-55, CPR-56, CPR-57 | T-01-1 |
| R-01 | 6 (Moderate) | C-01-2: Written evidence of each purchase is held [CPR-30] and the progress of each procurement procedure is documented and kept [CPR-29]. | CPR-29, CPR-30 | T-01-1 |
| R-02 | 15 (Extreme (Red)) | C-02-1: Requirements are not split or disaggregated to avoid the Procurement Legislation or the Contract Procedure Rules [CPR-11]. | CPR-11 | T-02-1, T-02-2 |
| R-02 | 15 (Extreme (Red)) | C-02-2: The procurement route follows the aggregated value of the requirement: invitations to quote at the quotation tier [CPR-56] [CPR-57], a full competitive tender via the Procurement Portal at the higher tiers [CPR-58] [CPR-59], with an electronic Invitation to Tender above the Threshold [CPR-12] and the resulting contract executed under seal [CPR-47]. | CPR-12, CPR-47, CPR-56, CPR-57, CPR-58, CPR-59 | T-02-1, T-02-2 |
| R-02 | 15 (Extreme (Red)) | C-02-3: Each contract rests on a decision within the Scheme of Delegation [CPR-02] and is approved at the level for its total contract value [CPR-51] [CPR-52] [CPR-53] [CPR-54], with awards over the Key Decision limit treated and recorded as Key Decisions [CPR-04]. | CPR-02, CPR-04, CPR-51, CPR-52, CPR-53, CPR-54 | T-02-1, T-02-2 |
| R-03 | 15 (Extreme (Red)) | C-03-1: The council keeps and publishes a register of contracts with value, duration and supplier [CPR-07]; every award is notified to the Service Lead for Commissioning and Procurement for recording on it [CPR-33], and contract information is reported to the relevant board monthly [CPR-08]. | CPR-07, CPR-08, CPR-33 | T-03-1, T-03-2, T-03-3 |
| R-03 | 15 (Extreme (Red)) | C-03-2: Contracts at or above the quotation threshold are let competitively and advertised as required [CPR-56] [CPR-09], evaluated against criteria notified in advance [CPR-16], awarded on best value [CPR-17], supported by a written procurement report kept for three years where above the Threshold [CPR-27] [CPR-28], and put in writing in an approved form [CPR-31] that includes the clause requiring payment of valid, undisputed invoices within the period the Rules set [CPR-38]. | CPR-09, CPR-16, CPR-17, CPR-27, CPR-28, CPR-31, CPR-38, CPR-56 | T-03-1 |
| R-03 | 15 (Extreme (Red)) | C-03-3: Any waiver of competition or exception to the Rules is justified on the permitted grounds [CPR-18], approved in advance [CPR-19] at the level for its value [CPR-20] [CPR-21] [CPR-22], fully documented [CPR-23], reported to the relevant board where required [CPR-24] and approved by the S151 Officer [CPR-25]. | CPR-18, CPR-19, CPR-20, CPR-21, CPR-22, CPR-23, CPR-24, CPR-25 | T-03-1 |
| R-03 | 15 (Extreme (Red)) | C-03-4: Purchases through a framework or other Purchasing Scheme have prior advice on entitlement and coverage [CPR-26] and, without further competition, prior written approval [CPR-62]; contracts excluded from competition under the Procurement Legislation or the Provider Selection Regime have the required approval or recorded decisions [CPR-60] [CPR-61] [CPR-67]. | CPR-26, CPR-60, CPR-61, CPR-62, CPR-67 | T-03-1 |
| R-04 | 9 (Medium - High (Amber)) | C-04-1: Each payment is supported by written evidence of a distinct purchase, an order and an invoice [CPR-30], and repeat invoices are checked before payment. | CPR-30 | T-04-1 |
| R-04 | 9 (Medium - High (Amber)) | C-04-2: Published expenditure details reflect the payments made, one line per payment [CPR-05]. | CPR-05 | T-04-1 |
| R-05 | 8 (Medium - High (Amber)) | C-05-1: Any extension of an existing contract that provides for it is approved by the S151 Officer before the original term ends [CPR-63]. | CPR-63 | T-05-1 |
| R-05 | 8 (Medium - High (Amber)) | C-05-2: New awards and extensions are notified for recording on the contract register, so end dates are current [CPR-33]. | CPR-33 | T-05-1 |
| R-06 | 10 (Medium - High (Amber)) | C-06-1: Variations of scope are approved before they take effect: in writing by the Monitoring Officer and S151 Officer below the Threshold [CPR-64], and by the relevant board on their recommendation above it [CPR-65]. | CPR-64, CPR-65 | T-06-1 |
| R-06 | 10 (Medium - High (Amber)) | C-06-2: Spend against each contract is monitored against its value and an existing budgetary provision is confirmed before commitment [CPR-03]. | CPR-03 | T-06-1 |
| R-07 | 2 (Low (Green)) | C-07-1: Agreed actions from the contract letting audit [AUD-01] are recorded with owner, due date and status and tracked to implementation, so that weaknesses in documenting procurement procedures [CPR-29] are corrected; no tracker is published [GAP-01]. | CPR-29 | T-07-1 |

## Rule coverage

Every rule in `outputs/rules.json` is accounted for: 46 cited by an in-scope risk, a control or a test; 21 not tested, with the reason below.

| Rule | Clause | Reason not tested |
|---|---|---|
| CPR-01 | 3.5 | Social value consideration applies above the Goods & Services Threshold, which is not set in the rules parameters, and leaves no trace in payment data. |
| CPR-10 | 6.14 | Approval and issue of notices is a Procurement Portal workflow record; no payment indicator points at it. |
| CPR-13 | 6.20 | Electronic tender locking and submission format leave no trace in payment data. |
| CPR-14 | 6.21 | Handling of late tenders is a tender-opening record with no trace in payment data. |
| CPR-15 | 6.22 | Electronic tender opening and its audit record sit in the e-tendering system, not in payment data. |
| CPR-32 | 10.3 | Retention of sealed documents by Legal Services is a legal records control outside the spend indicators. |
| CPR-34 | 10.5 | Use of standard clauses is contract content; this audit tests the procurement route and spend, not contract terms. |
| CPR-35 | 10.6 | Approval of amended standard forms is a legal drafting control outside the spend indicators. |
| CPR-36 | 10.7 | Minimum contract clauses are contract content; this audit tests the procurement route and spend, not contract terms. |
| CPR-37 | 10.7.7 | Data Protection Impact Assessments are an information governance control with no trace in payment data. |
| CPR-39 | 11.1 | Relaxation of indemnities is a contract terms decision with no trace in payment data. |
| CPR-40 | 11.3 | Performance bond forms are tender documentation with no trace in payment data. |
| CPR-41 | 11.4 | Bond risk assessments for large contracts are contract file records; no indicator points at them. |
| CPR-42 | 11.5 | Contract risk and insurance assessment is a contract management control with no trace in payment data. |
| CPR-43 | 11.6 | Custody of the Common Seal is a legal governance control outside procurement spend. |
| CPR-44 | 11.7 | Authority to affix the Seal is a legal governance control outside procurement spend. |
| CPR-45 | 11.8 | Attestation of sealing is a legal governance control outside procurement spend. |
| CPR-46 | 11.9 | The sealing register is a legal governance record outside procurement spend. |
| CPR-48 | 11.12 | Signing documents in legal proceedings is outside procurement. |
| CPR-49 | 11.13 | The register of documents executed not under seal is a legal records control outside the spend indicators. |
| CPR-50 | 11.14 | Selection and instruction of Counsel is outside procurement. |

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
