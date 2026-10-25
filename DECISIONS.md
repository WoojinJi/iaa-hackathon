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
| 10/20 | v9.csv | v8 without the motor frequency shifts (motor +0.27%) | 0.12274 |
| 10/21 | v10.csv | v9 + Lynden-Bell completeness + relative premium by start month; built by `src/pipeline.py` | 0.12265 |
| 10/21 | v11.csv | v10 + five flood-geography interactions in the buildings GLM | 0.12307 |
| 10/22 | blackbox_experiment.csv | EXPERIMENT E9: LightGBM in every line, high capacity, all non-leaking features | 0.11602 |
| 10/22 | stack_experiment.csv | EXPERIMENT E10: LightGBM + CatBoost + XGBoost + neural network stack | 0.12296 |
| 10/22 | **v12_freqsev.csv** | v11 with motor frequency x severity GLMs (E11, rule passed) | **0.12336** |

- **Current adopted model: v12** (final Part 1 submission, selected by hand; `python tools/exp_freqsev.py --out ...`). Motor: frequency (Poisson) x severity (Gamma) GLMs, ridge strength chosen per part on the last training year (E11, Oct 22). Previously v11 (`python -m src.pipeline`): motor GLM (10 bands, no frequency shifts) and buildings GLM (20 bands, five flood-geography interactions) with history and average weather; Lynden-Bell completeness; motor Pareto loading by risk; contents LightGBM with history, average weather and relative premium by start month.
- **Validation vs leaderboard** (predicted before submitting vs observed): v3 +0.0005 vs +0.0007; blend v1 +0.002–0.003 vs +0.0032; v4 +0.001 vs +0.0011; blend v2 about 0.122 vs 0.12186; v5 +0.0005–0.001 vs +0.0009; v6 +0.0005–0.0015 vs −0.00045 (miss); v7 +0.0002–0.0005 vs +0.00022; v8 −0.0003 to +0.0005 vs +0.0029 (miss, upward; attributed with v8a); v8a 0.1222–0.1227 if weather vs 0.12237; v9 −0.0002 to +0.0005 vs +0.00007; v10 −0.0002 to +0.0003 vs −0.00009; v11 +0.0005 to +0.0012 vs +0.00042 (just below); E9 −0.002 to +0.004 vs −0.0071 (miss); E10 −0.003 to +0.001 vs −0.00011; v12 +0.0005 to +0.002 vs +0.00029 (just below). Of 15: 6 inside the written range, 6 within 0.00025 of it (point estimates cannot be hit exactly), 3 outside (v6, v8, E9); figure 2 (`tools/figures.py`). [AI 43, 50]
- **v6 miss:** both submissions that lowered the motor level lost score in proportion (excess −4.3% → −0.0008; v6 −2.7% → −0.00045), pointing to the motor level being low on the public test. v6 kept: the loading rests on the fitted tail and the difference is within noise. Motor level is the first open issue.
- **Experiments** are not candidates for the final selection; final entries are chosen by validation, not by public score.
- **Context:** top 10 on the public leaderboard were 0.125–0.130 on Oct 19.

### Schedule
- Part 1 closes Oct 23. The organisers announced that Week 2 opens on 23 October at 12:00 PM EDT on a new competition page; Rule 2.4.a says Part 2 opens when Part 1 closes, so Part 1 is taken to close at noon EDT. Final model fixed on Oct 22 (v12); Oct 23 for checks only.
- **One final submission only** (Rules 2.2.b), and it counts towards the overall result. It is **selected by hand** (v12, selected Oct 22); otherwise Kaggle picks the best public score, which could be an experiment.
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

## 2026-10-21 — Pipeline, checks, v10

### Reproducible pipeline [src/pipeline.py, src/config.py, src/loading.py]
- **Decision:** the submission is built by one command (`python -m src.pipeline --out ...`) from a market configuration (`src/config.py`), instead of notebook cells. Pareto loading moved to `src/loading.py`; `src/target.py` gained a break date for steps (`adj["reform_date"]`, default 1 January 2023, identical to the previous rule), a Lynden-Bell completeness option, and valuation date / years as parameters (for Part 2).
  - **Evidence:** v9 rebuilt from code: totals +0.000%, correlation 1.000000, no row differing by more than 1%. The Pareto refit gives alpha 2.05, 119 claims above 100k, loading 2.83, as on Oct 19.
  - Tests: 44 (11 new: break date, Lynden-Bell on simulated lags, Pareto formula and fit, relative premium, step test, schema diff). CI runs them on every push. Exact package versions: `requirements-lock.txt`.

### Day 1 checks as a tool [src/checks.py; report: docs/checks_part1_report.md]
- One command produces the Day 1 report for any market: schema, data quality, completeness (both methods), reporting speed, quarterly step scan, policy scan with month-of-year effects, leakage suspects.
- **Controls on Part 1 data:** the step scan reproduces notebook 16b (own damage frequency 2023 Q1, BI closed severity 2023 Q1, TPP decline); the leakage test flags customer_service_contacts in all three lines.
- **New finding (policy scan):** average premium per year steps up by about 50–60% in May–June 2021 in all lines; the share of renewed policies falls at the same time (×0.90); from 2022 the share of new business rises (×1.12) and renewal counts fall (×0.82–0.86). Read together: a large rate increase in mid-2021, followed by more lapses and more new business. *Hypothesis:* lower-risk customers left after the increase (adverse selection), consistent with the feature-adjusted risk being lowest in 2021 and 5–10% higher afterwards (notebook 17). Not adjusted.

### Relative premium by start month [rule fixed before results]
- **Problem found by the checks:** the contents relative premium divided premium by the policy year's average, so within 2021 a policy starting before the mid-2021 rate step looked cheap and one after it looked dear, a price change read as risk.
- **Decision:** divide by the average of the policy-start month. Rule: a correction of how a feature is built, adopted if average D² does not fall by more than 0.0005 and tails stay within 0.1.
  - **Evidence (contents LightGBM, out of time):** D² 0.0847 / 0.0755 → 0.0843 / 0.0765 (average +0.0003); lowest decile A/E 0.988 / 0.983 → 0.999 / 0.958; highest 1.235 / 0.994 → 1.230 / 0.980. Adopted.

### v10
- v10 = v9 + Lynden-Bell completeness (rule R1, Oct 20) + relative premium by start month. Motor −0.09%, buildings +0.39% (subsidence 2024 completeness 0.919 → 0.913), contents −0.78%; total +0.033%; correlation 0.99988 with v9.
- Expected leaderboard change written before submitting: −0.0002 to +0.0003. Observed: −0.00009 (0.12265). Kept: both changes were adopted by rules before the result, and the difference is a tenth of the noise range.
- Config defaults now give v10 (`python -m src.pipeline` with no options).

### Interactions in the buildings GLM (E7) [tools/exp_interactions.py, src/interactions.py; rule fixed before results]
- **Purpose:** recover part of the GBM's buildings gain (about +0.009 D²) while keeping rating tables and avoiding the GBM's over-pricing of the safest decile.
- **Procedure (per fold, never seeing the validation year):** rank feature pairs by a depth-2 GBM (split gain of parent–child pairs) on the training years before the last; add each of the top 6 pairs to the GLM as one coarse cross-classified factor (5 × 5 bands, ridge-shrunk); keep a pair if D² on the last training year rises by ≥ 0.0003. Rule: adopted if the average validation D² rises by ≥ 0.0005 and both tails stay within 0.1.

| Buildings | Main effects | + interactions |
|---|---|---|
| D² 2023 / 2024 | 0.0630 / 0.0663 | 0.0647 / 0.0696 |
| D² average | 0.0647 | **0.0672 (+0.0025)** |
| Lowest decile A/E | 1.219 / 0.946 | 1.198 / 0.941 |
| Highest decile A/E | 1.032 / 1.087 | 1.025 / 1.078 |

- **Adopted.** 28% of the GBM's gain, with the tails slightly closer to 1 (the GBM over-priced the safest decile by 15–30%).
- **Final list** (same procedure on all years: ranked on 2021–23, kept on 2024): flood_zone × sum_insured, elevation × flood_zone, elevation × sum_insured, building_age × flood_zone, distance_to_river × flood_zone. All describe flood geography: flood risk is not additive (within a flood zone, height and distance from the river change the risk a lot), and larger sums insured lose more in a flood. Folds kept 3 pairs each; validation measures the procedure, not one fixed list.

- **Motor (same procedure, same rule): not adopted.** D² +0.0001 (0.0531 → 0.0532); the final selection keeps no pair. Candidates were driver-experience pairs (NCB × years licensed, driver age × NCB, mileage × NCB, voluntary excess × NCB), whose effect on the last training year was small and not stable between folds. The motor GBM's own gain was small (about +0.002), consistent with main effects being enough for motor. (The script's "share of GBM gain recovered" line uses the buildings figure, +0.009; for motor it does not apply.)

### Buildings blend with a regularised GBM (E8) [tools/exp_blend.py; rule of Oct 19, fixed before results]
- **Question:** with the interactions in the GLM, can a blend with a regularised GBM (7 leaves, min 5,000 per leaf, L2 50, 3 seeds) gain further without the tail problem? Blend weight chosen on the last training year (0 / 0.25 / 0.5 / 0.75 / 1).

| Buildings | v11 GLM + interactions | Blend (w = 0.75 in both folds) | GBM alone |
|---|---|---|---|
| D² 2023 / 2024 | 0.0643 / 0.0712 | 0.0723 / 0.0776 | 0.0716 / 0.0776 |
| D² average | 0.0677 | 0.0749 (+0.0072) | 0.0746 (+0.0069) |
| Lowest decile A/E | 1.147 / 0.901 | **0.735 / 0.720** | 0.618 / 0.709 |
| Highest decile A/E | 1.017 / 1.083 | 1.118 / 1.145 | 1.112 / 1.126 |

- **Not adopted:** the tail condition fails in both years (the safest 10% over-priced by about 27–28% with the blend, 10–15% off with the GLM).
- **The trade-off, measured:** about +0.007 validation D² (perhaps +0.002–0.003 on the leaderboard, as with the Oct 19 blends) against charging the safest customers about a quarter too much. D² barely penalises this, because their expected cost is small. Kept for the Thursday team decision, with the numbers above; the default remains the rule.
- The v11 GLM scores 0.0677 here vs 0.0672 in E7: here the final list of five pairs is used in both folds, in E7 each fold selected its own pairs (the procedure's estimate).
- **Process error:** the first run in a notebook used versions of `src/config.py` and `src/pipeline.py` loaded earlier in the same kernel (before the interactions were added), so its "v11" was in fact the main-effects GLM. Detected because its numbers matched E7's main-effects row exactly; re-run in a fresh process. Experiments that import `src` are run from the terminal (or after a kernel restart).

### v11
- v11 = v10 + the five buildings interactions (`src/config.py`). Motor and contents unchanged.
- Expected leaderboard change written before submitting: +0.0005 to +0.0012. Observed: **+0.00042 (0.12307)**, just below the range, in the right direction. Kept on the validation evidence.

## 2026-10-22 — Black-box comparison (E9, E10), frequency x severity (E11), v12

### Team decisions (briefing and meeting)
- **Buildings blend (E8): not adopted.** Over-pricing the safest 10% by about 27% would drive those customers away; the score gain (+0.007 validation, perhaps +0.002–0.003 public) does not justify it.
- **Motor level adjustment (E6 c1) and Tweedie p = 1.4: not adopted.** Both are below the thresholds; the leaderboard's preference for a higher motor level is within noise and a time term moves the motor prediction by under 1%.
- **Prizes and scores (Rules 2.4.c, 2.4.e):** Pricing (40%) combines the Part 1 and Part 2 private scores, equally weighted, with the panel's assessment; Part 1 position alone does not determine prizes. Whether scores enter as raw values or ranks is not stated; we assume raw scores (Kaggle's generic rule 3.7.a speaks of ranking).

### Traceability tiers for a final submission [fixed before the E10 validation result and before the E10 public score]
- (1) a GLM, readable as rating tables; (2) a single regularised tree model whose drivers can be shown with feature importance and partial dependence, if it passes the score and tail rule (contents); (3) a combination of several models including a neural network: a measured benchmark only, whatever its score, because a validation miss cannot be traced to a rating factor or even to one model.

### E9 black box max [tools/exp_blackbox.py]
- LightGBM in every line, high capacity (127 leaves, 200 per leaf, light L2), every non-leaking feature (features removed for instability put back), relative premium in all lines, no hand-built interactions; same target and loading as v11.
- Expected before submitting: −0.002 to +0.004 vs v11. **Observed: 0.11602 (−0.0071), outside the range.** Total −2.1% vs v11, correlation 0.898.
- **Out-of-time validation (run after submitting):** worse than v11 in every line and both years: D² motor −0.0068, buildings −0.0124, contents −0.0261. Tails collapse at both ends: safest 10% over-priced by 35–39% in buildings and contents (A/E 0.61–0.68); riskiest 10% under-priced by up to 79% (contents 2023 A/E 1.79). Seed spread 7.5–10% per row (contents GBM in v11: 3.7–3.9%).
- The validation predicted the leaderboard loss: had it been run first, E9 would not have been submitted. **Lesson: run the validation before any experimental submission.** Over-fitting from capacity on a noisy target is the likely cause.

### E10 stacked black box [tools/exp_stack.py]
- LightGBM + CatBoost + XGBoost + neural network (embeddings, two hidden layers, Tweedie loss); each tuned on the last training year, stack weights chosen there. Weights: CatBoost 0.55–0.70, LightGBM 0.15–0.30, network 0–0.15, XGBoost 0. A reasonably tuned stack (one seed, no hyper-parameter search), not an exhaustive one; early stopping halted every model after few iterations (trees 41–539, network 3 epochs).
- First run hung at the network (PyTorch and LightGBM / XGBoost OpenMP in one process on macOS); fixed by one PyTorch thread and per-epoch logging.
- Holdout 2024 D² (train 2021–23): motor 0.0550, buildings 0.0722 (v11 0.0712), contents 0.0741 (v11 0.0765). Total −1.6% vs v11, correlation 0.950.
- **Expected public change vs v11 (revised before submitting, after seeing the holdout D² and the comparison line): −0.003 to +0.001.** Observed: **0.12296 (−0.00011), inside the range.**
- **Out-of-time validation:** stack minus v11, average D²: motor +0.0016, buildings −0.0005, contents −0.0042. Worst tail distance from 1: motor 0.146 → 0.184, buildings 0.147 → 0.338, contents 0.229 → 0.418. Fails the Oct 19 GBM rule (+0.003, tails within 0.1) in every line, before the traceability tiers are even applied. In motor, v12's frequency x severity GLM (+0.0025 vs v11) beats the stack (+0.0016).

### E11 frequency x severity GLMs [tools/exp_freqsev.py]
- Open since Oct 19 (AI 44): deprioritised by reasoning, never tested. A Tweedie GLM ties frequency and severity to move in the same direction with every feature; this tests whether relaxing that helps. Frequency: claims with net cost > 0 per row (2025 level, capped), Poisson GLM, weight exposure x completeness. Severity: target / claim count, Gamma GLM, weight claim count. Same target, features, bands and loading as v11.
- **First version carried v11's ridge strength (0.5, tuned on the Tweedie cost scale)** into both parts, where the deviance scale is far smaller: both were nearly flat (NCB frequency range 0.98–1.06). Caught by the direction table before any validation result [AI 83]. Fixed: each part's alpha chosen on the last training year from a fixed list (0.5, 0.1, 0.03, 0.01, 0.003, 0.001). Chosen: frequency 0.001 (0.003 once), severity 0.1 in the folds and 0.03 in the final fit. Frequency alpha sits at the lower end of the list: recorded, not changed.
- **Directions (`--directions`):** factors pulling frequency and severity in opposite directions — motor: claim history (frequency up to ×3, severity slightly lower), cover type (third-party-only: fewer, larger claims), voluntary excess (small claims filtered out); buildings: building age, energy rating, voluntary excess. Flood geography and sum insured move both the same way. NCB moves both the same way here (all perils, averages by level, mixed with age and licence years), so the Oct 19 "NCB opposite" observation (own damage only) is not confirmed. Within customers, claim size on rows with 2+ claims vs 1: motor +1.1% (independence holds), buildings +4.3% (685 rows).
- Rule of Oct 19 (+0.0005 D², tails within 0.1). Expected before the result: small gain in motor, about equal in buildings.

| | Motor v11 | Motor freq x sev | Buildings v11 | Buildings freq x sev |
|---|---|---|---|---|
| D² 2023 / 2024 | 0.0527 / 0.0535 | 0.0551 / 0.0561 | 0.0643 / 0.0712 | 0.0673 / 0.0721 |
| D² average | 0.0531 | **0.0556 (+0.0025)** | 0.0677 | 0.0697 (+0.0020) |
| Safest 10% A/E | 0.854 / 0.960 | 0.923 / 1.003 | 1.147 / 0.901 | 0.864 / **0.665** |
| Riskiest 10% A/E | 1.017 / 1.070 | 0.973 / 1.011 | 1.017 / 1.083 | **1.278** / 1.208 |

- **Motor: adopted** (gain in both folds, both tails closer to 1). **Buildings: not adopted** (tails fail).
- **Why motor only:** the rule is applied line by line, as for contents (GBM) on Oct 19. Motor: several core rating factors move frequency and severity in opposite directions, which a Tweedie GLM cannot represent, and claim size does not depend on claim count within customers. Buildings (*hypothesis*): the strongest factors move both the same way, so the Tweedie constraint costs little; splitting adds parameters on far fewer claims (about 23k vs 80k rows with a claim) and the severity model becomes unstable at the extremes.
- **v12** = v11 with motor frequency x severity. Total +0.036% vs v11 (motor about +0.07%), correlation 0.9968; buildings and contents identical to v11. Expected public change: +0.0005 to +0.002. Observed: **0.12336 (+0.00029)**, just below the range, right direction. **Adopted as the final Part 1 submission** on the validation evidence.

### What the comparison shows
| Model | Public | Validation D² vs v11 (motor / buildings / contents) | Worst tail (buildings, contents) |
|---|---|---|---|
| E9 black box max | 0.11602 | −0.0068 / −0.0124 / −0.0261 | 0.64, 0.79 |
| E10 stack | 0.12296 | +0.0016 / −0.0005 / −0.0042 | 0.34, 0.42 |
### E10b: why the stack did not beat v11 [tools/exp_stack.py --why; for understanding only, no selection]
- 2 x 2 on the same folds: features (all non-leaking vs v11's set) x stack weights (chosen on the last training year vs equal). "All / chosen" reproduces the E10 validation exactly.
- **Unstable features hurt (hypothesis 5: supported).** Moving to v11's features improves the stack in every line: D² vs v11, chosen weights: motor +0.0016 → +0.0022, buildings −0.0005 → +0.0054, contents −0.0042 → −0.0027. The Oct 19 stability drops were right for black boxes too.
- **One-year stack weights did not over-fit (hypothesis 6: not supported).** Equal weights were no better than chosen weights in any line (motor v11 features: +0.0023 vs +0.0022).
- With v11's features, the buildings stack gains +0.0054 but over-prices the safest 10% by about 40% (A/E 0.61 / 0.58): the same pattern as the E8 blend and the E11 buildings split. Fails the tails; tier 3. Motor: the improved stack (+0.0022) is still behind v12 (+0.0025). Contents: our single regularised GBM still leads.
| v11 | 0.12307 | — | 0.15, 0.23 |
| **v12** | **0.12336** | +0.0025 / 0 / 0 | 0.15, 0.23 |

- Capacity alone over-fitted (E9); a tuned stack tied v11 but priced the extremes worse (E10); the gain came from actuarial structure (v12). The prediction written before the experiments ("the black box scores higher…") was half right: the black boxes did not score higher here.
- **Checking the validation folds is not free:** E8–E11 used the same two folds on one day. Further Part 1 experiments stopped here; new ideas go to Part 2 (docs/PART2_PLAYBOOK.md, Day 3).

---

## Open questions
- **Resolved:** evaluation metric (Tweedie D², p = 1.5); excess on liability (host: every peril); 2025 weather available for all test addresses; prior_claims_5y almost unrelated to recorded claims, so history is built from the claims table.
- **Motor level:** the leaderboard has favoured a higher motor level (excess, v6, v8; v9 +0.27% motor, +0.00007); E9 and E10, both 1.6–2.1% below v11 in total, lost or tied. The reconciliation (L1) points to the mix effect: features say 2025 is 3.25% safer than 2023, part of which may be spurious drift. Not explained by the BI joint estimate, by weather as a year effect, or fixed by a year term (under 1%). Recorded with its range; the leaderboard is not used to decide the level.
- All other open items are tracked in the Assumptions register below.

---

## 2026-10-23 — Part 2 Day 1: emerging-market data (checks before any model)

Data: `data_part2/emerging` (Kaggle Part 2 page, downloaded file by file; bulk download returns 404).
Tools: `python -m src.checks --out results/checks_part2 --data data_part2/emerging --reference
results/checks_part1/schema.json`; follow-up cells in `notebooks/20_part2_day1.ipynb`. No model fitted.

### What changed from the developed market
- **Two training years (2023, 2024)**, valued at 31 Dec 2024. Train rows: motor 47,283, buildings 27,447,
  contents 34,566; claims 7,183 / 1,059 / 1,016. **Test is about four times the 2024 exposure** (motor
  79,007 vs 20,104): the broker portfolio taken on in 2025.
- **76% of test rows are new business** (train 12–15%); 24% of test policies appear in train, so claim
  history is observable for about a quarter of test rows (Part 1: 85%).
- Columns: age bands instead of ages; no credit_band, annual_mileage, telematics; **gender added** (allowed
  for pricing in this market, Dataset Description); construction_type in local codes (BRK/STN/WOD/MIX);
  regions E01–E06. New tables: expenses, reference_policies.
- Channel, region, payment method and cover type shares are unchanged between train and test.

### Data quality
- **Exposure:** 0.5% of train rows inconsistent with dates (same as Part 1); corrected by `exposure_clean`.
  Test: none.
- **Clean:** no duplicate claims; 0.3–0.5% of claims outside any period (excluded as in Part 1); no negative
  amounts; repudiated 0–1.5% (excluded).
- **Missing values (~12% in motor vehicle_age, engine_size_cc, overnight_parking; buildings
  days_unoccupied, smoke_alarms; contents security_level, high_value_items).**
  - **Finding:** missing completely at random. Missing indicators are uncorrelated across columns (|r| ≤
    0.01); the share does not vary by year, channel or new business; claim frequency is the same with and
    without the value (largest gap buildings days_unoccupied 0.046 vs 0.035 on 100 claims).
  - **Decision:** keep a "missing" level in each banded factor; ridge shrinks it toward the average.
- **sum_insured entry error (×1000).** Buildings 157 rows, contents 192 rows (about 0.2%, train and test).
  - **Rule fixed before looking (the team asked whether these could be real values):** an entry error if
    the same policy's other years differ by about ×1000 and the written premium is normal; a real value if
    the premium is also large or the value is large every year.
  - **Evidence:** policies seen in two or more years: max/min ratio median 1,030 (buildings) and 1,019
    (contents), i.e. ×1000 with 2–3% annual indexation; only one year is affected. Written premium of the
    large rows equals that of normal rows (median 250 vs 250; 124 vs 124). No buildings rows between 5× and
    100× the median. Property type and bedrooms match normal rows.
  - **Decision:** sum_insured above 100× the line's training median is divided by 1000 (train and test;
    `src/clean.py`). Contents rows at 5–10× the median (17) are below the gap and kept as real.
- **renewal_count is consistent, not an error.** Train mean 6.8 in a market written since 2023, but it is 0
  for every new-business row and ≥ 1 for every renewal, rises by exactly 1 for every policy from 2023 to
  2024, and 47% of customers have customer_since_year ≤ 2015 (tenure includes the relationship before the
  insurer entered the market). Kept.
- **written_premium is the annual premium, not the row's premium** (Part 1 as well). Median written premium
  is flat by start month (motor 500–525) while median exposure falls from 1.00 to 0.04.
  - **Decision (Part 2):** relative premium = written_premium ÷ that year's average, not divided by exposure
    (`premium_norm="annual"`; not used in the baseline).
  - **Part 1 consequence (to re-check):** Part 1 divided by exposure, which inflated short rows; the v10 gain
    from normalising by start month (+0.0003) may have offset this artefact, and the mid-2021 "rate step"
    from the policy scan needs re-checking on the corrected definition. The Day 1 policy-scan steps in
    premium per year (motor ×1.9 at 2023-05, contents ×0.45) are this artefact.

### Development
- Completeness patterns match the developed market: bodily_injury 2024 0.55 (Lynden-Bell) / 0.57, subsidence
  2024 0.75, all other perils ≥ 0.94. The first-year method differs for bodily_injury 2023 (0.973 vs 0.945)
  because the reference year itself is immature. **Lynden-Bell kept.**

### Leakage
- customer_service_contacts: same-year correlation 10–82× next-year, test mean 0.40 vs 0.47–0.77 in 2024.
  **Excluded**, as in Part 1. renewal_decision excluded (train only).

### New business (the main Part 2 question)
- **Train: new business has higher claim frequency.** Motor 0.260 / 0.209 vs 0.184 / 0.170 (2023 / 2024);
  contents 0.042 / 0.048 vs 0.034 / 0.033; buildings 0.056 / 0.034 vs 0.045 / 0.045 (37–40 claims, no
  consistent direction). By renewal_count, motor frequency is 0.229 at 0 and 0.17–0.185 from 1 onward: a
  first-year effect, flat after.
- **Age-standardised** (new business is younger: 17–34 is 55% vs 37%): motor 1.17, contents 1.26,
  buildings 0.97.
- **Developed market, 2021–2024 (not age-standardised):** motor 1.36–1.43, buildings 1.05–1.15, contents
  1.11–1.21, stable every year.
- **Are the 2025 new customers like the train new customers?** On every observed variable, yes: age band,
  marketing segment, ncb_years, years_licensed, years_at_address, prior_claims_5y, licence_points, campaign
  code, previous insurer, cover type, channel. The only difference is timing: test new business starts in
  January (88–91%; the transfer date), train new business starts across the year (7–8% in January;
  exposure 0.47 vs 0.88).
- **Why it matters:** with 76% of test rows new business, a new-business relativity of 1.17 vs 1.00 moves
  the test level by about 13%.

### Other decisions
- **gender:** allowed for pricing in this market (Dataset Description) and in every feature list, but effective in buildings only (F/M 0.974; emerging-only training). Motor (developed relativities) and contents (combined) drop it because the developed table has no gender column (F/M 1.000, checked Oct 24 notebook 26); motor region levels E01-E06 are likewise not learned. Restoring them was tested as E21 (+0.0002 / +0.0004).
- **BI reform factor 0.83:** not applied. It is a developed-market legal change; the emerging data start in
  2023 and show no step to test.
- **Weather:** address average of 2023–24 (Part 1 E4 method). `weather.parquet` includes 2025 (the Dataset
  Description lists 2023–24 only); the average is kept for the Part 1 reason: next year's weather is unknown
  when pricing.

### Rules agreed before any model result (team, Oct 23)
1. **New business:** a GLM factor estimated on emerging data. If it differs from the developed market's
   relativity (same method) by more than two standard errors, use a credibility-weighted value.
2. **Validation:** one out-of-time fold (fit 2023, validate 2024). Report overall D² and, separately, A/E for
   2024 new business (motor 382 claims, about ±5%; a direction check).
3. **Borrowed from the developed market:** severity trends (two years cannot estimate them), the Pareto tail
   shape, and relativities for small lines as a credibility complement. Each borrowed item carries a "would
   be wrong if" line in the register.
4. **GBM / blend:** Part 1 rule unchanged (+0.003 D²; lowest and highest decile A/E no more than 0.1 further
   from 1 than the GLM's). Its Part 1 cost (about 0.002 on private) is stated in the report.

## 2026-10-23 (afternoon) — Part 2 baseline, ridge strength, buildings fire [notebook 21_part2_baseline]

Code: `tools/patch_part2_oct24.py` (Part 2 configuration, `--market part2`) and `tools/patch_part2_oct23b.py`
(decisions below). Part 1 reproduced exactly after both patches (v11 vs v11_check: +0.000%, 0.00% of rows
differ by more than 1%).

### Baseline with Part 1 settings failed
- Part 1 structure and ridge strength (alpha 0.5 / 0.5 / 0.3): validation D² −0.0003 (motor), −0.0581
  (buildings), −0.0471 (contents), with an inverted lift (lowest decile A/E 1.7–2.9, highest 0.14–0.56).
- **Cause:** sklearn applies the penalty to the mean deviance, so the same alpha shrinks a small book no more
  than a large one; Part 2 trains on one year of a much smaller book. [AI 97]

### Ridge strength chosen by cross-validation inside the training year
- **Rule (fixed before running):** alpha from [0.5, 2, 10, 50, 200, 1000] by 5-fold cross-validation inside
  2023, grouped by policy; 2024 is the validation, not the basis of the choice.
- **Result:** motor 10 (CV D² 0.0177; 2024 D² 0.0177, tails 0.75 / 0.98); contents 2 (CV 0.0394; 2024 0.0316,
  tails 1.04 / 0.92). The CV choice was also the best alpha on 2024 in both lines.
- Buildings: no alpha gave a positive 2024 D²; overall A/E 0.57–0.60 at every alpha (next section).

### Buildings: 2023 fire cluster; fire priced separately
- **Finding:** 2025-level cost per weight 523.6 (2023) vs 313.3 (2024). Fire explains about 90% of the gap
  (277 vs 92 per weight): 49 vs 21 claims, frequency 4.3 vs 1.7 per 1,000; 9 of the 15 largest buildings
  claims are 2023 fires. Lowering the cap does not close the gap (2023/2024 ratio 1.49 at a 100k cap):
  more claims, not larger ones. Fire severity is unrelated to sum insured (rank correlation −0.003; median
  claim 14% of sum insured).
- **Developed market fire is stable:** 1.7–2.1 claims per 1,000 and 90–104 per exposure in 2021–24.
  Emerging 2024 (1.7, 92) matches it; at the developed frequency 2023 would expect about 22 fires, not 49
  (about 5.9 standard deviations).
- **Where (depth-3 Poisson tree on 2023 fires, checked on 2024; the team asked for it):** two leaves defined
  by address-average weather (low hail days; low wind or low elevation), i.e. location, held 34 of 49 2023
  fires (11.5 and 8.0 per 1,000) but were normal in 2024 (1.4 and 2.5). A regional cluster in 2023, not a
  stable risk factor. [AI 98]
- **Consequence:** a single GLM learns the cluster as relativities (e.g. low-hail areas = high risk), which is
  why the buildings lift was inverted.
- **Decision:** buildings = GLM on all perils except fire (alpha 10 by the same CV rule) + fire at one rate per
  exposure: the **developed market's 2021–24 average at 2025 level, uncapped (96.04)**. The buildings
  large-loss loading is switched off (the fire rate is uncapped; no other buildings claim exceeds the cap).
  - Options considered before choosing: emerging two-year average (184 per weight, treats the 2023 cluster
    as a yearly event); developed average (chosen: stable over four years and equal to emerging 2024); a
    midpoint (139, no basis for the event weight). The 2024 validation cannot choose between them (it
    favours whichever level equals 2024 fire), so it was read as a sensitivity only.
  - **Uncertainty (register):** if regional fire clusters recur in this market, buildings is under-priced.
    The 2023 excess over the developed rate is about 180 per exposure in that year.
- **Validation (all perils):** D² −0.0017 (single GLM) → 0.0257 (split).

### Fewer features: tested, rejected by the pre-set rule
- **Concern (team):** 43–46 features per line on two years of a small book make the GLM hard to explain,
  close to a black box. [AI 99]
- **Rule (fixed before running):** Part 1 stability test: drop a feature if the rank correlation of its
  one-way claim frequency relativities between 2023 and 2024 is below 0.3 (levels with ≥ 20 claims each
  year; buildings without fire). Exceptions by judgement: hist_1y kept (not testable: 2023 has no observable
  history; strong in Part 1); motor basement and listed_building dropped (no plausible link). Removal adopted
  if the cross-validated D² inside 2023 falls by no more than 0.0005.
- **Result:** stable features 29 of 43 (motor), 25 of 44 (buildings), 26 of 46 (contents). CV D² full →
  reduced: motor 0.0177 → 0.0156, buildings 0.0034 → −0.0027, contents 0.0394 → 0.0099. **All three fail;
  full feature sets kept.** With a few hundred to a few thousand claims a year, a five-level rank
  correlation between two years is too noisy and removed useful features (e.g. contents sum_insured,
  security_level, tenure).
- Transparency is kept by the model form: one rating table per feature, ridge shrinking thin levels toward
  the average, and errors that can be traced (the fire cluster was found and removed).

### Pipeline validation (2024, `python -m src.pipeline --market part2 --validate`)
| Line | D² | A/E | Lowest decile | Highest decile | New business A/E | Renewal A/E |
|---|---|---|---|---|---|---|
| Motor | 0.0177 | 1.051 | 0.749 | 0.976 | 0.890 | 1.073 |
| Buildings (all perils) | 0.0257 | 0.910 | 0.662 | 1.660 | 0.596 | 0.947 |
| Contents | 0.0316 | 0.940 | 1.036 | 0.920 | 1.381 | 0.897 |
| **All lines pooled** | **0.0806** | **0.991** | | | | |
- Open for v2: new-business relativity against the developed market (rule 1): buildings over-prices new
  business (0.60), contents under-prices it (1.38); buildings highest decile under-priced (1.66).

### E9-P2: black box max vs ours on the emerging market (Oct 23 evening) — benchmark only [tools/exp_blackbox_p2.py]
- Same as E9 (LightGBM in every line, 127 leaves, 3 seeds, every non-leaking feature, no peril split, no hand-built
  interactions); trees chosen on a 20% policy holdout inside the training year. Fit 2023, validate 2024, all perils.
- D²: motor 0.0177 (ours) vs 0.0176 (black box); buildings 0.0257 vs −0.0182; contents 0.0316 vs 0.0055;
  pooled 0.0806 vs 0.0623. Black box A/E: buildings 0.60 (it learned the 2023 fire-cluster level as normal and
  over-priced 2024 buildings by about two thirds), pooled 0.84.
- Tails (lowest / highest decile A/E): buildings 0.40 / 0.55 (ours 0.66 / 1.66); motor 0.96 / 1.40 (ours
  0.75 / 0.98); contents 1.22 / 1.14 (ours 1.04 / 0.92). Seed spread per row 8.5–10% (ours 0).
- Against the prediction written on Oct 22: "the black box scores higher" did not hold (nor in Part 1, E9);
  "its errors fall on the safest customers" held for buildings (safest 10% priced 2.5× actual) but not
  consistently in motor and contents. The fire-cluster area check (hail days ≤ 16.25, 59% of weight) did not
  separate the models; the evidence is the buildings level.
- Caveat: one training year in this fold; the final models use two.

### E13: shallow trees on frequency and severity by peril (Oct 23 evening) — screening [tools/exp_trees_p2.py]
- Per line and peril: LightGBM depth 1 (main effects) vs depth 2 (pairs), fit 2023, checked on 2024 (D² after scaling
  to the 2024 total). Frequency on all rows; severity on claims with net cost > 0 only. Screening rule (set before
  running): pairs go to a GLM test if the 2024 gain is ≥ +0.002 (frequency) or ≥ +0.005 (severity).
- Severity: all nine peril models have negative 2024 D², depth 1 included (−0.01 to −0.08): within a peril, claim size
  is not predictable from the rating factors. Severity is effectively a peril average.
- Frequency pairs that hold out of time: motor own_damage +0.0120 (cover_type × voluntary_excess, cover_type ×
  years_licensed, cover_type × ncb_years; own damage is covered only under comprehensive cover) and motor
  third_party_prop +0.0033 (ncb_years × years_licensed, driver_age_band × gender). All other perils negative.
- Flood frequency is strongly predictable from main effects alone (depth-1 D² 0.25 buildings, 0.16 contents: elevation,
  flood zone, distance to river); pairs add nothing (−0.006). Buildings fire (−0.04) and escape of water have no
  predictable structure, supporting the flat fire rate.
- Next (to test under the Part 1 rule): motor own_damage structure (E14); a buildings flood GLM without pairs once the
  team decides how flat-rated parts enter the tail condition (E12); peril frequency × peril-average severity.

### Rule 1 applied: new business against the developed market [notebook 22_part2_new_business]
- **Credibility formula (fixed before running):** if the emerging relativity differs from the developed one by
  more than two standard errors, use Z x emerging + (1 - Z) x developed on the log scale, with limited-fluctuation
  credibility Z = min(1, sqrt(n / 1,082)), n = emerging new-business claims (full credibility: 90% within ±5%).
- **Method:** GLM on 2023–24 (emerging) and 2021–24 (developed) with the same features (developed ages banded
  like the emerging age bands; buildings without fire in both); emerging standard error by bootstrap over
  policies (30 resamples).
- **Result:** new_business relativity motor 1.110 vs 1.086 (0.8 SE), buildings 1.059 vs 1.037 (0.5 SE),
  contents 1.077 vs 0.983 (1.5 SE). **No line differs by more than two standard errors; the emerging values
  are kept (no change from p2_v1).** The raw gaps (e.g. motor 1.17 age-standardised vs 1.36–1.43) were
  portfolio mix, explained by the other rating factors.
- **Note:** renewal_count is 0 for every new-business row, so part of the new-business effect sits in its 0 level;
  the comparison is like for like (same structure in both markets), but the total new-business loading for the
  report must combine both factors.

### Part 1 correction: relative premium (Oct 23) [notebook 22]
- written_premium is the full annual premium; median written premium in Part 1 is flat by start month every year
  (contents 2021: 115–118) and rises about 5–6% a year. There was no mid-2021 rate step: the policy scan divided
  premium by exposure (December rows ×34). Contents validation D² is the same under all three definitions
  (year 0.0802, month 0.0804, annual 0.0802; mean of 2023 and 2024), so v10's result stands but its stated
  reason was wrong. [AI 100]

### E12: buildings flood (Oct 23 evening) — not adopted [notebook 22]
- Diagnosis: the under-priced highest decile (A/E 1.66) is flood: 610–670 of 790–870 actual cost per weight
  in decile 10, almost none in deciles 1–4. One ridge strength cannot fit flood (concentrated) and the other
  perils (alpha 2 fixed decile 10 but broke deciles 7–9).
- Rule (fixed before running): Part 1 GLM-setting rule on 2024 (all perils): D² +0.0005 and lowest/highest
  decile A/E no more than 0.1 further from 1 than the baseline; alphas by CV inside 2023.
- Result: A baseline 0.0257 (low 0.66, top 1.66); B + Part 1 flood pairs 0.0411 (low 0.31); C flood GLM with
  pairs + other-perils GLM 0.0631 (low 0.51, top 0.77); D flood GLM without pairs 0.0433 (low 0.53, top 0.80).
  All fail the lowest-decile condition (C by 0.15). **Not adopted; p2_v1 stays.**
- The gain forgone is large (C: D² +0.037 on buildings); the condition protects the safest customers from
  over-pricing, the team's stated priority. Hypothesis to test as a new, pre-registered experiment: the flat
  fire rate (96 for every policy) drives the low-decile over-prediction in every variant.

### Submission p2_v1 (Part 2 baseline)
- `python -m src.pipeline --market part2 --out submissions/p2_v1.csv`
- **Expected public score, written before submitting: 0.06–0.10 (centre about 0.08).** Basis: pooled 2024
  validation D² 0.0806. Up: the final model trains on two years. Down: 76% new business with an uncertain
  relativity; history for 24% of test rows; the fire assumption; a smaller test (more public-score noise
  than Part 1). The range is wide on purpose; later submissions are judged against this one.

- **Public score (Oct 24, 00:08, after the host fixed the scorer): 0.11166**, above the written range 0.06–0.10
  (miss, upward by about 0.012). Most likely cause: the validation fold trains on one year (2023, with the fire
  cluster and an unstable new-business effect); the submission trains on two. Expected ranges for later
  submissions are set relative to this score. First Part 2 submission on the leaderboard; selected by hand.

## 2026-10-24 — Tail rule for flat-rated parts; E12 re-judged

### Rule change: tail condition with flat-rated parts (Oct 24, decided by Woojin)
- From now on, when part of a line is priced at one flat rate per exposure (buildings fire), the lowest/highest
  decile condition is measured on the modelled part only: deciles ranked by predicted rate (the order is the same
  with or without the flat part), A/E = actual ÷ predicted excluding the flat-rated peril. D² and overall A/E stay
  on all perils (the basis of the leaderboard score); the flat rate is checked through the overall A/E and its
  own assumption (developed average).
- Why: in the safest decile the flat fire rate (96) is most of the prediction, so with fire included the condition
  measured whether fire happened to hit those policies, not whether the model ranked them well. The Part 1 rule was
  written when every model priced all perils together, so the two readings were the same.
- Disclosure: the issue was noticed after E12 failed the condition (AI 102). The change applies to every later
  comparison, not only E12; E12 is re-judged below under both readings.

### E12 re-judged under the Oct 24 tail rule — C adopted [notebook 23_part2_flood_rule]
- Reading a (all perils, as on Oct 23) reproduced exactly: A 0.662 / 1.660, C 0.514 / 0.767.
- Reading b (modelled part, the rule above): A 0.742 / 1.884; B 0.521 / 1.839 (fails); C 0.926 / 0.783
  (passes); D 0.948 / 0.788 (passes). D² (all perils): A 0.0257, B 0.0411, C 0.0631, D 0.0433.
- **Adopted: C** (highest D² among those passing): buildings = flood GLM (12 flood-related features + Part 1's five
  flood-geography pairs, alpha 0.5 by CV inside 2023) + other-perils GLM (alpha 10) + fire at the developed rate.
  In the pipeline: `tools/patch_part2_oct24c.py` (values fixed from this notebook).
- With fire excluded, C prices the safest decile closer to cost than the baseline (0.93 vs 0.74): the Oct 23 failure
  came from the flat fire rate, not from over-pricing safe customers.
- Note: E13 found no out-of-time gain from pairs on flood frequency, but on cost C (pairs) beats D (none) by 0.020;
  the pairs may act through claim size (e.g. sum insured × flood zone).

### E16: features shared by ours and the black box (Oct 24) [notebook 23]
- Public (Oct 24, 11:44): p2_v2_flood 0.11185 (expected 0.115–0.130: miss, below; +0.0002 over p2_v1 against a
  validation gain of +0.011); p2_blackbox_experiment 0.07566 (expected 0.09–0.11: miss, below). The black box with every
  model-side feature scores far below ours, so the gap to the leaders (0.136–0.164) is not model structure or those
  features; candidates are what both share: average weather, the target construction, the excluded features, and
  training on emerging data only.
- Validation fold, pooled D² against the base 0.0806 (run on the pre-flood config; relative comparison):
  actual-year weather 0.0822 (+0.0016; contents up, buildings safest decile 0.49), marketing variables 0.0806 (0),
  relative premium (annual definition) in all lines 0.0841 (+0.0035). None explains a gap of 0.05.
- Not visible to this validation: the level assumptions (trends borrowed from developed apply to both actual and
  predicted in the fold). Tested next: developed data as training data (E17).

### Submission p2_v3_developed (Oct 24) — expected public score written before submitting
- `python -m src.pipeline --market part2 --out submissions/p2_v3_developed.csv` (E17 adopted: motor developed
  relativities, buildings emerging other perils + combined flood + fire flat, contents combined + market).
- Pipeline validation (fit 2023 + developed 2021–24, validate 2024): motor 0.0373, buildings 0.0720 (tails b 0.89 / 1.02),
  contents 0.0638; pooled 0.1096 (p2_v2 0.0919, p2_v1 0.0806). Part 1 reproduced exactly after the patch.
- **Expected public: 0.120–0.155 (centre about 0.135).** Basis: public/validation ratios so far 1.39 (p2_v1) and 1.22
  (p2_v2) give 0.134–0.152; additive (p2_v2 public + validation gain 0.018) gives 0.130; if the gain does not carry
  over, as with p2_v2, about 0.112. This submission tests whether validation gains reach the leaderboard.
- **Public (Oct 24, 12:02): 0.12187**, inside the written range 0.120–0.155 (low end); +0.010 over p2_v2 against a
  validation gain of +0.018 (about half carried over; p2_v2 carried almost none). Developed data as training data is
  confirmed as a real gain; the gap to the leaders (0.136–0.164) remains 0.015–0.04.

### E18: weight of developed rows in combined training (Oct 24) — no change [notebook 23]
- Rule (fixed before running): candidates per line chosen by 3-fold CV inside emerging 2023 (developed rows always in
  training, level set on the emerging rows); adopted if 2024 D² is at least +0.0005 over v3 and the tail condition holds.
- Motor: CV picks developed only (current, CV 0.0430; combined weights 1 / 0.3 / 0.1: 0.0426 / 0.0413 / 0.0381) — kept.
- Contents: CV picks developed weight 0.1 (CV 0.0783 vs 0.0754): 2024 D² 0.0647 vs 0.0638 (+0.0009), but the highest
  decile moves from 1.03 to 0.83 (0.14 further from 1; limit 0.1) — kept at weight 1.
- Buildings other perils: CV picks combined weight 1 (2024 D² 0.0991 vs 0.0720) = E17b's B3, which fails the lowest
  decile under rule b (0.46 vs 0.89) — kept emerging only. (The notebook's buildings tails were computed on the other
  perils only; the decision uses the rule-b figures from E17b.) Third time the same result: combining the other
  buildings perils raises D² by about 0.02–0.03 but over-prices the safest emerging homes.

### E19: weather in a fair fold (Oct 24) [notebook 23]
- Concern: the address average (2023–24) includes the validation year, which could flatter it; the test's 2025
  weather differs (freezing days 17 -> 29, hail days 17 -> 11).
- Pooled 2024 D² with v3: average 2023–24 0.1096; average 2023 only (as the test sees it) 0.1104; actual weather of
  the year 0.1105. No fold bias and no gain from actual weather (contents lowest decile 0.46 with actual weather).
  Weather is not the cause of the leaderboard gap; the address average stays.

### E9-P2b: black box with the same data (Oct 24) [tools/exp_blackbox_p2b.py]
- Combined (developed + emerging) LightGBM vs ours (v3), validation: motor 0.0398 vs 0.0373 (+0.0025, below the
  +0.003 rule; safest decile 0.46 vs 0.72); contents 0.0531 vs 0.0638. Buildings re-run pending (the black-box config
  had kept the flood GLM; fixed). Same data lifts the black box a lot (motor 0.018 -> 0.040), but it does not beat
  the GLM by a margin: the remaining gap is not model capacity.

### Diagnostic submissions p2_v3_level_x0.9 / x1.1 (Oct 24) — expected directions written before submitting
- Every v3 prediction multiplied by 0.9 / 1.1 (ranking unchanged; level only). The validation cannot see level
  assumptions (trends, completeness, caps, loading, fire rate: applied to actual and predicted alike).
- Expected if our level is right: both below 0.12187. If x0.9 rises, our level is too high (trend or loading);
  if x1.1 rises, too low. Changes within ±0.003 mean level is not the cause of the gap. Diagnostics only, never
  the final selection.

### Result: level probes (Oct 24)
- Public: x0.9 0.10901 (-0.0129), v3 0.12187, x1.1 0.13073 (+0.0089): far outside the ±0.003 written beforehand.
  First read as 'our level is too low' (corrected below). For Tweedie p=1.5 a uniform scale k gives D(k) = a - b/sqrt(k) - c*sqrt(k) exactly, so three
  points fix the curve: b 0.686, c 0.473, optimum k* about 1.45 (D² about 0.142). The optimum k* = sum(y/sqrt(mu)) / sum(sqrt(mu)) is a
  sqrt(prediction)-weighted A/E on the public rows, not the total A/E. k* is NOT applied: it is a pointer to the wrong assumption, which must be found, fixed with an
  actuarial reason and validated before any submission.

### Diagnostic submissions p2_v3_<line>_x1.45 (Oct 24) — expectations written before submitting
- One line at a time multiplied by 1.45. c is split by line from our own predictions (sum of sqrt(prediction));
  each probe then gives that line's b and optimum k*_line. Check: the three b must add up to 0.686 (±0.01).
- Expected: the line(s) carrying the gap gain; a line already at the right level loses. Diagnostics only.

- Submitted: motor and buildings probes only (4 submissions left today); contents b derived as total minus the
  other two, check submission later. Expected gains if all lines are equally low (k* 1.45 each, c share motor 0.559,
  buildings 0.273, contents 0.168): motor +0.0111, buildings +0.0054 (contents +0.0033). Much more in one line and
  less or negative in the other = that line carries the gap; both near these = a cause common to all lines
  (valuation date, exposure, trends).

- Result: motor x1.45 0.13592 (+0.0141), buildings x1.45 0.12762 (+0.0058). Optimum by line: motor about 1.52,
  buildings about 1.47, contents about 1.21 (derived, least certain). Every line is too low, motor and buildings by
  about the same factor: a cause common to the lines is more likely than a line-specific assumption. Next: emerging
  raw cost per exposure 2023 / 2024 against the 2025 prediction; valuation date; report lags; test exposure.

- Correction (Oct 24): the 2025 prediction is already above the emerging raw cost per exposure (motor 489 vs
  362 / 319 in 2023 / 2024; buildings 338 vs 492 / 287; contents 83 vs 76 / 73), so 'level 45% too low' is not a
  credible reading. Validation 2024 (fit 2023): k* motor 1.09, buildings 0.93, contents 0.91, equal to the total A/E
  (1.09 / 0.91 / 0.94): no steepness problem and no level problem visible in the fold. The test differs from training.
  Test exposure matches days / 365 exactly (all lines). Largest test-only difference: new business 76% in every line.

### Diagnostic submission p2_v3_newbiz_x1.45 (Oct 24) — expected before submitting
- Test new-business rows x1.45 in all lines (c share of new business 0.784). Expected gain: +0.0155 if every row is
  equally low; +0.0234 if new business carries the whole gap; about -0.013 if new business is right and renewals are
  low. Diagnostic only.

- Result: 0.14115 (+0.0193), between the two hypotheses. Solved by group: new business k* about 1.51,
  renewals about 1.24 (derived, less certain). Two layers: the whole 2025 test is costlier than the training
  pattern (about 1.2), and new business more so (about 1.2 on top). Applying both would give about 0.142 in theory;
  NOT applied (fitted to the leaderboard). Next: find a data or actuarial reason for each layer; first candidate
  for the common layer is completeness (two years of emerging lags cannot show lags beyond about 730 days).

### Broker portfolio load on 2025 new business (Oct 24) — team decision [notebook 23]
- **Inference.** Validation 2024 is right (k* about 1 in every line), but the test is costlier: the change is not in
  the training data. The competition text names it: "at the start of 2025 it takes on a large portfolio from a
  broker, so most 2025 policies are new business" (76% of test rows). Such a book was not underwritten by us and its
  claims history is not in our data; a transferred book is commonly worse than customers who chose to switch.
- **Checked and ruled out** (data or the text): exposure, completeness, weather, developed-market level ("costs are
  different"), steepness of relativities. Diagnostics with expected results written before each: level x0.9 / x1.1,
  motor / buildings x1.45, new business x1.45 (new business k* about 1.51, renewals about 1.24 derived).
- **No evidence inside the training data:** validation k* of broker new business 1.00 / 0.61 / 1.43 (noise); test new
  business has the same channel mix (70/25/5) and start dates as training new business. The book is identified only
  by the new_business flag.
- **Decision:** new-business test rows x1.5 in every line (range 1.4-1.6 changes the public score by about ±0.0007);
  renewals unchanged (derived, uncertain, worth +0.0013 at most, no reason in the text). Applied after the model
  (`nb_load` in src/config.py); validation cannot test it, since the book is not in the training years.
- **Disclosure:** the existence and location of the load come from inference; its size comes from the diagnostic
  submissions, because the book's own loss experience (which a real acquirer would request) is not available.
- Expected public for p2_v4_brokerload: 0.139-0.142.

- Result: p2_v4_brokerload 0.14133 (expected 0.139-0.142; theory from the probe curves 0.1413). Selected as the
  current final Part 2 submission.
- Follow-up (same day): the Dataset Description says paid_to_date is net of excess, and closed claims have
  paid = incurred (100%) while 16-29% have incurred <= excess, so the claim amounts may already be net of excess and
  our target deducts it twice. Removing the second deduction raises the emerging target x1.20 / x1.05 / x1.19
  (renewals about x1.17), which would explain the common layer (renewal k* 1.24) and leave about 1.3 for new
  business. Being checked before any change (claims by voluntary excess level).

### Claim amounts are net of excess: the target deducted it twice (Oct 24) [notebook 23]
- **Evidence:** the Dataset Description says paid_to_date is net of excess and incurred = paid + case estimate;
  closed claims have paid = incurred (100%) while 16-29% have incurred <= excess (impossible if gross: the insurer
  would pay 0). Claim frequency falls with the voluntary excess (motor own damage, excess 1,000 vs 0: 0.47 emerging,
  0.59 developed): losses below the excess are not reported, and reported amounts are loss minus excess. No zeros;
  small amounts appear at every excess level. The Oct 16 reading ("gross, because some incurred <= excess") had the
  evidence backwards [AI 107].
- **Effect:** removing the second deduction raises the emerging target x1.20 motor, x1.05 buildings, x1.19 contents
  (developed x1.12 / 1.05 / 1.18). Invisible to validation, which deducts twice on both sides.
- **Decision:** `AMOUNTS_NET` in src/target.py (default False, so Part 1 reproduces v12 and its tests); on in PART2,
  for the emerging and the developed data used there (developed relativities, fire rate).
- **Part 1:** the final v12 has the same double deduction (developed target about 11-18% low by line). Part 1 is
  closed; reported as a limitation, consistent with the leaderboard favouring a higher level throughout Part 1.
- **New-business load re-estimated:** decomposition suggests about 1.3 (1.51 / 1.16). Submissions after the 8 pm
  reset: v5a (fix only), expected about 0.135; v5 (fix + new business x1.3), expected 0.140-0.145. The two give the
  new-business optimum on the corrected basis.

- **Run (Oct 24):** tests 46 passed; Part 1 pipeline unchanged (AMOUNTS_NET off). Part 2 with the fix: motor
  emerging level factor 0.742 -> 0.784 (consistent with x1.20 emerging vs x1.12 developed), fire rate 96.04 -> 97.05.
  Validation 2024 (actuals now on the corrected definition, so D² not comparable with earlier rows): pooled D² 0.1071,
  A/E 1.006; lowest decile motor 0.80, buildings 0.35 (modelled part 0.59), contents 0.74 (one small year).
  A correction of the target definition, decided by the documentation, not by the score (as on Oct 19).
- v5 total +1.3% vs v4 (fix about +15%, load 1.5 -> 1.3). Expected public: v5a (fix only) 0.131-0.137;
  v5 (fix + new business x1.3) 0.139-0.145, about equal to v4: the point of v5 is the definition, not the score.

### Part 1 impact of the double excess deduction, measured by a late submission (Oct 24)
- v12_net_late = v12 with only the second excess deduction removed (tools/exp_freqsev.py, AMOUNTS_NET on); does not
  change the Part 1 result or selection. Expected vs v12, written before submitting: +0.001 to +0.003.
- **Result:** private 0.13301 / public 0.12670 vs v12 private 0.13099 / public 0.12336. The error cost Part 1
  **0.0020 on the private score** (0.0033 public). Total +8.9% (motor +10.9%, buildings +4.7%, contents +16.5%),
  correlation 0.997: mostly level. The freq x sev rule gave the same choice on the corrected target (motor adopted,
  +0.0019; buildings failed the tails).
- For reference, the E10 stack (not selected, tier 3) had private 0.13311, +0.0021 over v12, at the cost of
  over-pricing the safest 10% by 30-40% in validation.

### Blind design by a second AI, compared with ours (Oct 24) [AI 108]
- A fresh chat (Claude Opus 5.5, no project context; the Fable spending limit was reached) was given only the
  Overview, the Dataset Description and raw counts, and asked how it would build the model.
- It defined the target correctly at once ("paid is already net of excess; do not deduct it again"), the error we
  found today. It asked whether incurred is already net of recoveries. **Checked:** no; recoveries are a fixed share
  of incurred (own damage 0.8, theft 0.3) and never exceed it, so incurred - recoveries is right.
- For the broker book it did not know the direction (default factor 1.0 ±15%) and proposed looking for identifying
  columns. **Checked:** test vs training new business on days_quote_to_inception, written_premium (+4.5-6%, the 2025
  rate level), missed payments, prior claims, licence points, years at address, household size, branch,
  previous insurer, campaign, payment method, marketing segment, discount, document preference, email domain: all
  alike (TVD 0.003-0.043). The book is identified only by the new_business flag.
- It proposed the developed model as an offset with emerging relativities by credibility; ours uses one emerging
  level factor for motor, so emerging-only effects (gender, regions E01-E06) are not learned. Tested as E21.

### E21: developed model as offset, emerging relativities shrunk toward it (Oct 24) — rule fixed before running
- Base o = developed GLM on emerging features (as v5); emerging GLM on all emerging features fitted to y/o with
  weight w*sqrt(o) (exact for Tweedie p = 1.5), ridge alpha fixed at the CV values (motor 10, contents 2); level
  rebalanced to the training total. Motor and contents; buildings excluded (E17: developed data over-prices its
  safest decile). Corrected target (net of excess). Fold: fit 2023, validate 2024.
- Rule (Part 1 GLM rule): adopt per line if D² +0.0005 or more and both tails no more than 0.1 further from 1 than
  the current model. Alpha x0.3 and x3 reported as sensitivity only.

- **Result:** motor D² 0.0366 -> 0.0368 (+0.0002), tails alike (0.80 / 0.88 -> 0.79 / 0.89): not adopted.
  Contents 0.0538 -> 0.0542 (+0.0004, 0.0001 short of the rule): not adopted, although the safest decile moves from
  A/E 0.74 to 1.06 (top 0.99 -> 0.97); recorded as an observation, the rule is not changed after the result.
  Sensitivity: alpha x0.3 motor +0.0003, contents -0.0025; x3 motor +0.0001, contents +0.0003. Only one feature is
  emerging-only (43 vs 42), so the developed base already carries the relativities: the structural difference
  from the blind design does not change the score; the decisive difference was the target definition.

### Independent review of Part 2, triaged (Oct 24) [AI 109]
- Fresh chat (Claude Opus 5.5) with config, pipeline, target, the Dataset Description and the Part 2 log.
- **Rebutted with data:** recoveries already in incurred (no: fixed shares 0.8 / 0.3, never above incurred);
  730-day truncation of completeness (emerging vs developed Lynden-Bell within 0.01-0.04); IBNER (Oct 17: open and
  closed severity alike); test-only missing weather for broker addresses (100% of test new-business addresses have
  2023-24 weather); history encoding (test new business and training 2023 / 2024 new business share the 'missing'
  level); fire as a weather effect (2023, 49 fires, was less dry than 2024, 21 fires: wildfire 0.503 vs 0.549, dry
  summer 0.679 vs 0.711; 2024 emerging fire frequency 1.74 per 1,000 matches developed 1.7-2.1, so the developed
  flat rate stands; 2025 is wetter, 0.605).
- **Confirmed:** completeness by calendar year biases new business. 2024 row-level completeness (each row's own days)
  vs the year average used: motor new business 0.777 vs 0.839 (renewals 0.847), buildings 0.922 vs 0.953, contents
  0.944 vs 0.965 (2023 within 0.01). New-business rows (mean exposure 0.47, mostly late in the year) were given too
  much weight, so the new-business risk was under-estimated by about 4% motor, 2% buildings, 1.5% contents; the fold
  could not see it (same weights on validation actuals). Fixed as E22.
- **Accepted, small:** sev_trend docstring ("gross amounts") outdated; BI trend 0% borrowed although the emerging
  market has no reform (sensitivity); buildings large-loss loading off (developed observed 2.33, about 0.7%).
- **Accepted for the report:** probe mathematics confirmed (derivation and curvature, ±0.0007 per 0.1 of load);
  report k* intervals from subset bootstrap; three classes of assumption (documented definition / calibrated on the
  leaderboard / borrowed and unverifiable), each with "would be wrong if"; premium sensitivity (±8% of the book per
  0.1 of load) next to score sensitivity; what an insurer would do in practice (broker loss bordereau, review clause,
  monthly A/E monitoring of the book).
- **Deferred:** customer snapshot variables (licence_points) as possible same-year leakage.

### E22: completeness by each row's own period (Oct 24) — rule fixed before running
- Year completeness (the total by year) unchanged; within a year each row's weight is scaled by its own period's
  completeness relative to the year's exposure-weighted average (Lynden-Bell by peril, amount shares by peril).
  `ROW_COMPLETENESS` in src/target.py (default False; Part 1 unchanged), on in PART2.
- Rule (definition correction, Oct 21): adopt if validation D² does not fall by more than 0.0005 and tails stay
  within 0.1. v5a / v5 are rebuilt with E22 before the 8 pm submissions.

- **Result:** validation 2024 (same actuals as v5 before E22): pooled D² 0.1071 -> 0.1077; motor 0.0366 -> 0.0373
  with new-business A/E 0.94 -> 1.00 (as predicted by the row-level completeness); buildings 0.0688 -> 0.0684
  (new business 0.66 -> 0.69); contents 0.0538 -> 0.0539; tails within 0.01 of before. **Adopted.** Part 1 reproduced
  exactly (v11 +0.000%), 46 tests pass. Test total +1.2% (new-business rows up).
- Submissions after the 8 pm reset, expected before submitting: p2_v5a_net_noload (corrected target + E22, no
  load) 0.132-0.138; p2_v5_net (+ new business x1.3) 0.140-0.145. The pair gives the new-business optimum on the
  corrected basis.

### 2026-10-24 — v5a / v5 pre-registered expectations (before 20:00 ET reset)
- p2_v5a_net_noload (amounts_net + E22, no load): expected public 0.132–0.138
- p2_v5_net (same + NB x1.3): expected public 0.140–0.145
- Decision rule: NB optimum on corrected basis kN = bN/cN (cN = 0.4009). If 1.25 <= kN <= 1.35, keep v5 as final, no fine-tuning (0.05 of load = ±0.0002).
  Otherwise build v6 with nb_load = kN.
- Same rule in score terms: keep v5 iff 0.00541 <= S_v5 - S_v5a <= 0.01034. Gain <= 0 means kN <= sqrt(1.3) = 1.140.

### 2026-10-24 20:00 — v5a / v5 results and final choice
- p2_v5a_net_noload: public 0.13541 (expected 0.132–0.138, inside)
- p2_v5_net (NB x1.3): public 0.14287 (expected 0.140–0.145, inside); +0.00154 over v4
- S_v5 - S_v5a = +0.00746, inside the pre-registered window. NB optimum on the corrected basis x1.292; expected public at the optimum 0.14287 (v5 is 0.00000 below it).
- Decision (rule set before the scores): **p2_v5_net is the Part 2 final.** No fine-tuning.

### 2026-10-24 20:15 — E9-P2b rerun on the corrected target (notebook 26)
- Patch: tools/exp_blackbox_p2b.py calls build_line directly and did not set T.AMOUNTS_NET / T.ROW_COMPLETENESS (set only in pipeline.run / validate), so after the Oct 24 fixes it would have compared all models, and the actuals, on the old target. It now sets them from its config, as the pipeline does.
- Validation (fit 2023 + developed 2021-24 -> 2024, all perils), D2 ours vs combined black box: motor 0.0373 vs 0.0390 (+0.0017; black-box seed spread 0.08); contents 0.0539 vs 0.0396; buildings 0.0684 vs -0.0383 (black-box A/E 0.53, level not comparable, left out of the conclusion); pooled 0.1077 vs 0.0832.
- Rule set before the run: black box - ours >= +0.005 -> shape gap is real; < +0.002 -> stop. Motor +0.0017, contents negative -> **GBM line closed.** The public gap to the top teams (0.154-0.168) is not explained by model class on our data.
- Signals for follow-up, validation only, credibility not yet checked: lowest-decile A/E below the line average (motor 0.79, contents 0.74, buildings 0.35) -> model may be too flat; new-business A/E by line in opposite directions (buildings 0.69, contents 1.35, motor 1.00) while the test load is one x1.3 for all lines.

### 2026-10-24 20:30 — Redistribution diagnostics on the 2024 validation; Part 2 data checks reviewed (notebook 27)
- Rows: results/valid2024_rows_ours.csv (59,202 rows; pooled D2 0.1077, same as the E9-P2b rerun). Not committed.
- Slope alpha (rate x (rate/mean)^alpha, total held), chosen per line on 2024 and on two policy halves: buildings 1.15 (halves 1.25 / 1.05), contents 1.10 (1.00 / 1.20), motor 0.90 (0.90 / 0.90); pooled gain +0.0009 in-sample. Rule set before the run (both halves on one side of 1 and pooled gain >= +0.002) not met -> no tilt.
- New business by line, policy bootstrap (2,000 reps): buildings A/E 0.69 [0.35, 1.07], contents 1.35 [0.82, 1.98], motor 1.00 [0.82, 1.21]. All include 1 -> one NB load for all lines kept.
- Buildings lowest decile A/E 0.365 [0.20, 0.56] is large-loss volatility, not mispricing: largest loss in decile 1 is 14.5k; A/E without each decile's largest loss ranges 0.28-0.88 (decile 6: one 300,000 loss is 77% of its losses). The policy bootstrap cannot produce unseen large losses, so buildings decile intervals are too narrow. A flat fire rate acting as a floor was checked and rejected (fire share 0.44 vs 0.40 in deciles 1 and 2).
- Buildings accidental_damage_cover: A/E without cover 0.77 [0.59, 0.98], with cover 1.11 [0.69, 1.60]; intervals overlap; vs line A/E 0.91, z = -1.4 -> not adjusted (Limitations).
- Conclusion with the E9-P2b rerun: the 2024 validation does not support finer redistribution than the current model.
- Data checks (results/checks_part2, run Oct 23) reviewed: customer_service_contacts is post-claim (mean 2.9-3.4 with a loss vs 0.42-0.45 without; test 0.40 on every line), confirmed leakage, not a model feature on any line. licence_points (customers.parquet snapshot): 0.91-0.94 with a loss vs 0.90 without, test 0.903 -> no time leakage; backlog item closed. prior_claims_5y: 0.32-0.36 with a loss vs 0.26-0.27 without, test 0.26-0.27; the loss-row mean is far below 1, so a policy's own claims are not counted -> no leakage. Targets of exactly 300,000 are the buildings cap applied after adjustment (fire claim, incurred 361,093, sum insured 362,000), not a raw value.

### E23: relative premium on the v5 structure (Oct 24, notebook 27) — rule fixed before running
- Column audit of both data folders against the feature lists (src/features.py EXCLUDE, config DROP, predict_rate):
  every exclusion re-checked with a one-way fit 2023 -> 2024; only written_premium was excluded without a test on the current structure (E16 +0.0035 on the old base).
- Rule (Part 2 GLM rule): adopt per line if 2024 D2 +0.0005 or more and neither tail moves more than 0.1 further from 1.
- Result, base -> prem_rel: motor 0.0373 -> 0.0371 (no); buildings 0.0684 -> 0.0688 (+0.0004, no; low decile 0.35 -> 0.54);
  contents 0.0539 -> 0.0553 (+0.0014; low 0.74 -> 0.86, top 0.99 -> 0.97) -> **adopted in contents** (as in Part 1). Pooled all-lines +0.0003.
- Not the cause of the leaderboard gap. Limitation (as Part 1): circular, inherits the insurer's own relativities.
- **p2_v6 (v5 + E23) expected public, written before submitting: 0.1425-0.1450** (contents gain about half carried over, as before).
  v6 becomes the final unless its public score is below 0.1420 (then investigate, keep v5).

### E14: motor frequency x severity on the v6 structure (Oct 24, notebook 28) — rule fixed before running
- Part 1's final motor structure (E11, v12: +0.0025 validation D2) was never carried into Part 2, which uses the v11 single Tweedie GLM.
- Design: Poisson frequency and Gamma severity GLMs, both fitted on the developed table (as v6 motor, developed relativities);
  same features, bands, target (2025 level, capped, net of excess), completeness weights; ridge for each part chosen inside the
  developed data (fit 2021-23, choose on 2024) from Part 1's list; one emerging level factor on 2023. Validate emerging 2024.
- Rule: adopt if motor 2024 D2 >= base + 0.0005 and neither decile A/E moves more than 0.1 further from 1 (base 0.0373, low 0.794, top 0.894).
- Expected: +0.000 to +0.003. If adopted, the new-business load is re-measured before any submission.
- **E14 result:** ridge chosen on developed 2024: frequency 0.001, severity 0.01. Motor 2024 D2 0.0373 -> 0.0364 (-0.0009); low 0.794 -> 0.766, top 0.894 -> 0.846 (within the limit); emerging level x0.765. **Not adopted.** Part 1's +0.0025 does not carry over: the relativities already come from 98k developed claim rows.

### Buildings ridge re-checked on the final training data (Oct 24, notebook 28)
- Concern: sklearn's penalty is on the mean deviance, so an alpha chosen on one year (2023 CV) acts about twice as strongly on two years.
- Same rule as Oct 23 (0.5/2/10/50/200/1000, 5-fold CV by policy): 2023 only picks 10 (CV D2 0.0012); 2023+2024 also picks 10 (0.0082; next 2: 0.0056). **No change.**

### E24: buildings other perils on combined data, re-run on the corrected target (Oct 24, notebook 28) — rule fixed before running (decided by Woojin)
- E17b / E18 (old target): combined training raised buildings 2024 D2 by about +0.02-0.03 but failed the lowest decile (rule b: 0.46 vs 0.89).
- Notebook 27 (AI 111) showed buildings decile cost A/E is dominated by single large losses (A/E without each decile's largest loss 0.28-0.88),
  so a one-decile, one-year cost A/E cannot separate mispricing from chance.
- Candidates: developed weight 1 / 0.3 / 0.1 (E18 list); flood GLM and the flat fire rate unchanged; level on emerging 2023; validate 2024.
- Rule: adopt the best candidate if 2024 D2 (all perils) >= current + 0.005 AND, with each decile's largest loss removed (modelled part, rule b),
  neither the lowest nor the highest decile A/E moves more than 0.1 further from 1 than the current model. Rule b without removal reported too.
- The tail reading changed before running, because of the large-loss evidence above, not because of any E24 result.
- Rule written 21:03:33, run started 21:03:37 (Oct 24).
- **E24 result:** 2024 D2 (all perils) current 0.0684 -> dev weight 1 / 0.3 / 0.1: 0.0950 / 0.0952 / 0.0937 (+0.027 / +0.027 / +0.025). Lowest decile A/E with each decile's largest loss removed: 0.515 -> 0.320 / 0.387 / 0.371 (0.13-0.20 further from 1; limit 0.1); top within the limit. Rule b without removal: 0.615 -> 0.370 / 0.441 / 0.426. **Not adopted.**
- Fourth time the same result (E17b, E18 twice, E24), now with the largest loss removed: developed relativities over-price the safest emerging homes (structural, not chance). Cost of protecting the safest decile, for the report: about +0.027 buildings validation D2 forgone.

### E25: buildings combined base + emerging corrections on selected features (Oct 24, notebook 28) — rule fixed before running
- Designed after E24 failed the lowest decile (disclosed). Aim: keep the combined-data gain (+0.027) and fix the safest decile.
- Base o: other-perils GLM on combined data (developed weight 1, pipeline default; E24's best weight 0.3 is not used because it was picked on 2024),
  level on emerging 2023. Flood GLM and the flat fire rate unchanged.
- Feature selection on emerging 2023 only (2024 not used): for each feature, a one-feature GLM on top of o (offset via y/o with weight w*sqrt(o),
  exact for Tweedie p = 1.5, as E21); 5-fold CV inside 2023 grouped by policy; keep features with CV D2 gain >= +0.001, at most the top 5.
  Developed-absent features (e.g. gender) are candidates too. One correction GLM on the selected features, alpha 10, fitted on 2023.
- Rule (same as E24): adopt if 2024 D2 (all perils) >= current + 0.005 AND, with each decile's largest loss removed (modelled part, rule b),
  neither tail moves more than 0.1 further from 1 than the current model. 2024 is used once.
- **E25 result:** no feature passed the screen inside 2023 (largest CV gain +0.0003: wind_exposure_index; then wildfire_index, smoke_alarms, new_business, energy_rating +0.0002), so E25 = E24 (combined): 2024 D2 +0.0266, lowest decile (largest removed) 0.515 -> 0.320. **Not adopted.** Buildings other perils stay on emerging data only.
- Reading: the combined model's over-pricing of the safest 2024 decile is not visible in 2023 as a feature-level difference (the year, an overall shape, or chance). A Buhlmann-Straub correction (E26) was considered and not run: with between-level variance about zero in 2023 its credibility would be near 0 and reproduce E24, at the cost of a third use of 2024.
- For the report: protecting the safest decile costs about +0.027 buildings validation D2; the attempt to keep the gain found no basis in 2023.
- **E25 re-run (screen inside 2023 only, ridge-scale fixed, AI 113; cost-scale alpha 10):** selected wind_exposure_index +0.0028, wildfire_index +0.0023, new_business +0.0021, energy_rating +0.0020, smoke_alarms +0.0017 (CV D2 gains). The earlier 'no basis in 2023' is withdrawn. These five are now judged once on 2024 under the unchanged E25 rule; this is the third use of 2024 for the buildings combined question (E24, E25 first run, this run), disclosed before running.
- **E25 re-run result:** 2024 D2 0.0684 -> 0.0931 (+0.0247; combined alone 0.0950); lowest decile with the largest loss removed 0.515 -> 0.346 (0.17 further from 1; limit 0.1); top 0.889 -> 0.861. **Not adopted.** The five corrections recover little of the safest-decile gap: its cause is not these features. Fifth time the same direction (E17b, E18, E24, E25 twice): buildings other perils stay on emerging data only (final).

### Trend leverage restored for net amounts (Oct 24, notebook 28) — definition, not score
- Register (ASSUMPTIONS 4): trends apply to the ground-up loss with the excess fixed, so the net grows faster (leverage).
  With AMOUNTS_NET the excess was set to 0 and the trend multiplied the net amount: leverage lost.
- Fix (src/target.py): match_claims keeps the excess already deducted in the amounts (excess_in_amount); adjust_claims trends
  incurred + excess and deducts the excess again. Untrended amounts are unchanged; tied to AMOUNTS_NET (every entry point, developed table included).
- Effect measured on emerging training claims (trended totals): motor x1.017, buildings x1.006, contents x1.010.
  Frequency leverage (losses newly above the excess) is still not modelled; it would raise the level further.
- **p2_v7 (v6 + leverage) expected public, written before submitting: 0.1426-0.1440.** Adopted by definition; v7 becomes the final
  unless its public score is below 0.1420 (then look for a bug). New-business load unchanged (x1.3).
- Run: totals v7/v6 motor +1.17%, buildings +0.73%, contents +0.83% (all +1.03%), correlation >= 0.9999; tests passed.
- **p2_v7 public (Oct 24, 21:12): 0.14336**, inside 0.1426-0.1440; +0.0001 over v6. **p2_v7_leverage is the Part 2 final.**

### H2a: do new-business relativities differ from renewals? (Oct 24, notebook 28) — rule fixed before running
- Question behind the broker-book ranking hypothesis, tested where new business is plentiful: the developed market (2021-24). No emerging 2024 use.
- Base o: GLM on developed 2021-23, all rows (Part 1 GLM settings, the features shared with emerging), per line.
- For each feature: a one-feature correction on top of o (offset via y/o, weight w*sqrt(o); alpha 10), fitted on 2021-23 new-business rows,
  scored on 2024 new-business rows (out of time). Control: the same on renewal rows. Signal = new-business gain - renewal gain.
- Rule: any feature with signal >= +0.002 (any line) -> new-business relativities differ; candidate = new-business corrections for those
  features, tested once on the emerging 2024 fold under the GLM rule. All signals < +0.001 -> no support; the broker-book tilt probes (2b) are dropped.
  In between: recorded only.
- **H2a result (re-run after the ridge-scale fix, AI 113; cost-scale alpha 0.5):** renewal control -0.0004 to +0.0007 (instrument alive). Motor: no feature >= 0.002 (largest listed_building +0.0008): new-business relativities match renewals. Buildings: rainfall_mm +0.0057, flood_zone +0.0026. Contents: distance_to_river_km +0.0027, freezing_days +0.0024, energy_rating +0.0023, building_age +0.0021, voluntary_excess +0.0020. **Rule met (home lines): new-business relativities differ, mainly location and weather.**
- Caveats: about 120 feature tests (some may pass by chance; new-business 2024 sample about 28k rows per line); developed new business is not the broker book (indirect evidence).
- Next (E26, to be fixed before running): new-business corrections for these features, fitted on developed new business 2021-24 (offset on the developed base), applied to emerging new-business rows only with each line's new-business total held fixed. The emerging 2024 fold has too few new-business losses to judge (buildings 35, contents 64); adoption rule to be decided by the team.

### Ridge scale error in offset corrections (E21, E25, H2a) — found Oct 24, 21:17 (notebook 28) [AI 113]
- Corrections were fitted on y/o with weight w*sqrt(o). sklearn's penalty is on the weighted mean deviance, and Tweedie p=1.5 deviance scales
  with sqrt(amount), so alpha on this scale equals alpha on the cost scale times mean(sqrt(o)) (motor about 22, buildings about 17, contents about 9.5).
- Check (emerging motor 2023, one feature): driver_age_band spread at alpha 10 is 1.37 on the cost scale but 1.02 on the ratio scale.
- Affected: E21 (alpha 10 / 2), E25 (alpha 10), H2a (alpha 10): corrections were shrunk almost to zero (H2a's renewal control was exactly 0).
  Their conclusions are withdrawn. Fix: alpha_ratio = alpha_cost / weighted mean of sqrt(o). Same rules re-run; E25 uses 2024 a second time (disclosed).
- **E21 re-run:** (cost-scale alpha motor 10, contents 2, rescaled) motor D2 0.0373 -> 0.0360 (-0.0014), contents 0.0553 -> 0.0411 (-0.0142, top decile 0.97 -> 0.65): **not adopted.** Sensitivity: alpha x0.3 motor 0.0285, contents 0.0005; x3 motor 0.0378, contents 0.0537. The less shrinkage, the worse: one year of emerging data over-fits emerging-specific relativities. Market levels differ (motor frequency x1.35, severity x0.55) but the developed relativities transfer.

### Developed vs emerging, peril level, and the borrowed amount assumptions (Oct 24, 21:20, notebook 28)
- 2023 policy year (mature in both), net of excess and recoveries, no trend, uncapped; ratio emerging / developed:
  motor frequency x1.35, severity x0.55, cost x0.74 (BI severity x0.45, glass frequency x1.55); buildings x1.00 / x1.18 / x1.19
  (fire x3.0 = 2023 cluster; escape of water x0.45); contents x0.85 / x0.92 / x0.78. Emerging: more claims, cheaper claims (motor).
  Largest mix difference: channel (TVD 0.45). construction_type TVD 1.00 is the raw local codes (mapped in the pipeline).
- Checked because severity levels differ:
  1. Motor Pareto (borrowed alpha 2.05, threshold 100k): emerging has 3 claims > 100k, 8 > 55k; loading 0.02%-0.49% of the rate
     under any threshold / alpha (current 0.31%). No change.
  2. Caps: no emerging motor claim > 500k; contents uncapped; buildings 300k cuts one claim (-1.0%). No change.
  3. Severity trends (not testable; sensitivity for the report and the office premium table): all trends -2 / +2 points:
     motor -2.4% / +3.5%, buildings -1.8% / +3.0%, contents -3.4% / +3.4%.
  4. Fire: emerging 2024 severity 53,585 (median 28,466) and frequency 1.74 per 1,000 match developed 2021-24
     (50,509-54,347; 27,240-29,850; 1.68-2.06). The x1.3 severity is the 2023 cluster. Developed rate 97.05 kept.

### E26: new-business corrections for home lines from developed new business (Oct 24, notebook 28) — rule fixed before running (decided by Woojin)
- Features (passed H2a): buildings rainfall_mm, flood_zone; contents distance_to_river_km, freezing_days, energy_rating, building_age,
  voluntary_excess. Motor unchanged (H2a: no difference).
- Fit: developed base GLM on all developed rows 2021-24 (Part 1 settings); one correction GLM per line on developed new-business rows
  2021-24 (offset on the base; cost-scale alpha 0.5 converted to the ratio scale, AI 113).
- Apply: emerging new-business rows only; each line's new-business total held equal to v7 (the x1.3 load unchanged; ranking only);
  correction factors clipped to 0.67-1.5 (bands come from developed weather and location). Renewals unchanged.
- Emerging 2024 fold: direction check only (new-business losses: buildings 35, contents 64), not a decision input.
- Adoption (option a, team): adopted on the developed out-of-time evidence (H2a). The leaderboard is a guard only:
  p2_v8 is withdrawn (v7 stays final) if its public score is below v7 - 0.001 = 0.14236. **Expected public: 0.1433-0.1455.**
- Run: test new-business factors (after clipping) buildings p10/p50/p90 0.725 / 0.865 / 1.021, clipped 8.7%; contents 0.720 / 0.907 / 1.122, clipped 4.8%; totals by line equal to v7; correlation with v7 0.9947. Emerging 2024 (direction only): buildings new-business D2 -0.0220 -> -0.0158, contents 0.0222 -> 0.0212.
- **p2_v8 public (Oct 24, 21:35): 0.14077**, below the guard 0.14236 (-0.0026 vs v7). **Withdrawn; v7 stays final.** Developed new-business relativities do not carry to the broker book, or the developed weather bands do not transfer (buildings factors skewed, 8.7% clipped). The guard worked as intended.

### Diagnostic: actual 2025 weather (Oct 24, notebook 28) — written before submitting (decided by Woojin)
- p2_diag_weather_actual = v7 with weather_mode "actual" (training rows get their own year's weather, test rows 2025 weather); nothing else changed.
- Why: 2025 weather is unusual (freezing days 17 -> 29, hail days 17 -> 11); E19 found no gain in the 2024 fold (a normal year).
- Expected vs v7 (0.14336): >= +0.005 -> 2025 weather explains a large part of the gap to the leaders; within +-0.002 -> not the cause.
- **Diagnostic only: the final selection does not use 2025 weather** (unknown when pricing; Part 1 E4, E19). Reported as the gap that
  information unavailable at pricing time would close.
- Run: totals vs v7 motor 0.9998, buildings 0.9791, contents 0.9756; correlation 0.988-0.996.
- **p2_diag_weather_actual public (Oct 24, 21:37): 0.14399**, +0.0006 vs v7: within +-0.002, so 2025 weather is not the cause of the gap to the leaders. Not used for the final (v7 stays). Value of information unavailable at pricing time: about +0.0006 public.

### Model frozen at v7 (Oct 24, 21:45) — decided by Woojin
- Part 2 final: **p2_v7_leverage (public 0.14336)**. After 21:45 no model change unless a definition error is found (as the excess and leverage fixes).
- Tonight, not adopted: E14 (motor freq x sev), E24 / E25 (buildings combined), E21 re-run (emerging relativities), E26 / v8 (new-business
  corrections; withdrawn by the guard, public 0.14077); diagnostic only: actual 2025 weather (public 0.14399, +0.0006, not used).
- Remaining days: tests for the new target code, bootstrap interval for the new-business load, Part 2 column of the assumptions register,
  office premium table (Krista), report, video, reproducibility check from a fresh clone.

### Independent target audit (Oct 24, 22:37) — results/target_audit/ [AI 114]
- Fresh chat (Claude Opus 5.5): stage 1 designed the target from the Overview and Dataset Description only; stage 2 compared with src/target.py,
  config and DECISIONS; stage 3 checked exposure, frequency, severity, a step waterfall and year / market comparisons on the data (PDF, 14 pages).
- **Definition matches on every core step**, found blind: amounts already net of excess (not deducted again; closed claims under 100 CU exist at
  excess 1,000: motor 6.7%, buildings 8%), recoveries, declined claims, date-based exposure, row totals, trend on ground-up loss with the excess
  fixed. Check: sum(target)/sum(weight) from build_model_target equals the direct calculation (494.7 / 441.7 / 97.2); frequency x severity
  = cost per exposure at every step.
- New level items, all judgement and within +-1% per line, partly offsetting; **no model change** (v7 stays):
  BI completeness by count vs amount (0.545 vs 0.518): motor +0.6% to +1.0% under; BI reports after 730 days (developed 1.45%): motor +0.4%;
  subsidence completeness from 52 claims (0.753 vs developed 0.662): buildings +0.5% (sensitivity up to +5%); open-claim recoveries not
  reflected (known): motor -0.6%. Recorded as known limitations.
- Cost concentration: renewal_decision = declined_by_insurer rows are 0.1-0.5% of exposure but 22% / 51% / 21% of 2025-level cost
  (motor / buildings / contents); a marker after large claims, not a termination (75-95% of these policies are in the test). Not a feature
  (leakage); used in the report to explain Tweedie D2 volatility and the uncertainty of two training years.
- 2023 buildings fires rise each quarter (9, 12, 13, 15): a regional cluster building up, not one event.

### Murphy decomposition and bootstrap of the new-business load (Oct 24, 23:03, notebook 29) — results/bootstrap_murphy/
- 2024 validation rows rebuilt with the v7 structure (pooled D2 0.1081). Murphy decomposition of the Tweedie p=1.5 score (shares of the
  constant-model deviance; recalibration by weighted isotonic regression in-sample, so MCB is an upper bound):
  all rows D2 0.108 = DSC 0.117 - MCB 0.0085, of which one level factor removes 0.0000; new business D2 0.065 = DSC 0.090 - MCB 0.025;
  renewals D2 0.114 = DSC 0.124 - MCB 0.010. The level is right in validation; new business ranks less well (no claim history), which is
  76% of the test. Buildings / contents new-business MCB 0.079 / 0.072 on 35 / 64 losses: small-sample noise.
- Bootstrap of the Tweedie-optimal scale k* (2,000 random halves of the fold by policy, spread scaled to the test public size; public share
  unknown): new-business load 1.29 has a public-sampling 95% band of 1.19-1.39 (public 20%), 1.21-1.37 (30%), 1.23-1.35 (50%).
  x1.3 sits in the middle; tuning within 1.25-1.35 is below sampling noise. The band covers public sampling only, not whether the broker
  book is really 1.3x (that uncertainty is separate and larger). Approximation: validation rows scaled to test size.

### E27: collinear variable groups replaced by one variable (Oct 25, notebook 30) — rule fixed before running
- Diagnosis (no target used): VIF on numeric features (Oct 24, 02:25) mean_temperature_c 430-460, freezing_days 134-144, dry_summer_index
  88-93, wildfire_index 5.5; engine_size_cc ~ vehicle_value_group r 0.88; plus variable clustering and Belsley condition indices (notebook 30).
- Groups by reasoning: climate (mean_temperature_c, freezing_days, dry_summer_index, wildfire_index; all lines: address averages that
  measure how cold / dry a place is); vehicle size and value (engine_size_cc, vehicle_value_group; motor). Contents prem_rel ~ sum_insured
  (r 0.90) left out (E23 adopted yesterday; the insurer prices partly from the sum insured).
- Candidates: A = keep the group's most central variable (highest mean |r| with the others), drop the rest; B = replace the group by its
  first principal component (standardised, fitted on emerging training rows, same transform on the developed table and the test).
- Rule (Part 1 simplification rule), per line on the 2024 fold: adopt if D2 falls by no more than 0.0005 and neither tail decile A/E moves
  more than 0.1 further from 1. If A and B both pass, A (simpler). The model stays v7 unless a line passes.

- **E27 result (Oct 25, 12:43):** first component of the climate group explains 79% (central variable mean_temperature_c);
  vehicle group 94% (central engine_size_cc).
  | line | current | A (keep central) | B (first component) | verdict |
  | motor | 0.0373 (tails 0.80 / 0.89) | 0.0371 (0.79 / 0.88) | 0.0382 (0.74 / 0.94) | both pass -> A |
  | buildings | 0.0681 (0.58 / 1.02) | 0.0694 (0.57 / 1.01) | 0.0702 (0.53 / 1.02) | both pass -> A |
  | contents | 0.0550 (0.85 / 0.98) | 0.0558 (0.64 / 0.96) | 0.0563 (0.62 / 0.98) | both fail (lowest decile -0.21) -> keep |
  Contents: the climate variables separate the safest customers there; removing them moves the lowest decile 0.85 -> 0.64.
- **Decision (Woojin, Oct 25):** adopt A in motor and buildings as a simplification (7 fewer variables) under the rule fixed
  before the run. This overrides the Oct 24 freeze for this change only, with a guard. Dropped: motor freezing_days,
  dry_summer_index, wildfire_index, vehicle_value_group; buildings freezing_days, dry_summer_index, wildfire_index.
- **p2_v9 expected public, written before submitting: 0.1426-0.1442** (validation change about +0.0003 pooled; within public
  noise). **Guard: if public < 0.1420, v7 stays the final.** Pipeline validation must reproduce motor 0.0371 and buildings 0.0694.

- Pipeline validation reproduced the experiment: motor 0.0371, buildings 0.0694 (rule-b tails 0.571 / 1.013), contents 0.0550,
  pooled 0.1084. v9 vs v7 totals: motor +0.02%, buildings +0.07%, contents 0 (identical), all +0.03%; correlation motor 0.9974,
  buildings 0.9999; row changes (5-95%) motor -5.9% to +7.4%, buildings -2.5% to +2.5%.
- **p2_v9 public (Oct 25, 12:56): 0.14477**, +0.0014 vs v7; above the range written before submitting (0.1426-0.1442), most likely
  public noise on top of a small real gain (validation +0.0003 pooled). Guard passed. **p2_v9_e27_simplified is the Part 2 final.**
  Reported as: seven collinear variables removed without loss of accuracy, not as a score improvement.

## Assumptions register (status as of Oct 22, after E1–E11)
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
| Completeness (IBNR) | report-lag pattern from all 2021–24 losses (Lynden-Bell), count-based; in use from v10 | verified | Changes ≤ 0.3 points vs the 2021 pattern; reporting speed unchanged; amount-weighted differs by < 2% |
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
| Validation design | two out-of-time folds (2023 on 2021–22; 2024 on 2021–23) | verified | Of 15 submissions, 12 inside or within 0.00025 of the written range; it would have flagged E9 before submitting |
| Tweedie power for fitting | 1.5 (buildings) | resolved | Motor p = 1.4 not adopted (+0.0004, below threshold); motor now frequency x severity (E11) |
| Motor model structure | frequency (Poisson) x severity (Gamma) GLMs | verified | E11: D² +0.0025, both tails closer to 1, both folds; v12 0.12336 |
| Frequency and severity independent within customers | yes (motor) | verified (motor); **open** (buildings) | Claim size 2+ vs 1 claims: motor +1.1%, buildings +4.3% (685 rows) |
| Ridge strength and bands | motor α 0.5 / 10, buildings α 0.5 / 20, contents α 0.3 / 20 | verified | Grid on two validation years |
| Balance factor k | from training years | verified | Level holds in validation years |
| Claim history | same policy, 1 and 2 years, known by 1 Jan; unknown = missing | verified; **open** (2+ levels) | v4 +0.0011. No renewals under a new policy_id. 2+ past claims under-priced in v11 (A/E 1.25–3.26; ridge shrinkage, and possibly the Tweedie same-direction constraint: frequency ×3 but severity lower). Re-check under v12 |
| Weather for 2025 | average 2021–24 weather per address | verified | Validation within 0.001 of actual weather; leaderboard +0.0026 |
| written_premium | contents only, relative to the start month's average | judgement | +0.0010 D² in contents (+0.0003 more by month, Oct 21); circular (inherits the insurer's relativities) |
| customer_service_contacts | excluded | verified | Leakage: same-year correlation 12–72× next-year; test mean 0.40 vs train 0.67–0.75 |
| make_model | excluded | verified | +0.0001 D²; unstable between periods (0.15) |
| Marketing and branch fields | excluded | open | Expected small |
| Removed features | previous_insurer; occupation, region (home); discount_applied; home-type features in motor; duplicate tenure | verified | Stability checks and add/drop tests |
| GBM by line | contents only (3 seeds) | verified | Buildings GBM / blend over-price the safest decile (E8: 27%); team kept the GLM (Oct 22). Black boxes E9, E10 fail the rule in every line |
| Traceability tiers | GLM; single regularised GBM if it passes; stacks as benchmarks only | rule (Oct 22) | Fixed before the E10 results |

### Decision rules (fixed before results)
| For | Rule |
|---|---|
| GBM or blend | +0.003 average validation D² over the GLM; lowest and highest decile A/E no more than 0.1 further from 1 than the GLM's in each year |
| Final submission | traceability tiers (Oct 22): a combination of models with a neural network is a benchmark only |
| Experimental submission | run the out-of-time validation first (Oct 22, after E9) |
| Adding a feature / changing a GLM setting | +0.0005 D² and the tail condition |
| Removing a feature | removed unless D² falls by more than 0.0005 |
| Target assumptions (trends, factors) | model-free evidence, A/E toward 1 in both validation years, yearly levels more even |
| Leakage | information not known when pricing is excluded whatever its score |
| Choosing settings | on the held-out last training year only; validation years used once |
| Leaderboard | not used for decisions; expected change written before each submission; ±0.001 treated as noise |
