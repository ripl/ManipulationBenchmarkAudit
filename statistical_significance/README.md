# Statistical Significance

## Purpose

This directory contains the public-recomputed LIBERO Goal five-policy shared-instance outcome package and the aggregate leaderboard significance-category tables used for the statistical-significance diagnostic.

## Current Public Status

1. The package under `libero_goal_5x5k/` includes five per-policy `episodes_combined.csv` files, one `policy_summary.json` per policy, `policy_success_summary.csv`, `pairwise_disagreement.csv`, and shared init-state/config provenance.
2. The paper-facing LIBERO Goal calibration value is mean pairwise `D = 0.03528` and median `0.0354` across five `5k` shared-instance rollouts.
3. `libero_goal_pairwise_status.json` records that the claim is public-recomputed from release files and keeps the internal source pointer for provenance.
4. `code/significance_cutoffs.py` is Sam's reference implementation for aggregate-data necessary/sufficient cutoff calculations, copied from the supplementary bundle at commit `d81bb7bbd18cb420c2c712668a8ee99f4c9c6cd7`.
5. `code/generate_significance_categories.py` regenerates `significance_categories/` from the released Sam exports under `leaderboards/stat_significance_sam_export_20260522T233929/`.
6. `significance_categories/` contains one row per comparable previous-SOTA transition in `all_comparisons.csv`, the four category CSVs, `excluded_missing_scores.csv` for rows missing current or previous-SOTA scores, and `classification_parameters.csv` recording the benchmark-specific `T`, `S`, `R`, score unit, count-rounding method, and category counts.
7. Category logic is: `no_improvement` if the reported delta is `<= 0`; `provably_not_significant` if the improvement's count delta is below the necessary cutoff; `provably_significant` if it meets or exceeds the sufficient cutoff; otherwise `indeterminate`.
8. Reported aggregate scores are converted to counts with Python's nearest-even `round()` to match Sam's `significance_cutoffs.py`; the category CSVs include scaled-count and rounding-residual columns so non-integral reported scores are visible.

## Validation Behavior

`scripts/recompute_claims.py` verifies each policy has `5000` rows and the same unique shared `instance_id` set, compares `policy_success_summary.csv`, recomputes every pair in `pairwise_disagreement.csv` by joining outcomes on `instance_id`, and checks the mean and median `D` values.

`scripts/validate_release.py` regenerates the category CSVs from `code/generate_significance_categories.py`, checks that the category CSVs partition `all_comparisons.csv`, verifies declared category counts, and checks that each benchmark/track's categorized plus explicitly excluded rows matches the corresponding released Sam export. Validation compiles but does not import `code/significance_cutoffs.py`, because that reference file depends on scipy/numba.
