# Public Claim Map

## Purpose

This file maps paper-facing manipulation benchmark audit claims to the lightweight public files in this repository. Claims are marked as public-recomputed when `scripts/recompute_claims.py` recomputes the number from included files; intentional exclusions are called out where they affect artifact scope.

## Shortcut Solvability

1. LIBERO fixed-instruction shortcut policy: public-recomputed from `shortcut_solvability/results/libero/results.csv` and `shortcut_solvability/results/libero/best_checkpoint/*/{summary.json,trials.csv}`. Headline cells are Spatial `495/500 = 99.0%`, Object `500/500 = 100.0%`, Goal `494/500 = 98.8%`, and Long `462/500 = 92.4%`.
2. CALVIN fixed-instruction shortcut policy: public-recomputed from `shortcut_solvability/results/calvin/results.csv` and `shortcut_solvability/results/calvin/best_checkpoint/*/{summary.json,trials.csv}`. Headline complete cells are `D->D` ATC `3.123` over `1000` sequences and `ABCD->D` ATC `3.872` over `1000` sequences. `ABC->D` ATC `3.242` is included as supporting evidence and remains labeled `no_full_official_artifact_manifest`.

## Statistical Significance

1. LIBERO Goal shared-instance pairwise disagreement: public-recomputed from `statistical_significance/libero_goal_5x5k/policy_success_summary.csv`, `pairwise_disagreement.csv`, `policies/*/{policy_summary.json,episodes_combined.csv}`, and `shared/{libero_config.yaml,init_state_goal_5000_MANIFEST.json}`. The released package verifies five policies with `5000` shared instance IDs each, then recomputes every joined policy pair. The paper-facing value is mean pairwise `D = 0.03528` and median `0.0354`.

## Creeping Overfitting

1. SimplerEnv fixed-grid calibration: public-recomputed from `creeping_overfitting/results/simplerenv/fixed_grid_calibration/per_episode_results_all.csv` and the summary CSVs. Aggregate policy rates are CogACT-Base `561/1152 = 48.70%`, SpatialVLA `432/1152 = 37.50%`, InternVLA-M1 `705/1152 = 61.20%`, X-VLA-WidowX `834/1152 = 72.40%`, and Dexbotic / DB-MemVLA `745/1152 = 64.67%`.
2. SimplerEnv Protocol A-E distribution-overfitting matrix: public-recomputed from `creeping_overfitting/results/simplerenv/distribution_overfitting/per_episode_results_all.csv` and the summary CSVs. Aggregate policy rates are CogACT-Base `230/2016 = 11.41%`, SpatialVLA `182/2016 = 9.03%`, InternVLA-M1 `287/2016 = 14.24%`, X-VLA-WidowX `1012/2016 = 50.20%`, and Dexbotic / DB-MemVLA `841/2016 = 41.72%`.
3. CALVIN Protocol 1 resampled-pose distribution-overfitting: public-recomputed from `creeping_overfitting/results/calvin/resampled_pose_per_sequence.csv`, `distribution_overfitting_summary.csv`, and `combined_summary.json`. ATC drops are X-VLA `1.027`, GR-1 `0.749`, and RoboFlamingo `0.498`.
4. CALVIN fresh-sequence sample-overfitting: public-recomputed from `creeping_overfitting/results/calvin/fresh_sequence_per_sequence.csv`, `fresh_sequence_summary.csv`, and `combined_summary.json`. Pooled ATC deltas versus matched calibration are X-VLA `-0.0145`, GR-1 `0.1070`, and RoboFlamingo `0.0690`, where positive means calibration scored higher. Result provenance is verified at `Eval_Policies_CoRL` commit `eba7c0037294557427a7a854c91be56d3f2838ec`.
5. LIBERO Layer 2 fresh-init-state summaries: public-recomputed from `creeping_overfitting/results/libero/fresh_init_state/*.csv`, `official_calibration/*.csv`, and `sample_overfitting_summary.csv`. Policy-level fresh rates are Spatial Forcing `9718/10000 = 97.18%`, SimVLA `9760/10000 = 97.60%`, and Pi05 / LeRobot `9741/10000 = 97.41%`. Per-episode rollout rows are excluded from this minimal package.

## Data Source Dependency

1. SimplerEnv WidowX scripted-demo DSD: public-recomputed from `data_source_dependency/results/scripted_widowx/trials.csv`, `results.csv`, and `aggregate_summary.json`. The result is stack `24/24`, carrot `23/24`, spoon `21/24`, eggplant `23/24`, and overall `91/96 = 94.79%`.
