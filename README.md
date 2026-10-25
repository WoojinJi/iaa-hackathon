# IAA AI-Assisted Hackathon 2026

Predicting the 2025 expected ultimate claim cost per policy period for motor, buildings and contents,
with an AI-assisted actuarial workflow.

## Repository layout
| Path | What it is |
|---|---|
| `data/` | Competition parquet files (not tracked; download from the competition page) |
| `src/target.py` | Loading, cleaning, matching claims to periods, and the 2025-level modelling target |
| `src/features.py` | Feature table (policy, customer, address, weather); excluded columns with reasons |
| `src/glm.py` | Banded Tweedie GLM |
| `src/evaluate.py` | Standard model checks (D², A/E, lift, segment flags) |
| `src/diagnostics.py` | Planted-error test: do our diagnostics tell assumption errors from model errors? |
| `tests/test_target.py` | Unit tests with hand-checked expected values |
| `notebooks/01_eda.ipynb` | Original exploration (kept as a record) |
| `notebooks/02_data_cleaning.ipynb` | Data checks and analysis behind each decision |
| `notebooks/03_frequency_mix.ipynb` | Motor frequency: portfolio mix check, motor modelling target |
| `notebooks/04_home_lines.ipynb` | Buildings and contents: development, trends, weather checks |
| `notebooks/05_baseline_glm.ipynb` | Baseline GLM: 2024 validation and first submission file |
| `notebooks/06_planted_error_test.ipynb` | Planted-error test of the diagnostics (motor) |
| `DECISIONS.md` | Decision log with evidence — **the current reference** |
| `AI_USE_LOG.md` | How AI was used and how each output was verified |
| `docs/` | Snapshot summaries (PDF, EN and KO). DECISIONS.md supersedes them where they differ |

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy pyarrow jupyter pytest scikit-learn matplotlib
```
Put the parquet files in `data/`, then run notebooks from the `notebooks/` folder.

## Reproduce the Part 2 final submission (v9, public 0.14477)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt          # exact environment used for the submissions
# competition data (not committed): Part 1 parquet files in data/, Part 2 in data_part2/emerging and data_part2/development
python -m src.pipeline --market part2 --out submissions/p2_v9_e27_simplified.csv
python -m src.pipeline --market part2 --validate   # out-of-time check: 2024 D2 motor 0.0371, buildings 0.0694, contents 0.0550
```
Settings live in `src/config.py` (`PART2`); every change and its evidence is in `DECISIONS.md`.
Checked on Oct 25 from a fresh clone: identical to the submitted file (max abs difference 0).

## Tests
```bash
pytest -v
```
Run from the repository root. The tests use small hand-made datasets, so the competition data is not needed.

| `src/history.py` | Claim-history features: claims known by 1 Jan of the policy year, same policy, previous 1 and 2 years (missing when not observable) |
| `tests/test_history.py` | Hand-checked tests for the history features |
| `notebooks/07_regularisation.ipynb` | Ridge strength and bands; balance correction |
| `notebooks/08_model_v2.ipynb` | GLM v2 fit and submissions; re-validation on the corrected target |
| `notebooks/09_lightgbm.ipynb` | LightGBM challenger; feature stability and association checks |
| `notebooks/10_claim_history.ipynb` | Model-free check of claim history against GLM v3 |
| `notebooks/11_history_model.ipynb` | GLM v4 (+ history), method B, GBM settings, calibration, v5 |
| `notebooks/12_limits_check.ipynb` | Policy limits and cover consistency |

## Working together
- Personal notebooks start with your name (e.g. `notebooks/krista_01_formula_check.ipynb`), so two people never edit the same file.
- `src/` is changed by one person; suggest changes through GitHub Issues.
- Questions go in Issues, one per question.
