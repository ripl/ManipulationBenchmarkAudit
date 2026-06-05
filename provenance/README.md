# Public Provenance

## Purpose

This directory records public-safe provenance for the released benchmark-audit artifacts. Put environment/package identity, checkpoint identity, and explicit unknown/best-effort caveats here. Do not put binary model weights, datasets, caches, containers, or full environment exports in this directory.

## Files

1. `environment_manifest.csv`: per-diagnostic package and runtime provenance. Exact historical package versions are marked `unknown` when no first-hand release evidence preserved them.
2. `checkpoint_identity_manifest.csv`: one public-safe checkpoint or model-file identity row per result-producing file when recoverable. Binary payloads are excluded; file sizes and SHA256 hashes are recorded only when first-hand evidence preserved them or the exact file was available to hash.

## Caveats

1. This is a best-effort public provenance layer over the existing lightweight release package.
2. Many historical runs preserved result rows, configs, and summaries but not `pip freeze`, conda lockfiles, container digests, or local checkpoint payloads in the public package.
3. `unknown` values are intentional. They mean the release did not contain first-hand evidence for that exact field.
