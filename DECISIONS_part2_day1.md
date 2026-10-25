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
  - **Decision:** sum_insured above 100× the line's median is divided by 1000 (train and test). Contents
    rows at 5–10× the median (17) are below the gap and kept as real.
- **renewal_count is consistent, not an error.** Train mean 6.8 in a market written since 2023, but it is 0
  for every new-business row and ≥ 1 for every renewal, rises by exactly 1 for every policy from 2023 to
  2024, and 47% of customers have customer_since_year ≤ 2015 (tenure includes the relationship before the
  insurer entered the market). Kept.
- **written_premium is the annual premium, not the row's premium** (Part 1 as well). Median written premium
  is flat by start month (motor 500–525) while median exposure falls from 1.00 to 0.04.
  - **Decision (Part 2):** relative premium = written_premium ÷ that year's average, not divided by exposure.
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

### Decisions
- **gender:** used (allowed for pricing in this market, Dataset Description).
- **BI reform factor 0.83:** not applied. It is a developed-market legal change; the emerging data start in
  2023 and show no step to test.
- **Weather:** address average of 2023–24 (Part 1 E4 method). The Dataset Description lists emerging weather
  for 2023–24 only.

### To decide before any model result (with Krista)
1. **New business:** fit as a GLM factor; compare the fitted relativity with the age-standardised raw ratio
   and with the developed market's relativity under the same features; if they differ by more than two
   standard errors, use a credibility-weighted value. Proposed: no separate treatment for transferred vs
   organic new business, because they match on every observed variable.
2. **Validation:** one out-of-time fold (2023 → 2024). Report D² and A/E for 2024 new business separately
   (motor about 1,830 exposure, 382 claims) because it is 76% of the test.
3. **What is borrowed from the developed market:** severity trends (two years cannot estimate them), the
   Pareto tail shape, and relativities for small home lines as a credibility complement. Each borrowed item
   carries a "would be wrong if" line in the register.
4. **GBM / blend rule and tail rule for Part 2** (Part 1 cost about 0.002 on private).
