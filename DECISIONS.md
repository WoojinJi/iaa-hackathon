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
- **Check:** After de-duplication, only 51 motor rows have more than one claim on the same loss date (about 40 with different perils), so applying excess per claim rather than per event has negligible effect.
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
- **Finding:** Frequency is flat or slightly down; own_damage and third_party_prop step down in 2023. See Motor frequency below.

### Motor frequency [notebook 03]
- **Finding:** own_damage and third_party_prop frequency step down in 2023 (about −7% and −5%) and stay at the lower level in 2024. Portfolio mix changes only gradually (driver_assist, telematics, cover type), and the drop appears within every driver_assist and telematics group, so mix does not explain it.
- **Decision:** Treat 2023 as a level shift, not a trend. On-level 2021–2022 frequency by 0.93 (own_damage) and 0.95 (third_party_prop); no frequency trend for other perils.
- **Observation:** Telematics opt-in policies have higher frequency than others, possibly adverse selection.

### Motor modelling target [notebook 03, src/target.py]
- **Decision:** Build the motor target at 2025 level per claim: trend incurred and recoveries by peril severity trend (excess fixed), apply the BI reform factor (0.83) and frequency shift (0.93 / 0.95) to pre-2023 losses, deduct excess (none on liability perils), cap at 500,000. Immaturity is handled by weighting exposure with the year's completeness (1.000 / 0.997 / 0.979 / 0.816), not by grossing up individual rows.
  - **Evidence:** Adjusted cost per weighted exposure is consistent across years: 550.8 / 548.4 / 551.0 / 540.0 (2021–2024), compared with 550.7 / 547.0 / 539.2 / 440.6 before the completeness weight.
  - **Limitation:** 2024 is about 2% lower, consistent with case-reserve development on open BI claims and amount-based completeness being about 2% below count-based; not adjusted.
- **Expected 2025 level:** about 548 per exposure, plus a large-loss loading of about 15.

---

## 2026-10-18 — Modelling plan (set before seeing any model results)

### Evaluation and validation
- **Decision:** Use Tweedie deviance with power 1.5 as the primary metric, reported as D² (1 − model deviance / deviance of a constant-rate model).
  - **Evidence:** This is the competition's scoring metric. The target has many zeros and a long right tail, which suits a Tweedie distribution; MSE would be dominated by a few large claims, and Cp/AIC assume a normal-error linear model.
- **Decision:** Main validation is out-of-time: train on policy years 2021–2023, evaluate on 2024 using the completeness-weighted exposure.
  - **Evidence:** This mirrors the real task (past years predicting a future year). 2024 is immature, so its weight reflects the share of claims reported so far.
- **Decision:** Secondary validation is 5-fold cross-validation grouped by `policy_id`.
  - **Evidence:** Renewals of the same policy are correlated; splitting them across train and test folds would overstate performance.
- **Supporting checks:** overall actual-to-expected ratio (should be close to 1.00), lift chart, double lift between models, Gini, and actual-to-expected by key segments (young drivers, flood zones, new business).
- **Guardrail:** Model choice is based on validation results, not the Kaggle leaderboard, to avoid overfitting the public test split. The only exception is the open excess question, which validation data cannot answer.

### Candidate models
- **Tweedie GLM** (power 1.5, log link), target = adjusted cost per weighted exposure, weight = exposure × completeness. Baseline; coefficients give rating relativities that can be explained directly.
- **LightGBM** with Tweedie objective (power 1.5), same target and weights. Captures non-linear effects and interactions.
- **Combination:** either a weighted average of the two (blend weight chosen on 2024 validation) or LightGBM trained to correct the GLM (GLM prediction as offset).
- **Decision rule:** prefer the simpler, more explainable model unless the more complex one improves validation deviance meaningfully and passes the segment checks.

### Prediction
- **Row prediction** = (predicted cost per exposure + large-loss loading) × test `exposure`, floored at 0; one CSV for all three lines.
- **Feature selection:** variables are kept if they improve cross-validated deviance and their effect is actuarially sensible (sign and size); LightGBM features are reviewed with importance and SHAP.


## 2026-10-18 — Buildings and contents adjustments [notebook 04]

### Development
- **Finding:** Only buildings `subsidence` is long-tailed (median report lag 85 days, 90th percentile 254); its 2024 completeness is 0.69. All other home perils are at least 95% complete in 2024.

### Severity trends (gross of excess)
- **Decision:** Buildings: escape_of_water 8%, flood 7%, storm 8%, subsidence 7%, accidental_damage 3%, fire 0% a year. Contents: theft 4%, flood 5%, escape_of_water 3%, accidental_damage 3%.
  - **Evidence:** Quarterly medians rise gradually (e.g. escape_of_water 3.3–3.6k in 2021 to 4.0–4.6k in 2024), and the 2023–24 vs 2021–22 change matches what a steady trend implies, so these are treated as inflation, not a step change. Storm severity rises mainly from late 2023 (sensitivity).

### Frequency and weather
- **Finding:** Frequency rises strongly with the matching weather variable: subsidence 3.1x from lowest to highest `dry_summer_index` quintile, flood 2.5x (`rainfall_mm`), storm 1.9x (`wind_exposure_index`), fire 1.8x (`wildfire_index`). The rise in subsidence frequency over 2021–2024 tracks drier summers.
- **Decision:** No frequency trend for weather-driven perils; weather enters the model as features. 2025 weather is available for 100% of test addresses.
  - **Practicality note:** In real pricing, next year's weather is unknown. We will report a sensitivity using each address's average past weather instead of 2025 values.
- **Open:** Buildings fire and contents theft frequency rise steadily (about 8% and 3% a year) without a weather explanation. Decide on a frequency trend from out-of-time validation (do models trained on 2021–23 under-predict these perils in 2024?).

### Large losses
- **Decision:** Buildings cap 300,000 (just above the 99.9th percentile, the same rule as motor), large-loss loading 2.3 per exposure; contents no cap (maximum claim 111,300). Final cap levels to be chosen by validation among none / 99.9th percentile rule / lower.

### Check: 2025-level cost per weighted exposure
| Year | Motor | Buildings | Contents |
|---|---|---|---|
| 2021 | 550.8 | 456.4 | 106.1 |
| 2022 | 548.4 | 452.9 | 101.1 |
| 2023 | 551.0 | 460.6 | 109.0 |
| 2024 | 540.0 | 488.5 | 108.1 |

- Motor is consistent within 2%. Home lines vary by about 8%, which is expected because weather differs by year. Buildings 2024 is high mainly because of subsidence (+18.6 per exposure), which relies on the 0.69 completeness estimate; reported subsidence cost alone is in line with earlier years. Contents 2022 is low because of flood.
- **Expected 2025 level (including large-loss loading):** motor about 564, buildings about 467, contents about 106 per exposure.
- **Limitation:** Buildings 2024 subsidence completeness is the main source of uncertainty for buildings.
---

## Open questions
- Completeness adjustment and trend split (frequency vs severity, weather vs inflation) for buildings and contents.
- Contents cost jumps about 12% in 2023: which perils?
- `customer_service_contacts`: possible leakage (present in test, but may respond to claims during the period).
- `weather`: are 2025 values available for test addresses?
- `prior_claims_5y` (customers) vs history built from the claims table.
- Evaluation metric for the competition (affects whether the large-loss loading matters).
- Excess on liability perils: posted on the Kaggle forum (Oct 18); if unanswered, compare both versions on the leaderboard.
- Final model structure (GLM, LightGBM, or combination): to be decided by Oct 21 using the rules above.