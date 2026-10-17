# Decision Log

Each entry records what we decided and the evidence for it. Code references are to
`src/target.py` and `notebooks/02_data_cleaning.ipynb` (section numbers in brackets).
No competition documentation was available beyond the parquet files, so all rules
below are inferred from the data.

---

## 2026-10-16 — Data structure and first target

### Data structure [§1]
- **Decision:** Use `row_id` (one policy period) as the unit of analysis.
  - **Evidence:** `policy_id` repeats across renewals and mid-term changes; `row_id` is unique and matches `sample_submission`.
- **Decision:** Link claims to periods by `policy_id` and `period_start <= loss_date <= period_end`.
  - **Evidence:** Consecutive periods of a policy are exactly 1 day apart, so both ends are inclusive and no loss date can fall in two periods. 99.7% of motor claims match exactly one period; none match more than one.
- **Check:** No row spans two calendar years, so policy year = exposure year.
- **Check:** Train covers 2021–2024; test covers 2025. Data valuation date is 2024-12-30 (last `report_date`).
- **Check:** 84.75% of test motor policies have earlier periods in train, so history features are possible for most test rows.
- **Decision:** Distinguish new business from renewals through features, not separate units of analysis.
  - **Evidence:** `new_business` and `renewal_count` exist in train and test. Renewals also allow history features (prior claims), which must use only claims reported before the period starts.

### Data quality
- **Decision:** Exclude 297 motor claims (0.26%) that fall outside any policy period. [§4]
  - **Evidence:** 198 have 2020 loss dates (before any policy starts); 99 fall in gaps between a policy's periods.
- **Decision:** Exclude repudiated claims. [§3]
  - **Evidence:** All repudiated claims have zero paid, incurred and recoveries, so excluding them does not change the target. Statuses in the data are only closed, open and repudiated.
- **Decision:** Exclude `renewal_decision` from modelling.
  - **Evidence:** Present in train only; it reflects information known after the period (leakage).

### Target definition [§5]
- **Decision:** Treat `incurred_to_date` as gross of excess; excess = `voluntary_excess` + `compulsory_excess`.
  - **Evidence:** In every motor peril, some closed claims (3–32%) have incurred at or below the excess, so amounts are recorded ground-up.
- **Decision:** Per-claim net cost = max(max(incurred − excess, 0) − recoveries, 0), summed per `row_id`; rows with no claims have target 0.
  - **Evidence:** Applying excess first or recoveries first gives the same motor total.
  - **AI use:** The alternative deduction order was raised during AI-assisted review and verified against the data rather than assumed.
- **Check:** `build_target` matches manual calculations for sample rows in all three lines.
- **Decision:** Define frequency on claims with positive net cost; keep all reported claims (including zero-cost) as a separate count for history features.
  - Frequency = (claims with net cost > 0) / exposure; severity = net cost / (claims with net cost > 0), so frequency × severity = net cost / exposure.
  - Zero-cost claims do not affect the target, but a past claim attempt can still signal risk. Open claims with zero incurred are not treated as zero-cost, since they may develop.
- **Observation:** Closed claims have paid = incurred. Open claims carry case reserves (76–78% of open incurred). Recoveries appear only on closed motor claims (7.3% of closed motor incurred), mainly `own_damage` and `theft`.

---

## 2026-10-17 — Corrections, large losses, development, BI change

### Exposure correction [§2]
- **Decision:** Replace exposure with days / 365 where it disagrees with the period dates (`exposure_clean`).
  - **Evidence:** About 0.5% of train rows use a 360-day year (1.0139 for a 365-day period) and about 0.1% record exposure in days (e.g. 327). Correcting them reduces total exposure by 25–28% in every line and year. Test data has no such rows.
- **Finding:** Net cost per exposure is about 35% higher than first reported (the Oct 16 figures are superseded), but the year-to-year pattern is unchanged.

### Duplicate claims [§3]
- **Decision:** Remove duplicate claim records (604 across all lines), keeping one of each pair.
  - **Evidence:** Different `claim_id`s but identical policy, peril, dates, status and amounts; no ambiguous near-duplicates. 600 of 604 have 2022 loss dates, consistent with a one-off duplication. They inflated 2022 cost by about 2% per line.

### Excess on liability perils [§5]
- **Decision:** Do not deduct excess from `bodily_injury` and `third_party_prop`.
  - **Evidence:** The data cannot settle this. The schema follows UK motor insurance (voluntary/compulsory excess, NCB), where excess applies to own-damage cover, not third-party liability.
  - **Sensitivity:** Deducting excess on liability lowers the motor total by 4.6% (404.1m → 385.5m before de-duplication), mostly from `third_party_prop` (−12%).

### Corrected net cost per exposure [§6]
Uncapped, de-duplicated, corrected exposure, no excess on liability:

| Year | Motor | Buildings | Contents |
|---|---|---|---|
| 2021 | 530 | 363 | 89 |
| 2022 | 541 | 382 | 89 |
| 2023 | 554 | 410 | 100 |
| 2024 | 421 | 428 | 100 |

### Large losses [§7]
- **Decision:** Cap individual motor claims at 500,000 for modelling; reallocate the excess as a loading (15.4 per exposure).
  - **Evidence:** The 99.9th percentile of BI incurred is about 420,000; 4 claims exceed the cap. One open 2023 BI claim of 11.9m alone is 6% of all BI cost.

### Development [§8]
- **Decision:** Gross up reported cost by reporting-delay completeness factors, built from 2021 report lags by peril (count-based).
  - **Evidence:** Non-BI perils are 94–100% complete in 2024, and their 2024 cost is in line with earlier years, so the 2024 motor drop is driven by BI (56% complete). Amount-weighted completeness differs by under 2%, so count-based is kept.
  - **Result:** Motor cost per exposure (capped, before loading) moves from 527 / 541 / 497 / 420 to 527 / 543 / 509 / 518.
  - **Limitation:** One valuation snapshot only, so case-reserve development on open claims cannot be estimated.

### Bodily injury severity change [§9]
- **Finding:** BI frequency is stable (10.5–11.4 per 1,000 exposures), but severity drops about 19% (mean) and 25% (median) from loss year 2023, with a clear step at 2023 Q1. The drop holds for claims reported within 365 days, open and closed claims have similar severity, and no other motor peril shows it.
- **Decision:** Treat 2023 as a change in the BI cost environment (consistent with a small-claims reform). On-level 2021–2022 BI losses by about 0.83 before modelling.
- **Assumption:** Post-reform BI severity trend 0% (one year observed); pre-reform trend of about 5% as sensitivity.

### Motor trends [§10]
- **Finding:** Gross-of-excess severity trends per year: glass_hail +8%, third_party_prop +8%, own_damage +4%, theft +3%. Net-of-excess medians rise faster (e.g. own_damage 13%) because of the fixed-excess leverage effect.
- **Finding:** Frequency is flat or slightly down; own_damage and third_party_prop step down in 2023. Not yet trended pending a portfolio-mix check.

---

## Open questions
- Match rates and unmatched counts for buildings and contents (computed in notebook §4; to be recorded here).
- Is the 2023 drop in own_damage / third_party_prop frequency portfolio mix (driver_assist, telematics, new business)?
- Completeness adjustment and trend split (frequency vs severity, weather vs inflation) for buildings and contents.
- Contents cost jumps about 12% in 2023: which perils?
- `customer_service_contacts`: possible leakage (present in test, but may respond to claims during the period).
- `weather`: are 2025 values available for test addresses?
- `prior_claims_5y` (customers) vs history built from the claims table.
- Evaluation metric for the competition (affects whether the large-loss loading matters).
