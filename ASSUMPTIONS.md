# Assumptions: why we believe them

`DECISIONS.md` records what we decided and the evidence. This file records **why each assumption is
plausible** (the mechanism), **what the data shows**, and **what would prove it wrong**. A mechanism marked
*hypothesis* has not been tested on our data.

Groups follow the order of the pricing work: data → development → frequency on-levelling → severity
on-levelling → large losses → model and features.

---

## 1. Data and target definition

| Assumption | Why (mechanism) | What the data shows | Would be wrong if |
|---|---|---|---|
| One row_id = one priced period | A price is set per policy period; a mid-term change creates a new period with different rating factors | Consecutive periods 1 day apart; 99.7% of claims match one period | Claims regularly matched two periods |
| Excess on every peril | The excess is a contract term deducted from each claim, whatever the peril | Host answer (Oct 19) | — (confirmed) |
| Declined claims excluded | The insurer pays nothing on a repudiated claim | All repudiated amounts are zero | Repudiated claims carried payments |
| Exposure from dates | Cost per year needs one time unit; some rows used a 360-day year or days | 0.6% of rows inconsistent; fixed rows match dates | — |
| Duplicates removed | Same policy, peril, dates and amounts under two ids is a system error, not two losses | 600 of 604 in 2022 (one-off event) | Pairs differed in any claim detail |
| Sum insured acts as a limit | The contract pays up to the sum insured | Claims above it 0.02–0.03% of cost | Many claims well above sum insured |

## 2. Development (losses not yet fully known)

| Assumption | Why | What the data shows | Would be wrong if |
|---|---|---|---|
| Late-reported claims (IBNR) handled by completeness | At the valuation date, the latest year is missing claims that have happened but are not yet reported | Non-BI perils ≥ 94% reported in 2024; BI 56%; subsidence 69% | — |
| BI and subsidence report slowly | Injuries take time to be diagnosed and claimed, often through lawyers; subsidence cracks appear gradually | Longest report lags of all perils | — |
| Report-lag pattern (Lynden-Bell, all 2021–24 losses) | Reporting speed is a property of the peril and the claims process. Using 2021 losses only misses lags longer than each loss could be observed (right truncation); the Lynden-Bell estimator uses every loss with its own observation window | Changes completeness by at most 0.3 points (BI 2024 0.560 → 0.562); motor 2025 prediction −0.09%. BI reporting speed unchanged: reported within 90 days 44.3% / 44.9% / 46.6% (2021 / 22 / 23 Jan–Jun losses) | Reporting speed changes over time |
| Open-claim reserves not developed (IBNER) | One snapshot cannot show how reserves change | Sign test planned | Late-closing claims are much larger than open ones look |
| No recoveries on open claims | Recoveries (from third parties, salvage) arrive after payment, so open claims have none yet | Closed-claim rates imply −0.34% (2024 −1.6%) | — (a known small overstatement) |

## 3. On-levelling to 2025: frequency

| Assumption | Why | What the data shows | Would be wrong if |
|---|---|---|---|
| Own damage / third-party property: 2023 level shift | Something changed in 2023, at the same time as the BI change (*hypothesis:* road environment or claims handling); 2024 stays at the 2023 level, so a step, not a trend | Drop within every driver_assist and telematics group; completeness-adjusted 0.93 / 0.95 | A frequency GLM with a year factor shows no residual year effect (mix), or the repudiation rate changed in 2023 |
| Weather perils: no trend, weather as a feature | Subsidence, flood, storm and fire claims are caused by that year's weather; a rise that tracks the weather is not a trend | Subsidence rise tracks drier summers; strong frequency gradients by weather | A residual year effect remains after weather |
| Buildings fire, contents theft: no trend (open) | No known mechanism for a steady rise | +8% / +3% a year, not explained by weather | Year effect remains in a frequency GLM with all features |

## 4. On-levelling to 2025: severity

| Assumption | Why | What the data shows | Would be wrong if |
|---|---|---|---|
| Motor own damage +4%, third-party property +8% | Repair cost inflation: parts, paint, labour; modern cars cost more to repair | Steady rise in quarterly medians | Rise is a one-off step |
| Glass +8% | *Hypothesis:* windscreens with driver-assistance cameras need recalibration after replacement | Steady rise | — |
| Theft +3% (open) | Vehicle values rise | May be a 2023 step instead | Quarterly means show a step |
| Home trends (escape of water 8%, storm 8%, ...) | Building materials and trades labour inflation | Steady rise in quarterly medians | — |
| Trend on gross amounts, excess fixed | Inflation raises the ground-up loss; the excess is a fixed amount in the contract, so the net grows faster (leverage) | Net medians rise faster than gross (own damage 13% vs 4%) | — |
| BI 2023 change is a reform | A legal change to injury awards lowers costs from a date of loss | Step at 2023 Q1 by loss quarter, also in closed claims only (21.6k → 16.6k); Gamma GLM step 0.78–0.80 in every cohort | The step appears by report date or in reserves only (reserving change) |
| BI reform affects claims up to the 95th percentile equally | Simplification | 2023/2022 ratio net of trend 0.70–0.74 from the 25th to the 90th percentile; lowest decile 0.65; 99th percentile 1.01 (the largest claims are not affected) | — (flat factor acceptable for the attritional part; the tail is not reformed, which matters for the large-loss loading) |
| BI trend and reform: 0% trend, factor 0.83 (kept; main open assumption) | One year observed after the reform; the joint estimate is not stable | Joint Gamma fit (claims reported within 180 days): pre-reform trend 2.8% (5.5% and 7.2% in the 365- and 730-day cohorts: unstable), post-reform 8.6% on all claims but 1.2% on closed claims, so the post-reform rise comes from open-claim reserves. With the joint estimate, yearly levels spread 7.8% (vs 2.0%) and 2024 A/E falls to 0.97: not adopted. Sensitivity: motor 2025 prediction +5.1% | A stable trend appears once 2024 claims close |

## 5. Large losses

| Assumption | Why | What the data shows | Would be wrong if |
|---|---|---|---|
| Cap individual claims | A very large claim is mostly chance; left in, it makes its rating cell look risky and distorts relativities | 4 motor claims above 500k; one is 6% of BI cost | — |
| Pareto tail for the loading | Liability losses (serious injury) have a heavy tail; a fitted tail is more stable than the few observed large claims | Alpha 2.05; stable across thresholds (2.83–3.47) | Hill / mean-excess plot not linear above the threshold |
| Loading allocated in proportion to risk (motor) | *Hypothesis:* riskier policies have more large claims too | Better 2024 tails than flat | Large BI claims follow BI frequency (young drivers, mileage) rather than total rate |

## 6. Model and features

| Assumption | Why | What the data shows | Would be wrong if |
|---|---|---|---|
| Weather affects motor | *Hypotheses:* hail → glass and dents; freezing days → ice and skidding collisions; rainfall → wet roads, poor visibility, flood damage to cars; wind → falling objects | Not yet tested by motor peril | No gradient for the matching peril |
| Average weather, not actual 2025 | A price is set before the year, so only the location's climate is known; one year's weather at one address is noisy. *Hypothesis:* with four years, the yearly part of weather moves with the year and absorbs year-level differences left in the target (e.g. the BI trend), then carries them into 2025 | Validation: same accuracy; leaderboard v8 +0.0029; motor prediction +2.6%. 2025 weather is not extreme (0.3–3.7% of values outside the 2021–24 1–99% range), so extrapolation does not explain the gain | Motor weather relativities stay the same when a year factor is added |
| Claim history predicts claims | Past claims reveal risk we cannot see (driving style, property condition): experience rating | Rows with a past claim under-priced by 22–80% before the feature | Gradient disappears out of time |
| customer_service_contacts excluded | Contacts are generated by claims (reverse causation) | Same-year correlation 12–72× next-year; test mean 0.40 vs 0.67–0.75 | — |
| Relative premium (contents) | The insurer's price contains underwriting information we do not see | +0.0010 D²; circular (inherits the insurer's errors) | — (presented as a limitation) |
| Ridge shrinkage | Credibility: thinly populated levels shrink toward the average | Fixes over-steep lowest decile | — |
| Balance factor | Total expected cost must equal total predictions (pricing principle) | Out-of-sample A/E 0.99–1.02 | — |
| Tweedie p = 1.5 | Compound Poisson–gamma: claim count × claim size in one model; matches the scoring metric | p = 1.4 near-miss for motor | — |
| previous_insurer removed | *Hypothesis was* adverse selection from some insurers | Signal not stable between periods | — |
| occupation removed (home) | Mostly a proxy for age | η 0.62–0.65 with age; unstable | — |
