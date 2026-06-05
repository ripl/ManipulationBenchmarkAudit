# Data Source Dependency

## Purpose

This directory contains lightweight public evidence for the scripted-demo WidowX data-source-dependency diagnostic on the official SimplerEnv WidowX `4 x 24` grid.

## Contents

1. `configs/widowx_scripted_dsd_official_4x24.yaml`: sanitized policy recipe, task setup, dataset counts, and evaluation protocol.
2. `results/scripted_widowx/results.csv`: per-task success counts.
3. `results/scripted_widowx/trials.csv`: one row per official grid episode.
4. `results/scripted_widowx/aggregate_summary.json`: overall and per-task public summary.
5. `results/scripted_widowx/task_summaries/*.json`: per-task summary JSON files.

## Headline Result

The public files recompute stack `24/24`, carrot `23/24`, spoon `21/24`, eggplant `23/24`, and overall `91/96 = 94.79%`.

## Exclusions

Datasets, checkpoints, videos, full training/evaluation directories, caches, raw logs, and credential-bearing files are intentionally excluded.
