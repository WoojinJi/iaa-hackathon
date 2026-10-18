# IAA AI-Assisted Hackathon 2026

Predicting 2025 net claim cost per policy period for motor, buildings and contents.

## Layout
- `data/` – competition parquet files (not tracked; download from the competition page)
- `src/target.py` – loading, cleaning and target functions
- `src/features.py` – feature table (policy, customer, address, weather); excluded columns with reasons
- `src/glm.py` – banded Tweedie GLM
- `src/evaluate.py` – standard model checks (D², A/E, lift, segment flags)
- `src/diagnostics.py` – planted-error test: do our diagnostics tell assumption errors from model errors?
- `notebooks/02_data_cleaning.ipynb` – data checks and analysis behind each decision
- `notebooks/05_baseline_glm.ipynb` – baseline GLM: 2024 validation and first submission
- `notebooks/06_planted_error_test.ipynb` – planted-error test of the diagnostics (motor)
- `tests/test_target.py` – unit tests with hand-checked expected values
- `DECISIONS.md` – decision log with evidence
- `AI_USE_LOG.md` – how AI was used and how each output was verified

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy pyarrow jupyter pytest scikit-learn matplotlib
```
Put the parquet files in `data/`, then run the notebook from the `notebooks/` folder.

## Tests
```bash
pytest -v
```
Run from the repository root. The tests use small hand-made datasets, so the competition data is not needed.
