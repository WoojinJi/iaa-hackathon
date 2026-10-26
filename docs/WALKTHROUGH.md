# Pricing walkthrough (Part 2): how to run it and what it means

`tools/walkthrough_p2.py` walks through the pricing process for the emerging market one step at a time and saves one figure
and a few numbers per step. It was written on Oct 26 for the team discussion (Woojin and Krista) and as material for the
report. **It is not part of the submission:** the submission is made by `python -m src.pipeline --market part2` (README).

## Why it exists
1. **To see the process, not just the score.** Each step answers one question (what is a row's exposure? what is the claim
   amount? how complete is 2024? ...) with one figure.
2. **As a second check of the target steps.** Every number is re-computed from the raw data with the same functions the
   pipeline uses (`src/target.py`), step by step, instead of in one call. If a number here disagrees with DECISIONS.md, one of
   the two is wrong.
3. **As a discussion tool.** The PDF "Pricing walkthrough for Krista" (Oct 26) is built from these figures, one page per step.

## How to run
Terminal (repository root, 1-2 minutes, no model fitting):
```bash
source .venv/bin/activate
python tools/walkthrough_p2.py
```
Notebook (`notebooks/32_pricing_walkthrough.ipynb`), one cell per step:
```python
import os, sys; from pathlib import Path; os.chdir(Path.home()/"IAA"); sys.path.insert(0, str(Path.home()/"IAA")); sys.path.insert(0, str(Path.home()/"IAA"/"tools"))
import walkthrough_p2 as W
claims, pol = W.load()          # policies (sum_insured x1000 fix applied) and claims, amounts net of excess
W.step2(claims, pol)            # then look at results/walkthrough/step2_excess.png; numbers in W.NUM["step2"]
```
Step 11 needs `results/office_premium_v9/reference_20_decomposed.csv` (the decomposition cell in notebook 31).

Output: `results/walkthrough/` (not committed): `stepN_*.png`, `step6_freq_sev.csv`, `numbers.json` (all numbers).

## The steps
| Step | Function | Question | What it computes | Expected (checked Oct 26) |
|---|---|---|---|---|
| 0 | — | What do we predict? | Definition only: expected claim cost per 2025 policy row (risk premium) | — |
| 1 | `step1` | Can we trust the exposure column? | Total exposure as given vs re-computed from the period dates; rows with a wrong value; claims matched to a row | About 0.5% of rows wrong, total inflated by about 40%; 99.6-99.7% of claims matched |
| 2 | `step2` | Is the excess already out of the amounts? | Raw cost per exposure with the excess deducted again (wrong, Oct 16-24) vs amounts as recorded (net) | Correct / wrong = 1.20 motor, 1.05 buildings, 1.19 contents |
| 3 | `step3` | How much of 2024 is reported yet? | Completeness by year (Lynden-Bell); motor 2024 completeness of each row by start month (E22) | Motor 2024 0.806; January rows 0.81, December rows 0.33; new business 0.745 vs renewals 0.812 |
| 4 | `step4` | What do past claims cost at 2025 prices? | Capped cost per exposure without trend, trend on the net amount, trend on the ground-up loss with the excess fixed (leverage, used) | Trend +8.3% / +6.8% / +7.3%; leverage +1.7% / +0.6% / +1.0% on top |
| 5 | `step5` | Is a large loss risk or bad luck? | Buildings fire claims by year; claims above the caps; the 30 largest claims per line | Fire 49 (2023) vs 21 (2024); developed flat rate 97.05 used |
| 6 | `step6` | More claims, or bigger claims? | Frequency per 1,000 exposure and mean severity by line, peril and year | `step6_freq_sev.csv` |
| 7 | — (notebook 31) | Where do the rating factors come from? | Relativities of the final model | `docs/figs/fig_relativities_v9.png` |
| 8 | — (notebook 31) | Does the model rank customers correctly? | A/E by predicted-rate decile, 2024 validation | `docs/figs/fig_deciles_v9.png` |
| 9 | `step9` | How is the 2025 test different? | New-business and broker shares: 2023, 2024, 2025 test | New business 6-9% before, 77% in the test; broker share about 70% throughout |
| 10 | — (notebook 31) | Did the written predictions hold? | Expected range vs public score per submission | `docs/figs/fig_submission_history.png`; 6 of 9 inside |
| 11 | `step11` | Why is the office premium 2-6x the current premium? | Office / current = (risk / current) x (office / risk) for the 20 reference policies | Buildings 7/7 and motor 6/7: risk alone above the current premium; contents 5/6: expenses |

## Limits
- Steps 1-6 and 9 work on the training rows of the emerging market before the model; they explain the target, not the
  predictions. Steps 7, 8 and 10 need model fits and reuse notebook 31's figures.
- Numbers in step 2 are raw (no trend, no cap); in step 4 they are capped and trended, so the two levels differ by design.
