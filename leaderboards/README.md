# Leaderboard CSVs

## Purpose

This directory contains the public leaderboard CSV snapshots used by the paper's benchmark-coverage and statistical-significance analyses. It should contain this README and lightweight CSV exports only, not raw audit folders, caches, downloaded papers, model weights, or private workspaces.

## Source

These files were copied from `/home/ripl/workspace/leaderboards` at git commit `725613ff4e10f2725de3ac4ebcdbff28fc39586b`.

## Contents

1. `libero/`, `calvin/`, `simplerenv/`, `robocasa/`, and `robotwin2_0/`: five main benchmark citation trackers.
2. `others/`: four supplementary benchmark trackers used for the broader leaderboard/source-coverage audit: LIBERO-Plus, LIBERO-Pro, The Colosseum, and VLABench.
3. `stat_significance_sam_export_20260522T233929/`: five official-protocol previous-SOTA exports used to derive the aggregate-data significance category tables.

## Exclusions

The release intentionally excludes the rest of the leaderboard repository, including raw scrape outputs, paper caches, scripts, zips, full audit scratch data, and any non-CSV artifacts.
