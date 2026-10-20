# Part 2 playbook (written Oct 20, before seeing any Part 2 data)

Part 2 is an **emerging market** on a separate Kaggle page, with the same team. This file fixes, in
advance, how we will detect what changed and how we will respond, so the response is not fitted to the
data after seeing it. Every assumption in `ASSUMPTIONS.md` has a "would be wrong if" condition; this
playbook says how each is checked on the new data. Results go into the Part 2 column of the assumption
ledger (report section 2).

## Order of work
1. **Day 1 — look, do not model.** Run the checks below (schema, data quality, distributions, step scan,
   reporting delay). Read the competition overview and forum; ask the host early about anything that
   changes the target definition (excess, limits, currency, declined claims).
2. **Day 2 — target.** Re-estimate development, trends, steps and large losses with the same methods
   and rules as Part 1. Record each assumption as *held / broke / re-estimated*.
3. **Day 3 onward — model.** Start from the Part 1 configuration; change it only through the same rules
   (+0.0005 D² for a feature or setting, +0.003 and tails for GBM, leakage excluded regardless).
4. Before every submission: write the expected leaderboard change.

## Scenarios: detect → respond

| # | What may change | How we detect it | Pre-set response |
|---|---|---|---|
| 1 | **Columns, perils or lines differ** (new perils, missing fields, other names) | Schema diff against Part 1 (columns, types, peril list, value ranges) | Map names explicitly in one table; a peril without Part 1 equivalent gets its own trend and development, no borrowed assumption |
| 2 | **Target terms differ** (excess as % of claim, policy limits, currency, other declined statuses) | Overview, forum, and the same checks as Oct 16 (claims at or below excess, amounts at limits) | Ask the host before building the target; until answered, keep both readings and do not submit on either |
| 3 | **Worse data quality** (missing values, inconsistent exposure, duplicates, claims outside periods) | Re-run every Part 1 data-quality check unchanged (`src/target.py`, tests) | Same rules as Part 1; new kinds of error get a new check and a test before being fixed |
| 4 | **High inflation or a currency step** | Quarterly severity by peril; step scan (notebook 16) on loss date | Trend by peril from equal-maturity claims; a step is applied **from its break date, not from 1 January**; if inflation is high, trend measured quarterly |
| 5 | **A law or market change in mid-year** (reform, new compulsory cover, tax) | Step scan on three date bases: loss date / report date / policy start | Split at the break date found by the scan (`reform_date`, not `REFORM_YEAR`); confirm on closed claims; loss-date steps adjust the target, report-date steps do not |
| 6 | **Longer or changing reporting delays** | Lynden-Bell completeness by peril; reporting speed by loss half-year | Peril-level completeness from all years; if speed changed, estimate by period and record the limitation |
| 7 | **Different claims handling** (repudiation, recoveries, settlement speed) | Repudiation and recovery rates by report quarter (scan) | A handling step is not a frequency change: frequency measured on all reported claims including declined ones as a check |
| 8 | **A catastrophe or one-off event** (flood, storm, riot) | Claims concentrated in one month and region; scan; largest-loss share | Event claims capped or removed from relativities and priced as a separate loading; never drives rating factors |
| 9 | **Less history or smaller volume** | Years, rows and claims per peril | Stronger ridge and fewer bands chosen on the last training year; option: Part 1 relativities as the starting point the ridge shrinks toward (tested before adoption) |
| 10 | **Fast growth: mostly new business** | Share of rows with observable history | History features keep "unknown" as its own level; check A/E for new business separately (notebook 17 B) |
| 11 | **Weather or address data missing or different** | Coverage of weather per test address | Average past weather per address, as in Part 1; region average where an address has none |
| 12 | **A new leaking field** | Same-year vs next-year correlation test (notebook 12); train vs test distribution | Excluded whatever its score |
| 13 | **January or other cohort effects** | Policy-side scan with month-of-year effects | Not treated as a change |

## What we reuse unchanged
- Target formula, claim matching, exposure correction, duplicate rule.
- Validation design (out-of-time folds), all decision rules, the leaderboard prediction log.
- Tools: step scan (16), completeness (Lynden-Bell), timing test for leakage (12), segment A/E (17 B).

## What we expect to re-estimate
- Severity trends, frequency shifts, reform factors (if any), completeness, caps and large-loss loading,
  GLM ridge strength and bands.

## Code needed before Part 2 opens (Wednesday–Thursday)
- `pipeline.py` with a **market configuration** (dates, perils, caps, trends) instead of constants.
- `adjust_claims` takes a **break date** per peril, not a year.
- `checks.py`: schema diff, data-quality checks, step scan, completeness, timing test — one command, one report.
