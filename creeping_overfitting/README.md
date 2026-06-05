# Creeping Overfitting

## Purpose

This directory contains lightweight public evidence for the creeping-overfitting diagnostic, covering distribution perturbation checks and fresh-test-sample checks.

## Contents

1. `results/simplerenv/fixed_grid_calibration/`: fixed-grid calibration per-episode rows, policy/task summaries, and validation report.
2. `results/simplerenv/distribution_overfitting/`: Protocol A-E per-episode rows, policy/condition summaries, test-set manifest, and validation report.
3. `results/calvin/`: CALVIN resampled-pose and fresh-sequence per-sequence rows, summary CSVs, confidence intervals, and combined summary JSON.
4. `results/libero/`: LIBERO Layer 2 fresh-init-state and selected official-calibration summary CSVs.
5. `configs/`: lightweight config/manifest-generation metadata retained for provenance.

## Notes

1. CALVIN fresh-sequence rows are included and recomputed here. Result provenance is verified at `Eval_Policies_CoRL` commit `eba7c0037294557427a7a854c91be56d3f2838ec`.
2. LIBERO Layer 2 is checked from released summary CSVs. Per-episode rollout rows are excluded to keep the public release small and credential-clean.
3. Binary reset banks, full manifests, raw logs, videos, checkpoints, datasets, caches, and environments are excluded.
