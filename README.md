# What Are We Actually Benchmarking in Robot Manipulation?

Public release package for the paper **"What Are We Actually Benchmarking in Robot Manipulation?"**

Project website: <https://ripl.github.io/manipulation_benchmark_audit/>

## Purpose

This repository contains lightweight public artifacts for the manipulation benchmark audit diagnostics. It is a curated release layer: CSV/JSON/YAML/MD result files, claim mappings, and lightweight support scripts, not a dump of internal training/evaluation workspaces.

## Layout

```text
.
├── shortcut_solvability/
├── statistical_significance/
├── creeping_overfitting/
├── data_source_dependency/
├── leaderboards/
├── provenance/
├── scripts/
├── CLAIMS.md
├── SHA256SUMS
├── public_manifest.json
├── LICENSE
└── README.md
```

## Included Diagnostics

1. `shortcut_solvability/`: LIBERO and CALVIN DINO+MLP/task-id shortcut-solvability summaries, configs, and compact per-trial/per-sequence outcomes.
2. `statistical_significance/`: LIBERO Goal five-policy `5k` shared-instance outcome rows, policy summaries, pairwise-disagreement summary, aggregate leaderboard significance-category CSVs, cutoff reference code, and shared init-state/config provenance.
3. `creeping_overfitting/`: SimplerEnv fixed-grid and Protocol A-E rows/summaries, CALVIN resampled-pose and fresh-sequence rows/summaries, and LIBERO Layer 2 summaries.
4. `data_source_dependency/`: scripted-demo WidowX data-source-dependency summaries and official `4 x 24` grid trial outcomes.
5. `leaderboards/`: copied public leaderboard CSV snapshots and the Sam official-protocol previous-SOTA exports used for the significance category tables.
6. `provenance/`: best-effort package/environment provenance and checkpoint identity manifests, with unrecoverable exact fields marked unknown.

## Exclusions

This release intentionally excludes model weights, datasets, rollout videos, full rollout directories, full observations, per-step action traces, simulator caches, conda environments, containers, raw logs, third-party source checkouts, Git metadata, browser state, credential files, and credential material. Checkpoint identity metadata is included without binary payloads. Private paths, hostnames, job IDs, and W&B links are not release blockers by policy if credential-clean, but this package keeps them minimal.

## Contact

For questions, please either post an issue to this repository or email Tianchong Jiang at <tianchongj@ttic.edu>.
