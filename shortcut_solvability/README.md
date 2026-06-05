# Shortcut Solvability

## Purpose

This directory contains lightweight public evidence for the shortcut-solvability diagnostic: fixed-instruction DINO+MLP/task-id policies evaluated on LIBERO and CALVIN.

## Contents

1. `results/libero/results.csv`: LIBERO suite-level headline results.
2. `results/libero/best_checkpoint/*/{summary.json,trials.csv}`: compact per-suite summaries and per-trial outcomes.
3. `results/calvin/results.csv`: CALVIN headline results.
4. `results/calvin/best_checkpoint/*/{summary.json,trials.csv}`: compact per-split summaries and per-sequence outcomes.
5. `results/calvin/official_1000_eval_sequences.json`: CALVIN evaluation sequence list used by the included runs.
6. `configs/`: sanitized YAML configs for the included cells.

## Exclusions

Training/evaluation source code, checkpoints, datasets, logs, videos, and caches are intentionally not included in this minimal release package.
