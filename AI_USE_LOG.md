# AI Use and Verification Log

How AI was used in the workflow, how each AI output was checked, and what changed as a result.
Every AI suggestion was treated as a hypothesis until verified against the data or the competition
documentation. Entries link to `DECISIONS.md` and notebook sections.

**Types**
- **A** – AI proposed; verified by the team with data
- **H** – Team member questioned or challenged; AI analysis followed
- **E** – AI error, caught by review or a sanity check

---

## Oct 16 — Target definition

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 1 | A | AI raised that deducting excess before or after recoveries could change the target. | Computed both orders on all motor claims. | Totals identical; kept excess-first. Logged in DECISIONS.md. |
| 2 | A | AI reviewed the written notes and found the target formula missing the final floor at 0 (recoveries could make it negative). | Compared the note with the code. | Code was correct; the note was fixed. |

## Oct 17 — Assumption review

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 3 | H | Asked whether new business and renewals should be treated differently, since they carry different information. | Checked the schema. | `new_business` and `renewal_count` exist in train and test; handled as features, with history features restricted to claims reported before the period starts. |
| 4 | H | Asked whether period boundaries are currently inclusive. AI stated it could not tell from the log. | Measured the gap between consecutive periods of each policy. | All gaps are exactly 1 day, so both ends are inclusive and no loss date can match two periods. |
| 5 | H | Asked why zero-cost repudiated claims can be dropped while withdrawn or nil claims might be treated differently. | Listed claim statuses in the data. | Only closed, open and repudiated exist; AI's mention of withdrawn/nil had been hypothetical. Frequency defined on positive net cost; zero-cost claims kept for history features. |
| 6 | H | Asked where "the competition target excludes declined claims" came from. AI could not trace a source. | Searched the data files (no documentation in the parquet metadata), later the competition page. | Evidence first rewritten as "amounts are zero, so no effect on the target"; later confirmed by the competition description. |

## Oct 17 — Data quality

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 7 | E | AI-written code converted every column ending in `_date` to datetime, including the amount columns `paid_to_date` and `incurred_to_date`. | Output showed amounts as 1970 timestamps, which is implausible; the cause was traced to the conversion loop. | Fixed to convert only `loss_date` and `report_date`; the fix is now in `load_claims()`. |
| 8 | A | AI noticed exposure with maximum 365 and standard deviation 9.6 in a summary table. | Classified every row against days / 365 in train and test, all lines. | 0.5% of rows on a 360-day basis and 0.1% in days; corrected. Total exposure fell 25–28%; test unaffected. |
| 9 | A | During a manual check of `build_target` (requested to verify the function on buildings and contents), AI noticed identical claims appearing twice in the same row. | Searched for claims identical on all fields except `claim_id`; checked spread by year and ambiguous near-duplicates. | 604 duplicates, 600 in loss year 2022; removed. The function itself was correct; the check surfaced a data issue. |
| 10 | A | AI proposed that motor excess may not apply to liability perils (UK practice). | Computed the target both ways; checked the competition description. | Motor differs by 4.6%. Documentation says only "net of the policy excess". **Still an assumption**: to be raised on the Kaggle forum and tested on the leaderboard. |

## Oct 17 — Development and trends

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 11 | A | AI attributed the 2024 motor drop to immaturity of bodily injury. | Reporting-delay completeness by peril; compared non-BI perils across years. | Confirmed for 2024: non-BI perils are near complete and in line with earlier years. |
| 12 | A | After the completeness adjustment, BI 2023–24 stayed about 20% below 2021–22. AI proposed two explanations: late-reported claims are larger, or open-claim reserves are too low. | Average cost by report-lag bucket; count- vs amount-weighted completeness; severity of open vs closed claims. | **Both rejected**: lag effect under 2%; open and closed severity similar. |
| 13 | A | Frequency was stable, so AI proposed a real BI severity change in 2023. | Quarterly severity; claims reported within 365 days only; other perils for comparison. | Step at 2023 Q1 (mean −19%, median −25%), BI only. Treated as a reform; pre-2023 BI on-levelled by 0.83. |
| 14 | H | AI recommended capping large claims and spreading the excess as a loading. Asked whether that is the only method. | AI listed alternatives (segment loading, separate large-loss model, no cap) and noted the choice depends on the evaluation metric. | Kept cap at 500k + loading; metric later confirmed as Tweedie D², which is evaluated on uncapped actuals, so the loading must be added back. |
| 15 | A | AI first measured severity trends on net-of-excess medians (own_damage +13% a year). | Re-measured gross of excess. | Gross trend is +4%; the gap is the fixed-excess leverage effect. Trends now applied to gross amounts. |
| 16 | A | AI proposed that the 2023 frequency drop in own_damage and third_party_prop was portfolio mix. | Mix by year (driver_assist, telematics, new business, cover type); frequency within each group. | **Rejected**: the drop appears within every group. Treated as a 2023 level shift (0.93 / 0.95). |

## Oct 17 — Final check of the motor target

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 17 | A | All adjustments combined into `build_model_target()`. | If the adjustments are right, cost per weighted exposure should be equal across years. | 550.8 / 548.4 / 551.0 / 540.0: consistent within about 2%. |
| 18 | — | Notebook reorganised by AI from the working notebook (errored cells removed). | Ran the cleaned notebook on the real data and compared every key figure with the original results. | All figures matched. |

## Oct 17 — Automated tests

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 19 | A | AI wrote 17 unit tests for `src/target.py` on tiny datasets, with the hand calculation written next to each expected value. | Each expected value reviewed by hand by the team; tests run with `pytest`. | 16 passed first time. One failed because **AI's expected value was wrong**: 2024 completeness is 365/366, not 1, since the valuation date (2024-12-30) is before Dec 31. The code was right; the expectation was corrected. |

## Oct 18 — Buildings and contents adjustments

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 20 | H | AI classified home-line changes as "steady severity trend", "2023 step" or "weather-driven frequency". Asked what the criteria were. AI admitted these were judgments from three clues (year pattern, physical cause, frequency vs severity), not proof. | Quarterly median severity; frequency by weather quintile; average weather by year; 2025 weather availability. | Buildings severity confirmed as gradual (inflation). Weather explains subsidence, flood, storm and fire frequency across addresses (1.8x–3.1x); subsidence and flood year changes track weather, but **storm and fire year changes do not**. Fire left as an open issue. |
| 21 | H | Asked whether "steady trend" referred to frequency or severity. AI had mixed the two in its explanation. | Re-stated each judgment by component. | Clarified: step vs trend was judged on severity; weather on frequency. Same split as motor (BI severity step, own_damage frequency shift). |
| 22 | H | Asked why the buildings cap was 250,000. AI admitted it had picked the middle of three candidates, and that this was inconsistent with the motor rule (just above the 99.9th percentile). | Compared with the motor rule; considered whether large fire claims follow `sum_insured`. | Changed to 300,000 (same rule as motor); final cap level to be chosen by validation among none / rule / lower. |
| 23 | A | A new unit test failed: completeness crashed when a peril had no claims in the reference year; a warning showed 0/0 when a year had no claims. | Traced both to edge cases that could occur in the Week 2 data. | Both handled (completeness = 1 with no basis for a delay pattern); 21 tests pass without warnings. |
| 24 | H | Asked what we had assumed about frequency and severity. AI listed 21 assumptions, marking which were verified and which were judgments. | Each assumption traced to the analysis that supports it. | Surfaced two items not acted on before: **recoveries on open claims** (raised on Oct 17, then dropped) and the **BI reform factor applied uniformly** although the reform hit small claims harder (median −25% vs mean −19%). |
| 25 | E | While writing the data preparation summary, AI noticed motor theft severity (6.3k, 6.2k → 6.9k, 6.8k) looks like a 2023 step, not the 3% annual trend it had set. | Self-review of the summary table. | Logged as an open issue (quarterly check pending). |

## Oct 18 — Baseline GLM

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 26 | E | AI's notebook compared the unweighted mean predicted rate with the exposure-weighted training level, so motor looked 6% low. | Spotted when interpreting results: the two numbers were on different bases. | Comparison to be redone exposure-weighted. |
| 27 | A | Buildings over-predicted by 7% (A/E 0.933), concentrated in the highest-risk rows and driest quintile. AI proposed the cause: one completeness factor for the whole line, while subsidence (69% complete) is concentrated in those rows. | Hypothesis only. Test: does the problem disappear when validating on mature 2023? | Weakened. Validating on mature 2023 (notebook 05) shows the model over-steepens the dryness effect in both years, and in 2024 the over-prediction is spread across all dryness quintiles (0.90–1.00), not concentrated in the driest homes. More likely: over-spread weather relativities plus 2024 being the driest year. Plan changed to tune regularisation first; split subsidence only if the 2024 gap remains.
| 28 | H | Asked how to tell whether a validation miss comes from the frequency/severity assumptions or from the model. AI proposed that they leave different signatures: assumption errors shift a whole year's level; model errors distort differences between segments. | — | Four diagnostics defined (model-free target check, frequency/severity split, mature-year comparison, train vs validation and GLM vs LightGBM). |
| 29 | H | Asked how to verify AI's claim in entry 28 itself, rather than accept it. | Planted-error test (notebook 06, motor): four known assumption errors (own_damage trend, 2024 immaturity ignored, BI reform removed, frequency shift removed) and three known model errors (driver-age features removed, over-fitting, region removed), each validated on 2023 and 2024. | **AI's rule scored 3 of 7.** Two causes: (1) AI's level metric measured distance from A/E = 1, so errors that offset the baseline's own bias (A/E 1.04 / 1.02) looked like improvements; measured as change against the baseline, all four assumption errors are attributed correctly. (2) Model errors also shift the level when a removed feature's distribution changes between years (driver age moved 2024 A/E by 2.7%). The over-fitting case was too weak to test (980k rows). Model-free diagnostics were most reliable (6/7 each) and complementary; the mature-year comparison mistook two model errors for immaturity, so it is not used alone. Post-hoc observation, recorded as a hypothesis only: assumption errors moved A/E but not D², model errors lowered D². |
| 31 | E | The planted-error test exposed a design flaw in AI's own diagnostic code: a level metric based on distance from 1 instead of change against the baseline (see entry 29). Earlier, the frequency/severity check compared the maximum deviation of the whole table, which hid planted errors. | Found by running the test, first on synthetic data, then on real data. | Both fixed or documented. Also found: the frequency shift is applied as an amount factor, so diagnostics read it as a severity change (right side, wrong component). |
| 30 | H | Chose not to submit the baseline yet and to improve first; asked for an order of fixes. | AI linked each validation problem to a cause and a fix, ordered so that target issues are fixed before model tuning. | Plan: two validation years → long-tail peril split → regularisation → feature checks → LightGBM → submissions. |
| 32 | H | Asked exactly how the regularisation works. While answering, AI found that its earlier explanation ("shrinks relativities toward the average, like credibility") did not match the code: with one-hot drop="first", ridge shrinks each level toward an arbitrary first level, and results depend on which level is first. | Read the encoder and solver settings against the objective. | Fix planned: encode all levels (no reference) so ridge shrinks toward each feature's average; compare both encodings during alpha tuning. |

## Oct 19 — Regularisation and first submissions

| # | Type | What happened | How it was checked | Outcome |
|---|---|---|---|---|
| 33 | E | AI wrote the tie-break rule as "prefer the smaller alpha", contrary to the principle it had stated before the results ("prefer the simpler model", i.e. larger alpha). | Self-review when reading the results. | Corrected to the principle stated beforehand, not to the results. |
| 34 | A | AI noticed that stronger ridge also shifted the overall level (buildings A/E 1.00 → 1.08), because a log-link Tweedie GLM with p = 1.5 does not balance the training total. Proposed an off-balance factor estimated on training years only. | Re-ran the shortlist with and without the factor; unit tests for the factor (training total matches; relativities unchanged). | Balanced buildings A/E 0.99–1.02 in unseen years. Rankings changed little. Showed most of the motor under-prediction is target-side. |
| 35 | H | Asked whether rebalancing after shrinking relativities is artificial. | AI separated what the factor does (re-estimates the intercept only) from its limits (can hide misfit; leaves segment bias). | Kept, with the condition that tails are checked after balancing. |
| 36 | E | AI proposed a limit of 3% on k without evidence; every buildings config exceeded it, although balanced validation A/E was close to 1. | Compared k with balanced validation A/E. | Replaced (after seeing results, recorded as such) by the out-of-sample check: balanced validation A/E near 1. |
| 37 | E | AI's pre-submission check compared the 2025 predicted level with the all-year training average and flagged motor at −7%. | Predicted level by year and by feature with the same model. | Against 2024 the drop is 4.6%, continuing a 2021–24 trend; explained by 2025 weather, vehicle age and NCB. Check fixed to compare with the latest year. |
| 38 | H | Asked whether D² of 0.12 is low (expected 0.7–0.8). | AI explained the ceiling: row-level losses are mostly process variance. | Leaderboard top 10 are 0.125–0.130; scores are compared with each other, not with R² norms. |
| 39 | H | Asked the host on the Kaggle forum instead of relying on the leaderboard test of the excess assumption. | Host answer compared with the leaderboard result. | Host: excess applies to every peril. The leaderboard had favoured the wrong reading by 0.0008, within the noise range fixed beforehand. Rule kept: documentation and host answers override the public leaderboard. |
| 40 | E | AI did not propose checking associations between features before modelling. Found later: renewal_count and customer_tenure are identical (Spearman 1.00), driver_age and years_licensed nearly so (0.99), region largely determines the weather features (eta 0.83–0.94), occupation partly proxies age (eta 0.62–0.65). | Association matrix (Spearman, Cramer's V, eta) on a 200k sample per line. | Duplicate dropped. Association and stability checks to become a reusable step before modelling (for the Week 2 data). |
| 41 | E | AI proposed on Oct 17 that excess does not apply to liability perils (bodily_injury, third_party_prop), based on UK practice. The data could not settle it; the team kept it as a stated assumption and asked the host (entry 10). | Host answer on the Kaggle forum (Oct 19): "Policy Excess applies to every peril." | **AI's assumption was wrong.** Default changed in `src/target.py`; five test expectations recalculated by hand; every downstream step reviewed (see DECISIONS.md, Oct 19, "Excess correction"). Lesson: an assumption borrowed from domain practice is still an assumption; asking the source was faster and more reliable than the leaderboard (entry 39). |
| 42 | E | AI's first re-check of the 2023 frequency shift (09f) counted only claims with net > 0. That mixes the fixed-excess effect into frequency (zero-net share falls from 32% to 28% for own_damage, 2021–24), so it suggested own_damage 0.967 vs the assumed 0.93 and a BI decline: a false alarm. | Re-measured with three definitions side by side; traced the original 0.93 to notebook 03 (all claims, no completeness adjustment, effectively 2023 only). | With the consistent definition (all claims, completeness-adjusted): own_damage 0.929 / 0.934, so 0.93 is confirmed; BI no adjustment. New finding: glass_hail frequency rises about 3% a year and is not adjusted (small effect on the motor level). third_party_prop (0.957 / 0.932) fell outside the ±0.02 tolerance of the rule; kept at 0.95 (two-year mean 0.945), decided after seeing results. |
| 43 | A | AI predicted the leaderboard change of two submissions from validation before submitting (v3 about +0.0005; experimental blend +0.002 to +0.003). | Submitted both. | Observed +0.0007 and +0.0032. Validation is a reliable guide. The blend was not adopted despite the higher score, because it fails the tail condition the leaderboard does not measure. |

---

## Lessons so far
- **Sanity checks on outputs caught AI code errors** (entry 7). Plausibility of numbers is checked before interpreting them.
- **Manual recalculation found a data issue the AI had not looked for** (entry 9).
- **About half of AI's explanations were rejected by data** (entries 12, 16). Hypotheses are tested, not accepted.
- **Where data cannot decide, the assumption is stated and its impact quantified** (entry 10).
- **Asking AI "what was your criterion?" exposed judgments presented as findings** (entries 20, 22). Each was then tested or made consistent.
- **AI's own diagnostic rules are tested before use** (entry 29), not only its numbers. The test showed AI's rule was half right and changed how we use the diagnostics.
- **Rules found after looking at a test result are kept as hypotheses** (entry 29), to avoid fitting the rule to the test.
- **Listing assumptions surfaced issues that had been raised and then forgotten** (entry 24).
