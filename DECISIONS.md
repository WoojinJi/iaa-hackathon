# Decision Log

Each entry records what we decided and the evidence for it. Code references are to `src/` and the notebooks
(section or notebook numbers in brackets). AI interactions behind these decisions are in `AI_USE_LOG.md`
(entry numbers in brackets).

The data came as parquet files only. Rules were first inferred from the data; the competition overview and
host answers on the Kaggle forum are cited where they settled a question.

**Records by date.** Figures dated before Oct 19 were computed without excess on liability perils (the
assumption at the time); they are kept as the record of that stage. The current state of every assumption is
in the **Assumptions register** at the end.

---

## 2026-10-16 — Data structure and first target

### Data structure [02 §1]
- **Decision:** Use `row_id` (one policy period) as the unit of analysis.
  - **Evidence:** `policy_id` repeats across renewals and mid-term changes; `row_id` is unique and matches `sample_submission`.
- **Decision:** Link claims to periods by `policy_id` and `period_start <= loss_date <= period_end`.
  - **Evidence:** Consecutive periods of a policy are exactly 1 day apart, so both ends are inclusive and no loss date can fall in two periods. 99.7% of motor claims match exactly one period; none match more than one.
- **Check:** No row spans two calendar years, so policy year = exposure year.
- **Check:** Train covers 2021–2024; test covers 2025. Data valuation date is 2024-12-30 (last `report_date`).
- **Check:** 84.75% of test motor policies have earlier periods in train, so history features are possible for most test rows.
- **Decision:** Distinguish new business from renewals through features, not separate units of analysis.
  - **Evidence:** `new_business` and `renewal_count` exist in train and test. Renewals also allow history features, which must use only claims known before the period starts.

### Data quality
- **Decision:** Exclude 297 motor claims (0.26%) that fall outside any policy period. [02 §4]
  - **Evidence:** 198 have 2020 loss dates (before any policy starts); 99 fall in gaps between a policy's periods.
- **Decision:** Exclude repudiated claims. [02 §3]
  - **Evidence:** All repudiated claims have zero paid, incurred and recoveries, so excluding them does not change the target. Statuses in the data are only closed, open and repudiated.
- **Decision:** Exclude `renewal_decision` from modelling.
  - **Evidence:** Present in train only; it reflects information known after the period (leakage).

### Target definition [02 §5]
- **Decision:** Treat `incurred_to_date` as gross of excess; excess = `voluntary_excess` + `compulsory_excess`.
  - **Evidence:** In every motor peril, some closed claims (3–32%) have incurred at or below the excess, so amounts are recorded ground-up.
- **Decision:** Per-claim net cost = max(max(incurred − excess, 0) − recoveries, 0), summed per `row_id`; rows with no claims have target 0.
  - **Evidence:** Applying excess first or recoveries first gives the same motor total. [AI 1]
- **Check:** `build_target` matches manual calculations for sample rows in all three lines.
- **Decision:** Keep all reported claims (including zero-cost) for frequency measurement and history features.
  - **Superseded wording (Oct 19):** frequency is measured on all reported claims; counting only claims with net > 0 mixes in the fixed-excess effect, which the severity trend on gross amounts already handles. [AI 42]
- **Observation:** Closed claims have paid = incurred. Open claims carry case reserves (76–78% of open incurred). Recoveries appear only on closed motor claims (7.3% of closed motor incurred), mainly `own_damage` and `theft`.
- **Check:** After de-duplication, only 51 motor rows have more than one claim on the same loss date (about 40 with different perils), so applying excess per claim rather than per event has negligible effect.

---

## 2026-10-17 — Corrections, large losses, development, BI change

### Exposure correction [02 §2]
- **Decision:** Replace exposure with days / 365 where it disagrees with the period dates (`exposure_clean`).
  - **Evidence:** About 0.5% of train rows use a 360-day year (1.0139 for a 365-day period) and about 0.1% record exposure in days (e.g. 327). Correcting them reduces total exposure by 25–28% in every line and year. Test data has no such rows. [AI 8]
- **Finding:** Net cost per exposure is about 35% higher than first reported (the Oct 16 figures are superseded), but the year-to-year pattern is unchanged.

### Duplicate claims [02 §3]
- **Decision:** Remove duplicate claim records (604 across all lines), keeping one of each pair.
  - **Evidence:** Different `claim_id`s but identical policy, peril, dates, status and amounts; no ambiguous near-duplicates. 600 of 604 have 2022 loss dates, consistent with a one-off duplication. They inflated 2022 cost by about 2% per line. [AI 9]

### Excess on liability perils [02 §5]
- **Decision (Oct 17):** Do not deduct excess from `bodily_injury` and `third_party_prop` (UK practice). [AI 10]
  - **Superseded (Oct 19):** the host confirmed the excess applies to every peril. See "Excess correction" (Oct 19).

### Corrected net cost per exposure [02 §6]
Uncapped, de-duplicated, corrected exposure, no excess on liability (record of that stage):

| Year | Motor | Buildings | Contents |
|---|---|---|---|
| 2021 | 530 | 363 | 89 |
| 2022 | 541 | 382 | 89 |
| 2023 | 554 | 410 | 100 |
| 2024 | 421 | 428 | 100 |

### Large losses [02 §7]
- **Decision:** Cap individual motor claims at 500,000 for modelling; reallocate the excess as a loading.
  - **Evidence:** The 99.9th percentile of BI incurred is about 420,000; 4 claims exceed the cap. One open 2023 BI claim of 11.9m alone is 6% of all BI cost.
  - **Superseded (Oct 19):** loading now from a fitted Pareto tail (2.83 per weight), allocated by risk. See "Motor large-loss loading".

### Development [02 §8]
- **Decision:** Account for reporting delay with completeness factors built from 2021 report lags by peril (count-based).
  - **Evidence:** Non-BI perils are 94–100% complete in 2024, and their 2024 cost is in line with earlier years, so the 2024 motor drop is driven by BI (56% complete). Amount-weighted completeness differs by under 2%, so count-based is kept. [AI 11, 12]
  - **Limitation:** One valuation snapshot only, so case-reserve development on open claims (IBNER) cannot be estimated.

### Bodily injury severity change [02 §9]
- **Finding:** BI frequency is stable (10.5–11.4 per 1,000 exposures), but severity drops about 19% (mean) and 25% (median) from loss year 2023, with a clear step at 2023 Q1. The drop holds for claims reported within 365 days, open and closed claims have similar severity, and no other motor peril shows it. [AI 12, 13]
- **Decision:** Treat 2023 as a change in the BI cost environment (consistent with a small-claims reform). On-level 2021–2022 BI losses by about 0.83 before modelling.
- **Assumption:** Post-reform BI severity trend 0% (one year observed); pre-reform trend of about 5% as sensitivity.
  - **Update (Oct 19):** contradicted by the data; see "Bodily injury trend and reform factor".

### Motor trends [02 §10]
- **Finding:** Gross-of-excess severity trends per year: glass_hail +8%, third_party_prop +8%, own_damage +4%, theft +3%. Net-of-excess medians rise faster (e.g. own_damage 13%) because of the fixed-excess leverage effect. [AI 15]

### Motor frequency [notebook 03]
- **Finding:** own_damage and third_party_prop frequency step down in 2023 (about −7% and −5%) and stay lower in 2024. Portfolio mix changes only gradually (driver_assist, telematics, cover type), and the drop appears within every driver_assist and telematics group, so mix does not explain it. [AI 16]
- **Decision:** Treat 2023 as a level shift, not a trend. On-level 2021–2022 frequency by 0.93 (own_damage) and 0.95 (third_party_prop); no frequency trend for other perils.
  - **Re-checked (Oct 19):** confirmed on all reported claims, completeness-adjusted (see Oct 19).
- **Observation:** Telematics opt-in policies have higher frequency than others, possibly adverse selection.

### Motor modelling target [notebook 03, src/target.py]
- **Decision:** Build the motor target at 2025 level per claim: trend incurred and recoveries by peril severity trend (excess fixed), apply the BI reform factor (0.83) and frequency shift (0.93 / 0.95) to pre-2023 losses, deduct excess, cap at 500,000. Immaturity is handled by weighting exposure with the year's completeness (1.000 / 0.997 / 0.979 / 0.816), not by grossing up individual rows. [AI 17]
  - **Evidence:** Adjusted cost per weighted exposure is consistent across years: 550.8 / 548.4 / 551.0 / 540.0 (2021–2024), compared with 550.7 / 547.0 / 539.2 / 440.6 before the completeness weight.
  - **Limitation:** 2024 is about 2% lower, consistent with case-reserve development on open BI claims and amount-based completeness being about 2% below count-based; not adjusted.

### Automated tests [tests/]
- Hand-checked unit tests for `src/target.py`; each expected value is worked out in a comment next to it. [AI 19, 23]

---

## 2026-10-18 — Modelling plan (set before seeing any model results)

### Evaluation and validation
- **Decision:** Use Tweedie deviance with power 1.5 as the primary metric, reported as D² (1 − model deviance / deviance of a constant-rate model).
  - **Evidence:** This is the competition's scoring metric. The target has many zeros and a long right tail; MSE would be dominated by a few large claims, and Cp/AIC assume a normal-error linear model.
- **Decision (plan):** Out-of-time validation: train on earlier years, evaluate on the next year using completeness-weighted exposure.
  - **As run (Oct 18–19):** two folds — validate 2023 on 2021–22, and 2024 on 2021–23. Grouped cross-validation by `policy_id`, planned as secondary, was not used.
- **Supporting checks:** overall A/E, lift (deciles), lowest / highest decile A/E, segment A/E.
- **Guardrail:** Model choice is based on validation, not the Kaggle leaderboard. Before each submission the expected change is written down; the leaderboard is used to check it.

### Candidate models and rule
- Tweedie GLM (power 1.5, log link), target = adjusted cost per weighted exposure, weight = exposure × completeness; LightGBM with Tweedie objective on the same target and weights; blends or GBM on top of the GLM.
- **Rule:** prefer the simpler, more explainable model unless the more complex one improves validation deviance meaningfully and passes the segment checks (made numeric on Oct 19).

### Prediction
- Row prediction = (predicted cost per exposure + large-loss loading) × test exposure, floored at 0; one CSV for all three lines. (Motor loading allocated by risk from Oct 19.)

### How validation misses are attributed [notebook 06]
- **Decision:** Attribute a validation miss to assumptions (target) or to the model using the model-free checks first (target check by year; frequency/severity check by peril and year), then the train vs validation comparison. The mature-year comparison is used only together with these.
  - **Evidence:** Planted-error test (motor, 7 known errors): model-free checks attributed 6 of 7 correctly each; the mature-year comparison 4 of 7; the AI-proposed "level vs shape" rule 3 of 7. [AI 28, 29, 31]

---

## 2026-10-18 — Buildings and contents adjustments [notebook 04]

### Development
- **Finding:** Only buildings `subsidence` is long-tailed (median report lag 85 days, 90th percentile 254); its 2024 completeness is 0.69. All other home perils are at least 95% complete in 2024.

### Severity trends (gross of excess)
- **Decision:** Buildings: escape_of_water 8%, flood 7%, storm 8%, subsidence 7%, accidental_damage 3%, fire 0% a year. Contents: theft 4%, flood 5%, escape_of_water 3%, accidental_damage 3%. [AI 20, 21]
  - **Evidence:** Quarterly medians rise gradually and the 2023–24 vs 2021–22 change matches a steady trend, so these are treated as inflation, not a step change. Storm severity rises mainly from late 2023 (sensitivity).

### Frequency and weather
- **Finding:** Frequency rises strongly with the matching weather variable: subsidence 3.1× from lowest to highest `dry_summer_index` quintile, flood 2.5× (`rainfall_mm`), storm 1.9× (`wind_exposure_index`), fire 1.8× (`wildfire_index`). The rise in subsidence frequency over 2021–2024 tracks drier summers.
- **Decision:** No frequency trend for weather-driven perils; weather enters the model as features. 2025 weather is available for 100% of test addresses.
  - **Practicality note:** in real pricing, next year's weather is unknown. A sensitivity with each address's average past weather is planned (E4).
- **Open:** buildings fire and contents theft frequency rise steadily (about 8% and 3% a year) without a weather explanation.

### Large losses
- **Decision:** Buildings cap 300,000 (just above the 99.9th percentile, the same rule as motor), large-loss loading 2.3 per exposure; contents no cap (maximum claim 111,300). [AI 22]
  - **Open:** final cap levels to be chosen by validation among none / 99.9th-percentile rule / lower (not yet done).

### Check: 2025-level cost per weighted exposure
| Year | Motor | Buildings | Contents |
|---|---|---|---|
| 2021 | 550.8 | 456.4 | 106.1 |
| 2022 | 548.4 | 452.9 | 101.1 |
| 2023 | 551.0 | 460.6 | 109.0 |
| 2024 | 540.0 | 488.5 | 108.1 |

- Motor is consistent within 2%. Home lines vary by about 8%, expected because weather differs by year. Buildings 2024 is high mainly because of subsidence (+18.6 per exposure), which relies on the 0.69 completeness estimate. Contents 2022 is low because of flood.
- **Limitation:** buildings 2024 subsidence completeness is the main source of uncertainty for buildings.

### Recoveries on open claims
- **Decision:** No adjustment; recorded as a limitation. [AI 24]
  - **Evidence:** Recoveries are recorded only on closed claims (own_damage 23.6% of incurred, theft 4.0%). Applying these rates to open claims would reduce the motor target by 0.34% in total, and by 1.6% for 2024 losses, where open claims concentrate.
  - **Implication:** 2024 actual cost is slightly overstated, which explains up to 1.6 points of the 2024 validation A/E above 1.

---

## 2026-10-19 — Regularisation, excess correction, feature audit, claim history, GBM, loading

### Regularisation [notebook 07]
- **Decision:** Ridge-penalised GLM with every level coded (`drop=None`), so each feature shrinks toward its average level (credibility-style).
  - **Evidence:** In the baseline, the lowest-risk decile was under-predicted in every line and both validation years (A/E about 1.2): relativities too steep. Stronger ridge brings it toward 1; too strong flattens the model and under-predicts the top decile (A/E 1.13–1.19).
- **Decision:** 10 bands for motor, 20 for buildings and contents. Five bands were worse in every line.
- **Finding:** Regularisation removed the buildings 2024 over-prediction (A/E 0.933 → 1.00), consistent with over-steep weather relativities in the driest year. The subsidence split is not pursued.

### Balance correction [notebook 07c]
- **Decision:** After fitting, scale predictions by one factor k so that training predictions sum to training actuals (`balance=True`). k changes the level only, not relativities. [AI 34, 35]
  - **Evidence:** A log-link Tweedie GLM with p = 1.5 does not reproduce the training total, and ridge widens the gap (k up to 1.07 at strong ridge). Without the correction, configurations differed in level as well as shape.
  - **Check:** k is estimated on training years only. Balanced validation A/E for buildings is 0.99–1.02 in both years. A proposed 3% limit on k was dropped for this out-of-sample check. [AI 36]

### Chosen configuration (model v2)
| Line | alpha | Bands | Validation D² (baseline → v2, average of 2023 and 2024) |
|---|---|---|---|
| Motor | 0.5 | 10 | 0.050 → 0.051 |
| Buildings | 0.5 | 20 | 0.055 → 0.065 |
| Contents | 0.3 | 20 | 0.060 → 0.067 |
- Rule fixed before results: highest average balanced D²; within 0.001, prefer larger alpha (flatter), then 10 bands; tails must not be clearly worse than the baseline. [AI 33]
- Buildings: alpha 1.0 had D² 0.0002 higher (noise) but was over-flattened (top decile A/E 1.18–1.19, lowest 0.76 in 2024), so excluded by the tail condition.

### Excess correction [AI 39, 41]
- **Decision:** Deduct the excess on every peril. The host confirmed on the Kaggle forum (Oct 19): "Policy Excess applies to every peril." The public leaderboard had pointed the other way (−0.0008 for the correct definition, within the ±0.001 noise range fixed beforehand); following it would have locked in the wrong target.
- **Changed in code:** `src/target.py` default `excess_on_liability=True` in `match_claims`, `build_target` and `build_model_target` (the earlier reading remains available with `False`). `tests/test_target.py`: five expected values recalculated by hand (BI 1,000 → 700; BI 800,000 → 799,700 before the cap; row sum 1,200 → 900; BI 2022 8,300 → 8,000; BI 2023 10,000 → 9,700).
- **Recomputed automatically:** target, cap and loading, completeness. **Not affected:** severity trends and the BI reform factor (gross amounts); the planted-error test.
- **Re-run:** GLM v2 validation on the corrected target (D² 0.051 / 0.065 / 0.067, unchanged).
- **Re-checked** [notebook 09f]:
  - Motor cost per weight by year: 526.3 / 523.8 / 526.7 / 516.2 (spread 2.0%). Unchanged.
  - 2023 frequency shift, all reported claims, completeness-adjusted, vs the 2021–22 average [AI 42]: own_damage 0.929 / 0.934 → **0.93 confirmed**; third_party_prop 0.957 / 0.932 → **kept at 0.95** (mean 0.945; just outside the rule's ±0.02 tolerance, judged after seeing results); bodily_injury 0.981 / 0.949 → **no adjustment** (2024 only 56% reported).
  - Rule used (fixed before results): both 2023 and 2024 below 2021–22 by a similar amount → level shift; steady change → annual trend; one year only → no adjustment.

### Feature stability and associations [notebook 09]
- **Decision:** Remove features with no stable signal (rank correlation of one-way cost between 2021–22 and 2023–24 below 0.3): previous_insurer (all lines), occupation and region (buildings), occupation (contents); remove duplicate customer_tenure (= renewal_count). GLM D² change: +0.000 / +0.0011 / +0.0015. [AI 40]
- **Findings:** driver_age ≈ years_licensed (Spearman 0.99); region largely determines weather features (η 0.83–0.94); occupation partly proxies age (η 0.62–0.65); channel ≈ discount_applied (0.71).

### Policy limits and cover [notebook 12]
- Motor: no limit field; no pile-up of large claims at one amount (consistent with unlimited bodily injury cover). No action.
- Buildings / contents: sum insured acts as a limit in practice (99.9th percentile of incurred / sum insured 0.998 and 0.974). Claims above sum insured: buildings 7 (fire, up to 1.48×), contents 3 (flood, up to 1.24×), 0.02–0.03% of incurred. Target left as recorded.
- Claims outside the recorded cover: motor 4 (0.00% of net), ignored. Accidental damage claims without the add-on: buildings 502 (0.18% of net), contents 1,087 (0.96%), almost all closed and paid; kept, because they are paid, not declined. [AI 46]

### Claim history [notebooks 10, 11; src/history.py]
- **Decision:** Add claim history: claims on the same policy with loss in the previous 1 and 2 years, reported before 1 January of the policy year (the information a 2025 test row has); levels 0 / 1 / 2+; missing when not observable (window before the data start, or policy new to the data).
  - **Evidence:** Before the feature, rows with a claim in the previous year were under-priced by 22–80% (A/E 1.22–1.81, stable in both validation years). After: motor 1.22 → 1.05 / 0.98. GLM D² +0.0019 / +0.0009 / +0.0008. Test history distribution matches 2024.
  - **Finding:** self-reported prior_claims_5y is almost unrelated to recorded claims (Spearman 0.04).
- **Not adopted:** history by peril group (D² change 0.0000 in all lines) [AI 48]; past claim amounts (valued at the data end, so they leak development after the cutoff) [AI 47]; claims on the customer's other lines (no signal).

### LightGBM challenger and GBM adoption [notebooks 09, 11c, 11d, 11k; AI 44, 45, 51]
- **Rule (fixed before GBM results):** a GBM or blend replaces the GLM only if average validation D² over 2023 and 2024 is at least **0.003** higher, and in each year the lowest and highest decile A/E are no more than **0.1** further from 1 than the GLM's. GBM settings and blend weights are chosen on the held-out last training year only.
- **Motor:** GLM. No variant reached +0.003 (best: blend +0.0016–0.0020).
- **Buildings:** GLM. GBM variants gain +0.0065 to +0.0090 but over-price the lowest decile (A/E 0.56–0.74) in every setting, including stronger regularisation and calibration; structural rather than tuning. The calibrated blend failed the tail condition by 0.002 in 2023 (0.870 vs limit 0.872). **Team decision (Thursday):** the 0.1 tolerance was set without evidence; adopting would add about +0.002 on the leaderboard at the cost of pricing the safest 10% about 15–30% too high.
- **Contents:** LightGBM alone (num_leaves 7, min_data_in_leaf 5000, lambda_l2 50; GLM weight 0 chosen on the last training year), 3-seed average: **+0.0106 D²**, tails within limits (v7). It replaces the v5 blend, which had been preferred after seeing results; the weight is now chosen by the pre-set procedure. Seed spread 5.8% per row, reduced by averaging.
- **Not adopted:** GBM on top of the GLM (method B; keeps tails but gains only +0.002 / +0.004); monotone calibration on the last training year (lowers D² by about 0.001, does not fix the buildings tail).

### Motor large-loss loading [notebooks 11g, 11h, 11j; AI 49]
- **Finding:** one open 2023 bodily injury claim (incurred 11.9m) made up 96% of the observed loading (16.00 per weight; 0.71 without it). Under the fitted tail it is roughly a once-in-several-centuries event for this portfolio; as an open claim its amount is a case reserve.
- **Decision:** loading from a Pareto tail fitted to claims above 100k (alpha 2.05, 119 claims): **2.83 per weight**. Rule fixed before results: estimates for thresholds 100k, 150k, 200k within ±30% and alpha > 1.2 (range 2.83–3.47; passed).
- **Allocation:** in proportion to predicted rate (×1.0054 on the motor rate) instead of a flat amount. Validation on uncapped cost: D² 0.0512 / 0.0546 vs 0.0512 / 0.0542 for flat; 2024 tails closer to 1 (0.94 / 1.01 vs 0.89 / 1.03). The 2023 difference is negligible, so the gain rests on 2024.
- **Sensitivity:** without the 11.9m claim the tail gives alpha 2.21–2.59 and loading 1.18–1.86. Uncertainty range: about 1.2 to 3.8 per weight (0.2–0.7% of the motor rate). Kept at 2.83 because the claim is real and excluding it would understate large-loss risk.

### Feature clean-up [notebook 11g]
- Motor: nine home-type address features removed (soil_type, roof_type, energy_rating, building_age, property_type, bedrooms, flood_zone, elevation_m, distance_to_river_km): D² +0.0004.
- discount_applied removed in all lines: D² change 0.0000; it reflects pricing policy, not risk.
- age_at_licence in place of years_licensed: D² −0.0004, not adopted.

### Tweedie power for fitting [notebook 11m; AI 52]
- No change (p = 1.5). Motor p = 1.4: D² +0.0004 (0.0001 below the threshold) but tails near 1 (0.99–1.01) and k 1.01 instead of 1.02, consistent with the balance property improving as p approaches 1. **Team decision (Thursday).** Contents GLM p = 1.4 passed (+0.0006) but contents uses LightGBM.

### Bodily injury trend and reform factor [notebook 11n; AI 53]
- **Finding:** equal-maturity comparison (Jan–Jun losses reported within 180 days, gross, capped): BI severity +5.9% 2021→2022 (pre-reform) and +7.7% mean / +9.4% median 2023→2024 (post-reform). The 0% post-reform trend is contradicted.
- **Trend alone not adopted:** at 6%, 2023 A/E 1.030 → 1.001 but 2024 1.003 → 0.973 (rule requires both years toward 1), and yearly levels became 578 / 562 / 550 / 527. The reform factor 0.83 was estimated assuming zero trend, so the two are confounded (with a 6% trend the reform step is about 0.838 / 1.06 = 0.79). To be re-estimated jointly on Oct 20.

### Submissions
| Date | File | Change | Public score |
|---|---|---|---|
| 10/19 | glm_v2.csv | Ridge GLM per line (drop=None), balance correction; no excess on liability | 0.11803 |
| 10/19 | glm_v2_excess_liability.csv | Same, excess deducted on every peril (motor total −4.3%) | 0.11724 |
| 10/19 | glm_v3.csv | v2 config minus unstable features and duplicate customer_tenure; excess on every peril | 0.11798 |
| 10/19 | blend_v1_experiment.csv | EXPERIMENT, not adopted: v3 + LightGBM 50/50 in buildings and contents (fails the tail condition) | 0.12113 |
| 10/19 | glm_v4.csv | v3 + claim history | 0.11907 |
| 10/19 | blend_v2_experiment.csv | EXPERIMENT, not adopted: v4 + LightGBM 50/50 in buildings and contents (fails the tail condition) | 0.12186 |
| 10/19 | v5.csv | v4 + contents GLM/LightGBM 50/50 | 0.11996 |
| 10/19 | v6.csv | Motor without home-type and discount features; Pareto loading 2.83 by risk; discount_applied removed in all lines | 0.11951 |
| 10/19 | v7.csv | v6 + contents LightGBM alone (leaves 7, min_data 5000, lambda_l2 50), 3-seed average | 0.11973 |
| 10/20 | v8.csv | v7 + average weather in all lines; contents relative premium | 0.12267 |
| 10/20 | v8a_experiment.csv | EXPERIMENT (attribution): v8 without the contents premium | 0.12237 |
| 10/20 | **v9.csv** | v8 without the motor frequency shifts (motor +0.27%) | **0.12274** |

- **Current adopted model: v9.** Motor GLM (10 bands, no frequency shifts) and buildings GLM (20 bands) with history and average weather; motor Pareto loading by risk; contents LightGBM with history, average weather and relative premium.
- **Validation vs leaderboard** (predicted before submitting vs observed): v3 +0.0005 vs +0.0007; blend v1 +0.002–0.003 vs +0.0032; v4 +0.001 vs +0.0011; blend v2 about 0.122 vs 0.12186; v5 +0.0005–0.001 vs +0.0009; v6 +0.0005–0.0015 vs −0.00045 (miss); v7 +0.0002–0.0005 vs +0.00022; v8 −0.0003 to +0.0005 vs +0.0029 (miss, upward; attributed with v8a); v8a 0.1222–0.1227 if weather vs 0.12237; v9 −0.0002 to +0.0005 vs +0.00007. 8 of 10 consistent. [AI 43, 50]
- **v6 miss:** both submissions that lowered the motor level lost score in proportion (excess −4.3% → −0.0008; v6 −2.7% → −0.00045), pointing to the motor level being low on the public test. v6 kept: the loading rests on the fitted tail and the difference is within noise. Motor level is the first open issue.
- **Experiments** are not candidates for the final selection; final entries are chosen by validation, not by public score.
- **Context:** top 10 on the public leaderboard were 0.125–0.130 on Oct 19.

### Schedule
- Part 1 closes Oct 23 (check the exact time on the Overview tab; the Rules tab shows placeholders). Final model fixed on Oct 22; Oct 23 for submission and checks only.
- **One final submission only** (Rules 2.2.b), and it counts towards the overall result. It is **selected by hand** on Oct 23; otherwise Kaggle picks the best public score, which could be an experiment.
- Pricing (40%) combines Part 1 and Part 2 private scores with the panel's view of modelling choices, adaptation, data quality and uncertainty (Rules 2.4.c). Final deliverables (report, video, repo) are due at the end of Part 2 and cover both parts. Winners must provide code that reproduces the submission (Rules 2.9).

## 2026-10-20 — Candidate features, weather, independent review, BI and completeness

### Candidate features E1–E3 [notebooks 12, 13]
- **customer_service_contacts: excluded as leakage** (all lines). Alone it lifts validation D² from 0.05 to 0.55; its correlation with same-year claims is 12–72× that with next-year claims; the lowest decile A/E is 0.00–0.07. In test its mean is 0.40 against 0.67–0.75 in train, consistent with contacts generated by claims during the period.
- **written_premium: adopted in contents only, as a relative premium** (premium per year ÷ that year's average). Average premium rises every year (motor 618 → 766 from 2021 to 2025), so the raw value would shift 2025 rows into higher bands. Contents LightGBM: +0.0010 D², tails within limits. Motor and buildings GLM: no gain. **Limitation:** circular, as the model inherits the insurer's own relativities; presented separately in the report.
- **make_model: not adopted.** +0.0001 D²; rank correlation of cost between periods 0.15 (unstable).

### Weather for 2025 (E4) [notebooks 12, 13]
- **Decision:** use each address's average 2021–24 weather in training and prediction, in all lines (the same definition everywhere). Rule fixed before results: adopt if it loses less than 0.001 D² against actual weather, with the tail condition.
  - **Evidence:** validation change vs actual weather: motor −0.0005, buildings +0.0002, contents GBM +0.0006. For buildings, "train actual, predict average" had a higher D² (+0.0008) but failed the tail condition (lowest decile 1.22 in 2023); the single definition was chosen after seeing this.
  - **Why:** a price is set before the year, so next year's weather is not known. 2025 weather is not extreme (0.3–3.7% of values outside the 2021–24 1–99% range).
  - **Leaderboard:** +0.0026 from weather alone (v8a), against an expected change near 0. Motor prediction +2.6%. *Hypothesis:* with four years, the yearly part of weather acts as a year effect and carries year-level target differences into 2025 (to be tested with a year factor).

### Reproducibility
- v7 rebuilt from code: total −0.002%, correlation 0.99996 with the submitted file.

### Independent review of assumptions [AI 55]
- A second model (Claude Fable 5.1, new chat, given the code and this log, asked to find errors) reviewed the target assumptions. Each finding was checked against the code and data: accepted, tested, or rebutted with evidence. The reviewer did not design the fixes, so the review stays independent.

### Completeness and BI (E5) [notebook 15; rules R1–R4 fixed before results]
- **R1 adopted: report-lag pattern from all 2021–24 losses (Lynden-Bell estimator for right truncation).** Completeness changes by at most 0.3 points (BI 2024 0.560 → 0.562); motor 2025 prediction −0.09%. The reviewer's concern that truncation materially overstates completeness is not supported. BI reporting speed is unchanged (within 90 days: 44.3% / 44.9% / 46.6% for 2021 / 22 / 23). To be moved into `src/target.py` with the pipeline.
- **R2 not adopted: joint BI trend and reform.** Gamma GLM on equal-maturity claims:

| Cohort | Pre-reform trend | Step | Post-reform trend |
|---|---|---|---|
| Reported within 180 days | 2.8% | 0.796 | 8.6% |
| Within 365 days | 5.5% | 0.792 | — |
| Within 730 days | 7.2% | — | — |
| Within 180 days, closed only | 4.3% | 0.784 | 1.2% |

  - The pre-reform trend is not stable across cohorts (rule a fails). The post-reform rise is 8.6% on all claims but 1.2% on closed claims: it comes from open-claim reserves on recent losses, not from settled costs.
  - With the joint estimate, yearly levels spread 7.8% (vs 2.0%) and 2024 A/E falls from 1.007 to 0.970 (rule c fails).
  - **Robust finding:** the reform step is 0.78–0.80 in every cohort and appears by loss quarter in closed claims (2022 Q4 21.6k → 2023 Q1 16.6k), so it is a change in claim cost, not in reserving.
  - **Kept:** 0% trend, factor 0.83. Sensitivity: motor 2025 prediction +5.1% under the joint estimate. Main open assumption.
- **R3: flat reform factor acceptable.** 2023/2022 ratio net of trend 0.70–0.74 from the 25th to the 90th percentile (difference from the median 0.001). The 99th percentile ratio is 1.01: the largest claims are not affected by the reform, which matters for the large-loss tail.
- **R4 not adopted: peril-level grossing** (−0.0001 D² on the same validation actuals).
- **Reviewer findings rebutted with data:** BI understated by 10–12% (post-reform trend on closed claims is 1.2%); reform step about 0.71 (0.78–0.80 in every fit); frequency shifts as a completeness artefact (already completeness-adjusted on Oct 19).

### Step-change scan [notebooks 16, 16b; rules S0–S2 fixed before results]
- **Purpose:** find sudden level changes (law, claims handling, product) in every line × peril, on three date bases (loss date → law or environment; report date → handling or reserving; policy start → product or underwriting). Reusable on Part 2 data.
- **S0 failed on monthly series:** the known BI step was found at the right date and size (2023-01, ×0.81) but below the threshold (dBIC 4.8); third-party property not found. The tool was changed to quarterly series and re-run (recorded as a fix after a failed control, not a change of threshold).
- **Quarterly:** own damage frequency 2023 Q1 ×0.92 (dBIC 20.7); BI closed-claim severity 2023 Q1 ×0.78 (16.3; all claims 7.0 because open reserves add noise, consistent with E5). **No other step in any line or peril** above the threshold.
- **Third-party property frequency:** best fit is a declining trend (−4.4% a year from 2022 Q1), not a 2023 step. Consistent with Oct 19 (2023 0.957, 2024 0.932: 2024 further down). If it is a trend, 2025 TPP frequency is about 4–6% below the 2023–24 level now assumed. **Open.**
- **Policy side:** apparent February 2024 drops in motor vehicle_age and ncb_years are an artefact: January starts are a distinct cohort every year (renewals of long-standing policies: new business 1%, renewal count 7, vehicle age 9) and the same pattern repeats in January 2025. The policy scan now includes month-of-year effects. Vehicle age rises gradually over time (portfolio ageing); 2025 is close to 2024.
- **Retention:** the share of renewed policies fell by about 19% from 2022, when average premium rose 13% (context only; renewal_decision is not a feature).
- **Effect on the target:** none adopted (S2).

### Year effects after rating factors; renewal checks [notebook 17; rules RA–RD fixed before results]
- **RA — frequency by peril with a year factor plus all rating features.** After the features, frequency per risk rises about 1–2.5% a year in almost every peril, even where raw frequency is flat or falling (motor own damage raw 2024 0.939 → adjusted 1.069; TPP 0.938 → 1.031).
  - **TPP: "mix".** Its raw decline is explained by the rating features, so the 0.95 shift on 2021–22 may count the same change twice. **Own damage:** the 2023 drop also largely disappears after the features (adjusted 1.072 / 1.052 / 1.069 for 2022–24). The Oct 17 mix check used two features only (driver_assist, telematics). Both shifts: **open** (see E6).
  - **Buildings fire:** raw +25.5% by 2024, adjusted +6.1%: mostly mix (reviewer finding B4 largely resolved for fire).
  - **Contents theft:** adjusted +7.3% (step); **glass:** +6% in 2023 (step). Both rise per risk; neither is adjusted in the target. **Open.**
- **RB — validation A/E by new business, renewal count and past claims.** New business and renewal bands: no consistent bias (directions differ between years). **Policies with several past claims are under-priced:** hist_1y = 2+ A/E 1.25–3.26 in all lines; contents hist_1y = 1 A/E 1.21–1.71. Cause: ridge shrinks thinly populated levels hard. Weight 0.1–3%, so small for D², but customers with more claims pay too little. Contents uses LightGBM; to be checked there. **Open.**
- **RC — renewals under a new policy_id:** none in any line (0 of 124–166k first periods). History linkage by policy_id is complete.
- **RD — does yearly weather act as a year effect?** No: motor weather relativities are unchanged when a year factor is added (average change 0%). The v8 gain is not explained this way.

### Time effect in the GLM (E6) [notebook 18; rules T1–T2 fixed before results]
- **Mix decomposition (motor):** rating features alone imply the portfolio became 4.2% safer from 2021 to 2024 (predicted 0.958), while the on-levelled actual fell 1.9% (0.981). Drivers: ncb_years −4.0%, vehicle_age −2.7%, years_licensed −1.7% (features that change by themselves with time), and the history features (hist_1y −2.4%, hist_2y +3.5%), because history is unknown for every 2021 row (data start), so history levels partly carry the 2021 year effect.
- **Variants (out-of-time):** year factor with prediction at the last training year's level (b1), the same with a log-linear trend extrapolated (b2), and both with the own damage / TPP shifts removed from the target (c1, c2).

| Motor | D² change | A/E 2023 / 2024 | 2025 total |
|---|---|---|---|
| a current | — | 1.031 / 1.007 | — |
| b1 latest level | +0.0000 | 1.023 / 0.997 | +0.43% (at 2023 level +0.73%) |
| c1 latest level, no shifts | +0.0002 | 0.993 / 0.996 | +0.55% (+0.82%) |
| b2 / c2 trend extrapolated | −0.0003 to −0.0015 | 0.91–0.94 | +3.3 to +4.0% |

- **Not adopted (T1):** no variant reaches +0.0005 D². c1 has A/E closest to 1 in both years, but the rule fixed for this test was the D² threshold, and it is not changed after the result. Extrapolated trends over-predict in both years (year effects are not linear: 1.059 / 1.109 / 1.106).
- **Buildings:** all variants fail; the 2025 total is +2.5% at the 2024 level but −2.3% at the 2023 level, so the latest year (dry, subsidence 69% complete) is not a reliable level. This was flagged as a caveat before the run.
- **Conclusion:** the drift is real, but controlling for time changes the 2025 motor prediction by under 1%. The hypothesis that it explains the leaderboard's preference for a higher motor level is **not supported**. Kept as a documented check.

### Reform boundary
- Steps are applied by loss year (before / after 1 January 2023). The scan places the BI and own damage breaks at 2023-01 (monthly) and 2023 Q1 (quarterly), so the calendar split is correct here. For Part 2, `adjust_claims` will take a break date found by the scan instead of a year (see docs/PART2_PLAYBOOK.md).

### Level reconciliation and frequency shifts [notebook 19; rules L1, F1 fixed before results]
- **L1 — level reconciliation** (2025 total vs the latest mature year's actual level, split into mix and level):

| Line | Model vs 2023 actual level | Mix part (what the features say) | Level part |
|---|---|---|---|
| Motor | −4.0% | −3.25% | −0.8% |
| Buildings | +5.0% | +2.35% | +2.6% |
| Contents | +0.8% | +2.1% | −1.2% |

  - **Motor:** the model believes 2025 risks are 3.25% safer than 2023 because of features that drift with time; E6 found those features overstate the improvement (4.2% vs 1.9% over three years), so part of the mix effect, perhaps about 1.5%, may be spurious. Consistent in direction with the leaderboard's preference for a higher motor level; size uncertain (the year term moved it by under 1%). **Check only; no change.**
  - **Buildings:** above the 2023 level, partly because the dry 2024 (subsidence 69% complete) raises the training level. Recorded as a risk of over-prediction.
- **F1 adopted — motor frequency shifts removed** (0.93 own damage, 0.95 TPP on 2021–22). The rule treats removal as a simplification: no worse than 0.0005 D², tails within 0.1, A/E no more than 0.01 further from 1.

| Variant | D² change | A/E 2023 / 2024 | 2025 motor |
|---|---|---|---|
| Current (0.93 / 0.95) | — | 1.031 / 1.007 | — |
| No TPP shift | +0.0001 | 1.014 / 1.005 | +0.17% |
| No own damage shift | +0.0002 | 1.017 / 1.005 | +0.11% |
| **No shifts (adopted)** | **+0.0002** | **1.000 / 1.003** | **+0.28%** |

  - All three passed; the rule adopts the one removing most assumptions. The 2023 drops were mix: the Oct 17 check used two features only; with all rating features the conclusion reverses.
  - **Changed in code:** `src/target.py` motor `freq_shift` = {} (mechanism kept for other markets); `tests/test_target.py`: the default test now expects no shift (1,124.864) and a separate test keeps the mechanism (1,046.12352).
  - Yearly levels become 542 / 540 / 527 / 516 per weight (less even, because the mix is no longer hidden).

---

## Open questions
- **Resolved:** evaluation metric (Tweedie D², p = 1.5); excess on liability (host: every peril); 2025 weather available for all test addresses; prior_claims_5y almost unrelated to recorded claims, so history is built from the claims table.
- **Motor level:** the leaderboard has favoured a higher motor level (excess, v6, v8; v9 +0.27% motor, +0.00007). The reconciliation (L1) points to the mix effect: features say 2025 is 3.25% safer than 2023, part of which may be spurious drift. Not explained by the BI joint estimate, by weather as a year effect, or fixed by a year term (under 1%). Recorded with its range; the leaderboard is not used to decide the level.
- All other open items are tracked in the Assumptions register below.

---

## Assumptions register (status as of Oct 20, after E1–E6 and notebook 19)

Status: **verified** (tested on data) · **judgement** (reasoned, not fully testable) · **open** (not yet checked) · **team decision** (to be decided by the team)

### Target
| Assumption | Current value | Status | Evidence / next step |
|---|---|---|---|
| Unit and claim linkage | row_id; both period ends inclusive | verified | Consecutive periods exactly 1 day apart; 99.7% of claims match one period |
| Declined claims | excluded | verified | All repudiated amounts are zero; matches the competition definition |
| Excess | voluntary + compulsory, on every peril | verified | Host answer on the Kaggle forum (Oct 19) |
| Net cost | max(max(incurred − excess, 0) − recoveries, 0) | verified | Both deduction orders give the same total |
| Exposure errors | recomputed from dates where inconsistent | verified | Total exposure changed by 25–28% |
| Duplicate claims | 604 removed | verified | Concentrated in 2022 |
| Completeness (IBNR) | report-lag pattern from all 2021–24 losses (Lynden-Bell), count-based | verified | Changes ≤ 0.3 points vs the 2021 pattern; reporting speed unchanged; amount-weighted differs by < 2% |
| Motor severity trends (gross of excess) | glass 8%, own damage 4%, theft 3%, third-party property 8%, BI 0% | **open** (BI) | Joint estimate unstable: pre-reform 2.8–7.2% by cohort; post-reform 8.6% all claims vs 1.2% closed (reserves). Sensitivity +5.1% on motor |
| Home severity trends | buildings: AD 3, EoW 8, fire 0, flood 7, storm 8, subsidence 7; contents: AD 3, EoW 3, flood 5, theft 4 (%) | judgement | Quarterly medians (Oct 18) |
| BI reform factor | 0.83 on 2021–22, all claim sizes | judgement | Step 0.78–0.80 in every joint fit; by loss date and in closed claims (a cost change). Flat up to the 90th percentile; the 99th percentile unaffected |
| Frequency level shift | none (removed Oct 20; was own damage 0.93, TPP 0.95) | verified | The 2023 drops are mix: after all rating features they vanish. Removal passed the simplification rule: D² +0.0002, A/E 1.000 / 1.003 |
| Glass frequency | no adjustment | **open** | Adjusted for features: +6% step in 2023; small share of cost |
| Recoveries on open claims | not adjusted | judgement | Closed-claim recovery rates applied to open claims would lower the motor target by 0.34% (2024: 1.6%); recorded as a limitation |
| Development of open claims (IBNER) | not modelled | judgement | One valuation snapshot; recorded as a limitation |
| Motor theft severity | 3% a year | **open** | May be a 2023 step rather than a trend [AI 25] |
| Buildings fire / contents theft frequency | no frequency trend | fire: verified (mix); theft: **open** | Fire +25.5% raw → +6.1% after features. Contents theft +7.3% after features (step) |
| Contents 2023 | no adjustment | **open** | Validation A/E 1.07 in 2023 |
| Cap levels | motor 500k, buildings 300k, contents none | **open** | Plan: choose among none / 99.9th-percentile rule / lower by validation; not yet done |
| Large losses, motor | Pareto loading 2.83 per weight, allocated by risk | verified | Range 1.2–3.8; GPD check optional |
| Large losses, buildings | observed loading 2.33, flat | **open** | Align with the motor method (small effect) |
| Limits and cover | no adjustment | verified | Claims above sum insured 0.02–0.03%; AD claims without the add-on are paid claims |

### Model and features
| Assumption | Current | Status | Evidence / next step |
|---|---|---|---|
| Validation design | two out-of-time folds (2023 on 2021–22; 2024 on 2021–23) | verified | Predicted the leaderboard change 6 of 7 times |
| Tweedie power for fitting | 1.5 | team decision | Motor p = 1.4: +0.0004 D² (below threshold) with better tails and balance |
| Ridge strength and bands | motor α 0.5 / 10, buildings α 0.5 / 20, contents α 0.3 / 20 | verified | Grid on two validation years |
| Balance factor k | from training years | verified | Level holds in validation years |
| Claim history | same policy, 1 and 2 years, known by 1 Jan; unknown = missing | verified; **open** (2+ levels) | v4 +0.0011. No renewals under a new policy_id. 2+ past claims under-priced (A/E 1.25–3.26; ridge shrinkage). Unknown level partly carries the 2021 year effect |
| Weather for 2025 | average 2021–24 weather per address | verified | Validation within 0.001 of actual weather; leaderboard +0.0026 |
| written_premium | contents only, relative to the year's average | judgement | +0.0010 D² in contents; circular (inherits the insurer's relativities) |
| customer_service_contacts | excluded | verified | Leakage: same-year correlation 12–72× next-year; test mean 0.40 vs train 0.67–0.75 |
| make_model | excluded | verified | +0.0001 D²; unstable between periods (0.15) |
| Marketing and branch fields | excluded | open | Expected small |
| Removed features | previous_insurer; occupation, region (home); discount_applied; home-type features in motor; duplicate tenure | verified | Stability checks and add/drop tests |
| GBM by line | contents only (3 seeds) | team decision | Buildings +0.009 D² but over-prices the safest decile |

### Decision rules (fixed before results)
| For | Rule |
|---|---|
| GBM or blend | +0.003 average validation D² over the GLM; lowest and highest decile A/E no more than 0.1 further from 1 than the GLM's in each year |
| Adding a feature / changing a GLM setting | +0.0005 D² and the tail condition |
| Removing a feature | removed unless D² falls by more than 0.0005 |
| Target assumptions (trends, factors) | model-free evidence, A/E toward 1 in both validation years, yearly levels more even |
| Leakage | information not known when pricing is excluded whatever its score |
| Choosing settings | on the held-out last training year only; validation years used once |
| Leaderboard | not used for decisions; expected change written before each submission; ±0.001 treated as noise |
