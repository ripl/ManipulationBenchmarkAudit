# Statistical Significance

## Purpose

This directory contains the public-recomputed LIBERO Goal five-policy shared-instance outcome package used for the statistical-significance diagnostic.

## Current Public Status

1. The package under `libero_goal_5x5k/` includes five per-policy `episodes_combined.csv` files, one `policy_summary.json` per policy, `policy_success_summary.csv`, `pairwise_disagreement.csv`, and shared init-state/config provenance.
2. The paper-facing LIBERO Goal calibration value is mean pairwise `D = 0.03528` and median `0.0354` across five `5k` shared-instance rollouts.
3. `libero_goal_pairwise_status.json` records that the claim is public-recomputed from release files and keeps the internal source pointer for provenance.

## Validation Behavior

`scripts/recompute_claims.py` verifies each policy has `5000` rows and the same unique shared `instance_id` set, compares `policy_success_summary.csv`, recomputes every pair in `pairwise_disagreement.csv` by joining outcomes on `instance_id`, and checks the mean and median `D` values.
