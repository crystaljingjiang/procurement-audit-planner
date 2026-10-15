# Procurement risk register: West Berkshire Council

**Revision 1: applies the auditor's decisions.** Built 2026-10-14T16:42:30.

Auditor approved all seven risks (R-01 to R-07) without amendment; no changes and no new risks.

Changed in this revision:

- nothing; every risk was approved as drafted

Inputs: `outputs/risk-ratings.json` sha256 e3a42d28dc06 · `outputs/analytics.json` sha256 e244d2530621 · `outputs/history.json` sha256 5048a6da68fa · `outputs/rules.json` sha256 256f615d3939

These are **risk indicators to investigate**, not findings of wrongdoing by the council, a service or a supplier.

## Method

- Council 5×5 method from the Risk Management Strategy 2024–2027 as recorded in history.json: likelihood LIK-1…5, impact IMP-n-DIM (Table 1), matrix MX-I1…5 (Figure 1), bands BAND-* (Table 4).
- Score = likelihood × impact, checked against the scores printed in Figure 1. Band and RAG from Table 4; 'matrix label' is the Figure 1 cell name.
- Likelihood follows the rubric in `.claude/skills/risk-assessment/SKILL.md`; each signal is evaluated here from analytics.json. A repeat finding (a cited audit or follow-up with an adverse opinion) adds one point, capped at 5, and is stated on the risk.
- Every figure is filled from analytics.json; [M*] marks a metric listed under the risk's evidence.

**Conflicts inside the council's scoring method** (one value used, the other marked; nothing resolved silently):

- Band names differ between the matrix and Table 4 (Figure 1 'High' = Table 4 'Medium - High'). **Used:** Table 4 band and RAG as the band; the Figure 1 name is shown as 'matrix label'. [DISC-03]
- Corporate Risk Register entry is printed as Table 4 'Extreme' (15 -25) [BAND-EXTREME] and as 'score 9 or above' [ESC-CRR-1]. **Used:** Table 4 for the band and escalation. **Marked:** risks scoring 9 or above but below 15 carry ‡ (CRR-level under ESC-CRR-1). [DISC-04]
- Financial impact ranges conflict: £ ranges of adjacent levels share their end points; % of budget ranges overlap (level 3 up to 0.3% vs level 4 from 0.25%). **Used:** the £ ranges; a value on a shared end point takes the higher level. **Not used:** the % ranges (no annual budget figure is in the papers). The £ basis is value exposed to the indicator, not a loss. [DISC-02, DISC-09]
- 'Medium (2)' in SM-10 conflicts with Table 1 / Figure 1, which place Medium at 3. **Used:** Medium = 3. **Marked:** the prose numbering is not used. [DISC-01]

## Summary

| ID | Risk | L | I | Score | Matrix label | Band | Scope |
|---|---|---|---|---|---|---|---|
| R-01 | Payments just below the £25,000 quotation threshold | 2 | 3 | 6 | Moderate | Moderate | in |
| R-02 | Same-supplier payments within 30 days that together cross a competition threshold | 3 | 5 | 15 | Extreme | Extreme (Red) | in |
| R-03 | High-value general procurement suppliers with no Contracts Finder notice found | 3 | 5 | 15 | Extreme | Extreme (Red) | in |
| R-04 | Repeated same-amount payments to one supplier within 7 days | 3 | 3 | 9 ‡ | High | Medium - High (Amber) | in |
| R-05 | Spend with suppliers whose only published notices ended before the spend window | 2 | 4 | 8 | High | Medium - High (Amber) | in |
| R-06 | Annualised spend above the published award value for single-supplier notices | 2 | 5 | 10 ‡ | High | Medium - High (Amber) | in |
| R-07 | Implementation of agreed actions from prior procurement audits is not evidenced in the public papers | 1 | 2 | 2 | Low | Low (Green) | in |

‡ CRR-level under ESC-CRR-1 ('score 9 or above'), not under Table 4. See Method.

## R-01: Payments just below the £25,000 quotation threshold

Payments fall in the band just below the threshold at which invitations to quote via the Procurement Portal are required [CPR-56] [CPR-57]. This is an indicator to investigate, not evidence that any purchase was structured to stay below the threshold [M1].

- **Likelihood 2 – Unlikely.** 46 payments sit in the band below the threshold [M1], 10 of them in general procurement [M2], but the band does not beat its comparator of 52 payments just above the threshold [M3], so the indicator is present without showing clustering. L3 needs the band to beat its comparator. At the higher competition-triggering threshold the band is empty [M4].
  - Signals: ✓ $.tests.threshold_clustering.per_threshold[?threshold==25000].band_count > 0 → 46 > 0; ✓ $.tests.threshold_clustering.per_threshold[?threshold==25000].band_by_tag.general_procurement.n > 0 → 10 > 0; ✓ $.tests.threshold_clustering.per_threshold[?threshold==25000].band_count < $.tests.threshold_clustering.per_threshold[?threshold==25000].comparator_count → 46 < 52
- **Impact 3 – Medium.** Value exposed (not a loss) is the general procurement spend in the band, £239,428 [M5], which falls in the council's Medium financial band [IMP-3-FIN]. Placement and grant payments in the band are left out of the basis because they may be exempt from competition [CPR-66].
  - £ basis £239,428 [M5] → council £ band level 3
- **Score 6**: matrix label Moderate; band Moderate.
- **Evidence:**
  - CPR-56 (clause App B row B1): goods or services, Total Value (ex VAT) £25,000 or more and less than the Threshold
  - CPR-57 (clause App B row B2): works, concession or light touch, Total Value (ex VAT) £25,000 or more and less than £500,000
  - M1 `$.tests.threshold_clustering.per_threshold[?threshold==25000].band_count` = 46
  - M2 `$.tests.threshold_clustering.per_threshold[?threshold==25000].band_by_tag.general_procurement.n` = 10
  - M3 `$.tests.threshold_clustering.per_threshold[?threshold==25000].comparator_count` = 52
  - M4 `$.tests.threshold_clustering.per_threshold[?threshold==500000].band_count` = 0
  - M5 `$.tests.threshold_clustering.per_threshold[?threshold==25000].band_by_tag.general_procurement.gbp` = 239,427.82
  - IMP-3-FIN: 3 Medium – Financial loss to Council: 0.1% - 0.3% annual WBC budget £175k -500k
  - CPR-66 (clause App C row F): social care services listed in row F a)–f) (individual placements, packages, Shared Lives)
  - CPR-55 (clause App B row A): Total Value (ex VAT) above £1,000 and less than £25,000
  - CPR-06 (clause 5.2): invitation to tender for a goods/services contract with value exceeding £5,000
  - CPR-53 (clause App A row 3): Total Contract Value above £500,000 and less than £2.5million
  - CPR-54 (clause App A row 4): Total Contract Value £2.5million or more
  - M6 `$.tests.threshold_clustering.per_threshold[?threshold==2500000].band_count` = 0
- **Proposed focus:** For the general procurement payments in the band [M2], confirm the total contract value of the underlying requirement and whether the quotation route required by [CPR-56] or [CPR-57] was followed.
- **Proposed scope:** in. Recommended in at low effort because the band items can be pulled with the split-purchase sample [CPR-56]. The lower thresholds [CPR-55] [CPR-06] are not competition-triggering and are not rated separately; the upper thresholds [CPR-53] [CPR-54] have empty bands [M6].

## R-02: Same-supplier payments within 30 days that together cross a competition threshold

Groups of payments to one supplier, each below a competition-triggering threshold, combine within a short window to reach or exceed it [M1]. This pattern is an indicator to check against the anti-disaggregation rule [CPR-11]; many windows will reflect legitimate recurring invoicing under one contract.

- **Likelihood 3 – Likely.** In general procurement, 39 supplier windows combine to £25,000 or more [M1] and 2 reach £500,000 [M2]. L4 is not supported: threshold clustering at the same threshold does not beat its comparator [M3]. Prior coverage of contract letting was Reasonable Assurance [AUD-01], which is coverage, not a repeat finding.
  - Signals: ✓ $.tests.split_purchases.per_threshold[?threshold==25000].headline_general_procurement.windows > 0 → 39 > 0; ✓ $.tests.split_purchases.per_threshold[?threshold==500000].headline_general_procurement.windows > 0 → 2 > 0
- **Impact 5 – Critical.** Value exposed (not a loss) in the general procurement windows at the lower competition threshold is £2,221,901 [M4], which falls in the council's Critical financial band [IMP-5-FIN]. Placement windows [M5] are excluded from the basis because periodic care fees legitimately recur [CPR-66].
  - £ basis £2,221,901 [M4] → council £ band level 5
- **Score 15**: matrix label Extreme; band Extreme (Red).
- **Evidence:**
  - M1 `$.tests.split_purchases.per_threshold[?threshold==25000].headline_general_procurement.windows` = 39
  - CPR-11 (clause 6.16): any requirement that is split or disaggregated
  - M2 `$.tests.split_purchases.per_threshold[?threshold==500000].headline_general_procurement.windows` = 2
  - M3 `$.tests.threshold_clustering.per_threshold[?threshold==25000].comparator_count` = 52
  - AUD-01: Contract Letting – Reasonable Assurance (End of March 2025)
  - M4 `$.tests.split_purchases.per_threshold[?threshold==25000].headline_general_procurement.gbp` = 2,221,901.37
  - IMP-5-FIN: 5 Critical – Financial loss to Council: > 1% annual WBC budget >£2m
  - M5 `$.tests.split_purchases.per_threshold[?threshold==25000].by_tag.care_or_education_placement.windows` = 126
  - CPR-66 (clause App C row F): social care services listed in row F a)–f) (individual placements, packages, Shared Lives)
  - CPR-56 (clause App B row B1): goods or services, Total Value (ex VAT) £25,000 or more and less than the Threshold
  - CPR-58 (clause App B row C): works, concession or light touch, Total Value (ex VAT) above £500,000 and less than the Threshold
- **Proposed focus:** For the highest-value general procurement windows [M4], establish whether the payments sit under one let contract (which explains the pattern) or are separate orders for one requirement, and if the latter whether the route in [CPR-56] or [CPR-58] was followed [CPR-11].
- **Proposed scope:** in. Recommended in: the anti-disaggregation rule [CPR-11] is directly testable from the spend data and the general procurement value exposed is the largest transaction-level indicator [M4].

## R-03: High-value general procurement suppliers with no Contracts Finder notice found

Suppliers whose annualised spend estimate is at or above the competition threshold have no matching published notice [M1]. The notice export is not a contract register [M2], so no notice found is an indicator to check against the council's register, never evidence of off-contract spend.

- **Likelihood 3 – Likely.** 186 general procurement suppliers above the threshold have no notice found [M1]. The rating is capped at L3 because no contract register is available [M2]. The match set also excludes 6 notices whose buyer name is an upper-case variant of the council's name [M3], pending the auditor's decision; including them may reduce the count.
  - Signals: ✓ $.tests.off_contract.headline_general_procurement_no_notice_found.suppliers > 0 → 186 > 0
- **Impact 5 – Critical.** Value exposed (not a loss) is the annualised estimate for those suppliers, £97,905,912 [M4], an extrapolation of three months of spend that falls in the council's Critical financial band [IMP-5-FIN].
  - £ basis £97,905,912 [M4] → council £ band level 5
- **Score 15**: matrix label Extreme; band Extreme (Red).
- **Evidence:**
  - M1 `$.tests.off_contract.headline_general_procurement_no_notice_found.suppliers` = 186
  - M2 `$.contracts.register_present` = False
  - M3 `$.contracts.rows_dropped_case_variant_of_council_name` = 6
  - M4 `$.tests.off_contract.headline_general_procurement_no_notice_found.annualised_estimate_gbp` = 97,905,911.80
  - IMP-5-FIN: 5 Critical – Financial loss to Council: > 1% annual WBC budget >£2m
  - CPR-07 (clause 5.2.1): all contracts in progress or awarded
  - CPR-56 (clause App B row B1): goods or services, Total Value (ex VAT) £25,000 or more and less than the Threshold
  - CPR-19 (clause 7.3): any waiver of or exception to these Rules
- **Proposed focus:** Request the council's contract register [CPR-07] and match the highest-value suppliers with no notice found [M4]; for any without a contract, confirm the procurement route or approved exception [CPR-56] [CPR-19].
- **Proposed scope:** in. Recommended in because the value exposed is in the Critical band [IMP-5-FIN]; the result should be re-run once the auditor decides on the excluded notices [M3]. Suppliers below the publication threshold are not questioned.

## R-04: Repeated same-amount payments to one supplier within 7 days

Payments of the same amount to the same supplier at different times within a short gap [M1] are an indicator of possible duplicate payment to investigate; many will be legitimate repeat invoices [CPR-30].

- **Likelihood 3 – Likely.** 35 general procurement groups of equal payments at different timestamps [M1]. Same-timestamp batches are treated as lower signal and not relied on [M2]. No second test points at this theme, so L4 is not supported. Accounts payable was last audited with Reasonable Assurance [AUD-11], which is coverage, not a repeat finding.
  - Signals: ✓ $.tests.duplicates.per_tier.different_time.by_tag.general_procurement.groups > 0 → 35 > 0
- **Impact 3 – Medium.** Value exposed (not a loss) is the value beyond the first payment in each general procurement group, £299,374 [M3], in the council's Medium financial band [IMP-3-FIN].
  - £ basis £299,374 [M3] → council £ band level 3
- **Score 9**: matrix label High; band Medium - High (Amber); ‡ CRR-level under ESC-CRR-1.
- **Evidence:**
  - M1 `$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.groups` = 35
  - CPR-30 (clause 10.1): any purchase
  - M2 `$.tests.duplicates.per_tier.same_timestamp.by_tag.general_procurement.groups` = 33
  - AUD-11: Accounts Payable – Reasonable Assurance (End of December 2025)
  - M3 `$.tests.duplicates.per_tier.different_time.by_tag.general_procurement.gbp_beyond_first` = 299,374.24
  - IMP-3-FIN: 3 Medium – Financial loss to Council: 0.1% - 0.3% annual WBC budget £175k -500k
- **Proposed focus:** For the general procurement groups [M1], trace each payment to a distinct invoice and order [CPR-30] and confirm any recovery of duplicates.
- **Proposed scope:** in. Recommended in: a direct transaction test with value exposed in the Medium band [IMP-3-FIN], complementing the Reasonable Assurance accounts payable audit [AUD-11].

## R-05: Spend with suppliers whose only published notices ended before the spend window

Suppliers paid in the window match only notices that had ended before it began [M1]. This is an indicator of possible spend after expiry without an approved extension [CPR-63]; a newer contract or extension may exist with no notice.

- **Likelihood 2 – Unlikely.** 8 suppliers show the indicator [M1]. L3 cannot be shown because analytics.json gives no general procurement breakdown for this test, and the notice set is not a contract register [M2]. The match set also excludes 6 upper-case buyer-name notices [M3] pending the auditor's decision, which could change which suppliers appear.
  - Signals: ✓ $.tests.expired_notice_spend.suppliers > 0 → 8 > 0
- **Impact 4 – Major.** Value exposed (not a loss) is the annualised estimate for these suppliers, £945,399 [M4] (actual window spend £236,350), in the council's Major financial band [IMP-4-FIN].
  - £ basis £945,399 [M4] → council £ band level 4
- **Score 8**: matrix label High; band Medium - High (Amber).
- **Evidence:**
  - M1 `$.tests.expired_notice_spend.suppliers` = 8
  - CPR-63 (clause App C row D): extension of an existing contract that provides for such extension
  - M2 `$.contracts.register_present` = False
  - M3 `$.contracts.rows_dropped_case_variant_of_council_name` = 6
  - M4 `$.tests.expired_notice_spend.annualised_estimate_gbp` = 945,399.44
  - IMP-4-FIN: 4 Major – Financial loss to Council: 0.25% - 1% annual WBC budget £500k £2M
- **Proposed focus:** For each supplier listed [M1], obtain the current contract or the approved extension [CPR-63].
- **Proposed scope:** in. Recommended in: a short supplier list that tests the extension approval rule [CPR-63] at low effort; re-run after the auditor decides on the excluded notices [M3].

## R-06: Annualised spend above the published award value for single-supplier notices

For suppliers matched to one active notice with a stated award value, the annualised spend estimate is at least the flag ratio of the annual award value [M1]. This is an indicator of possible spend beyond the award without an approved variation [CPR-64] [CPR-65]; award values may be estimates or maxima.

- **Likelihood 2 – Unlikely.** 12 of 22 compared suppliers are flagged [M1] [M2]. L3 cannot be shown because analytics.json gives no general procurement breakdown for this test, and the ratio extrapolates three months against award values that may be maxima. The comparison set excludes 6 upper-case buyer-name notices [M3] pending the auditor's decision.
  - Signals: ✓ $.tests.spend_vs_award.flagged > 0 → 12 > 0
- **Impact 5 – Critical.** Value exposed (not a loss) is the annualised estimate for flagged suppliers, £5,353,417 [M4], in the council's Critical financial band [IMP-5-FIN]; the amount above the award is smaller and is not computed in analytics.json.
  - £ basis £5,353,417 [M4] → council £ band level 5
- **Score 10**: matrix label High; band Medium - High (Amber); ‡ CRR-level under ESC-CRR-1.
- **Evidence:**
  - M1 `$.tests.spend_vs_award.flagged` = 12
  - CPR-64 (clause App C row E): variation of scope of an existing contract, contract value below the Threshold
  - CPR-65 (clause App C row E): variation of scope of an existing contract, contract value greater than the Threshold
  - M2 `$.tests.spend_vs_award.suppliers_compared` = 22
  - M3 `$.contracts.rows_dropped_case_variant_of_council_name` = 6
  - M4 `$.tests.spend_vs_award.flagged_annualised_estimate_gbp` = 5,353,417.28
  - IMP-5-FIN: 5 Critical – Financial loss to Council: > 1% annual WBC budget >£2m
- **Proposed focus:** For flagged suppliers [M1], compare cumulative spend with the contract value and obtain any approved variation [CPR-64] [CPR-65].
- **Proposed scope:** in. Recommended in: the only data test of the variation approval rules [CPR-64] [CPR-65], with value exposed in the Critical band [IMP-5-FIN].

## R-07: Implementation of agreed actions from prior procurement audits is not evidenced in the public papers

Contract letting was audited with Reasonable Assurance [AUD-01], but no action tracker or status of agreed actions is published [GAP-01], so whether any agreed procurement actions were implemented cannot be confirmed from the papers.

- **Likelihood 1 – Rare.** No data indicator exists for this theme; only a gap is cited [GAP-01]. The prior opinion was Reasonable Assurance [AUD-01], which is coverage, not an adverse finding.
- **Impact 2 – Minor.** Unimplemented actions from a Reasonable Assurance audit would leave a compliance weakness with a low possibility of challenge [IMP-2-CMP]; there is no £ exposure to measure [GAP-01].
- **Score 2**: matrix label Low; band Low (Green).
- **Evidence:**
  - AUD-01: Contract Letting – Reasonable Assurance (End of March 2025)
  - GAP-01: Agreed actions / action tracker (theme, due date, status, owner, overdue)
  - IMP-2-CMP: 2 Minor – Compliance (litigation, regulatory, contract): Low possibility of legal challenge. Low possibility regulatory interest
- **Proposed focus:** Request the action tracker for the contract letting audit [AUD-01] and confirm the status of any agreed actions [GAP-01].
- **Proposed scope:** in. Recommended in as a document request only, because the missing tracker [GAP-01] also limits any future repeat-finding uplift.

## Risks excluded by the builder

None.

## Auditor decisions

Record a decision for every risk in `outputs/auditor-comments.md` (Approve, Amend or Reject, with a comment for Amend and Reject), then ask for the risk-assessor to be re-run. It re-issues this register as the next revision, applying exactly what you asked and nothing else. The audit program is not built until every risk is decided and applied.

| Risk ID | Decision recorded | Comment |
|---|---|---|
| R-01 | Approve |  |
| R-02 | Approve |  |
| R-03 | Approve |  |
| R-04 | Approve |  |
| R-05 | Approve |  |
| R-06 | Approve |  |
| R-07 | Approve |  |
