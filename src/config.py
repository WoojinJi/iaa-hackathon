"""Market configuration: every number the pipeline uses, in one place.

PART1 reproduces the adopted model (v11, DECISIONS.md Oct 21). For Part 2, copy PART1, change the values
that the Day 1-2 checks re-estimate (docs/PART2_PLAYBOOK.md) and pass the new dict to the pipeline.
"""
import copy

import pandas as pd

from .target import ADJ, DATA_DIR, LINES, VALUATION_DATE, YEARS

# Features removed from every model, with the reason (DECISIONS.md Oct 19).
DROP = {
    "motor": ["previous_insurer", "customer_tenure",            # unstable; duplicate of renewal_count
              "soil_type", "roof_type", "energy_rating", "building_age", "property_type", "bedrooms",
              "flood_zone", "elevation_m", "distance_to_river_km",   # home-type address features
              "discount_applied"],                                   # pricing policy, not risk
    "buildings": ["previous_insurer", "occupation", "region", "customer_tenure", "discount_applied"],
    "contents": ["previous_insurer", "occupation", "customer_tenure", "discount_applied"],
}

GBM_BASE = dict(objective="tweedie", tweedie_variance_power=1.5, metric="tweedie", learning_rate=0.03,
                num_leaves=31, min_data_in_leaf=500, feature_fraction=0.8, bagging_fraction=0.8,
                bagging_freq=1, lambda_l2=1.0, min_data_per_group=1000, cat_smooth=50, cat_l2=10,
                max_cat_threshold=8, verbose=-1, seed=42)

PART1 = {
    "name": "part1",
    "data_dir": DATA_DIR,
    "lines": list(LINES),
    "valuation_date": VALUATION_DATE,          # last report date in the claims data
    "years": list(YEARS),                      # training policy years
    "adj": copy.deepcopy(ADJ),                 # trends, reform factors and dates, frequency shifts, caps
    "completeness_method": "lynden_bell",      # v10: rule R1 (notebook 15); v9 used "ref_year"
    "weather_mode": "average",                 # address average 2021-24 (E4)
    "drop": DROP,
    "model": {"motor": "glm", "buildings": "glm", "contents": "gbm"},
    "glm": {"motor": dict(alpha=0.5, n_bands=10, drop=None, balance=True),
            "buildings": dict(alpha=0.5, n_bands=20, drop=None, balance=True),
            "contents": dict(alpha=0.3, n_bands=20, drop=None, balance=True)},
    "gbm": {"contents": dict(GBM_BASE, num_leaves=7, min_data_in_leaf=5000, lambda_l2=50)},
    "gbm_seeds": [42, 43, 44],
    "premium_lines": ["contents"],             # relative premium as a feature (E1)
    "premium_norm": "month",                   # v10: start-month average (mid-2021 rate step); v9 "year"
    # GLM interactions as coarse cross-classified factors (E7, Oct 21): selected by the procedure in
    # tools/exp_interactions.py (ranked by a depth-2 GBM on 2021-23, kept if D2 on 2024 rises >= 0.0003)
    "interactions": {"buildings": [("flood_zone", "sum_insured"), ("elevation_m", "flood_zone"),
                                   ("elevation_m", "sum_insured"), ("building_age", "flood_zone"),
                                   ("distance_to_river_km", "flood_zone")]},
    # large-loss loading added to the predicted rate
    #   pareto: fitted tail above `threshold`; `fixed` (if set) is used instead of the refit, so a
    #           submission can be reproduced exactly; allocated in proportion to the predicted rate
    #   observed: capped-off cost per weight from build_model_target, added flat
    "loading": {"motor": {"method": "pareto", "threshold": 100_000, "fixed": 2.83},
                "buildings": {"method": "observed"},
                "contents": {"method": "none"}},
    "folds": [(2023, [2021, 2022]), (2024, [2021, 2022, 2023])],
}


# ------------------------------------------------------------------ Part 2 (emerging market)
# Day 1 checks and team rules: DECISIONS.md Oct 23. Baseline = Part 1 structure with what the emerging data
# require; anything else is an experiment judged by the Part 1 rules.
PART2 = copy.deepcopy(PART1)
PART2.update({
    "name": "part2",
    "data_dir": DATA_DIR.parent / "data_part2" / "emerging",
    "years": [2023, 2024],
    "data_start": pd.Timestamp("2023-01-01"),  # history windows before this are not observable
    "hist": ["hist_1y"],                       # a 2-year window is never observable in training (2023 start)
    "fix_sum_insured": True,                   # x1000 entry error (Oct 23)
    "model": {"motor": "glm", "buildings": "glm", "contents": "glm"},   # rule 4: a GBM must pass the Part 1 rule here
    "premium_lines": [],                       # relative premium: an experiment in Part 2 (+0.0005 rule)
    "premium_norm": "annual",                  # written_premium is the full annual premium (Oct 23)
    "interactions": {},                        # Part 1 pairs were selected on developed data; re-select before use
    "loading": {"motor": {"method": "pareto", "threshold": 100_000, "alpha": 2.05},   # tail shape borrowed (rule 3)
                "buildings": {"method": "observed"},
                "contents": {"method": "none"}},
    "folds": [(2024, [2023])],                 # one out-of-time fold (rule 2)
})
PART2["adj"]["motor"]["reform"] = {}           # BI reform 0.83 is a developed-market change (Oct 23)
for _line in PART2["drop"]:                    # occupation is free text in the emerging market
    if "occupation" not in PART2["drop"][_line]:
        PART2["drop"][_line] = PART2["drop"][_line] + ["occupation"]

# Oct 23 afternoon (notebook 21_part2_baseline): ridge by CV inside the training year; buildings fire separate
PART2["glm"]["motor"]["alpha"] = 10
PART2["glm"]["buildings"]["alpha"] = 10
PART2["glm"]["contents"]["alpha"] = 2
PART2["peril_split"] = {"buildings": {"peril": "fire", "rate": "developed"}}   # or a number per exposure
PART2["loading"]["buildings"] = {"method": "none"}                              # fire rate is uncapped

# Oct 24 (E12 re-judged, notebook 23): buildings flood priced by its own GLM
PART2["peril_models"] = {"buildings": [{
    "peril": "flood", "alpha": 0.5,
    "features": ["flood_zone", "elevation_m", "distance_to_river_km", "rainfall_mm", "basement", "property_type",
                 "sum_insured", "building_age", "urban_density", "soil_type", "construction_type", "voluntary_excess"],
    "pairs": [["flood_zone", "sum_insured"], ["elevation_m", "flood_zone"], ["elevation_m", "sum_insured"],
              ["building_age", "flood_zone"], ["distance_to_river_km", "flood_zone"]]}]}

# Oct 24 (E17, notebook 23): developed data as training data (v3)
PART2["construction_codes"] = {"BRK": "brick", "STN": "stone", "WOD": "timber", "MIX": "non-standard"}
PART2["developed_training"] = {"motor": "developed", "contents": "combined"}
PART2["peril_models"]["buildings"][0]["train"] = "combined"

MARKETS = {"part1": PART1, "part2": PART2}
