# IAA AI-Assisted Hackathon 2026

Predicting 2025 net claim cost per policy period for motor, buildings and contents.

## Layout
- `data/` – competition parquet files (not tracked; download from the competition page)
- `src/target.py` – loading, cleaning and target functions
- `notebooks/02_data_cleaning.ipynb` – data checks and analysis behind each decision
- `DECISIONS.md` – decision log with evidence

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy pyarrow jupyter
```
Put the parquet files in `data/`, then run the notebook from the `notebooks/` folder.
