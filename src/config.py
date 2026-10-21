"""Market configuration: every number the pipeline uses, in one place.

PART1 reproduces the adopted model (v9, DECISIONS.md Oct 20). For Part 2, copy PART1, change the values
that the Day 1-2 checks re-estimate (docs/PART2_PLAYBOOK.md) and pass the new dict to the pipeline.
"""
import copy

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
    # large-loss loading added to the predicted rate
    #   pareto: fitted tail above `threshold`; `fixed` (if set) is used instead of the refit, so a
    #           submission can be reproduced exactly; allocated in proportion to the predicted rate
    #   observed: capped-off cost per weight from build_model_target, added flat
    "loading": {"motor": {"method": "pareto", "threshold": 100_000, "fixed": 2.83},
                "buildings": {"method": "observed"},
                "contents": {"method": "none"}},
    "folds": [(2023, [2021, 2022]), (2024, [2021, 2022, 2023])],
}
