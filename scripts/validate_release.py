#!/usr/bin/env python3
"""Validate the public release package shape, parseability, claims, and hygiene."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REQUIRED_TOP_LEVEL = {
    "shortcut_solvability",
    "statistical_significance",
    "creeping_overfitting",
    "data_source_dependency",
    "leaderboards",
    "provenance",
    "scripts",
    "CLAIMS.md",
    "public_manifest.json",
    "README.md",
    "SHA256SUMS",
    "LICENSE",
}

REQUIRED_LEADERBOARD_FILES = {
    "README.md",
    "calvin/calvin_citation_tracker.csv",
    "libero/libero_citation_tracker.csv",
    "robocasa/robocasa_citation_tracker.csv",
    "robotwin2_0/robotwin2_0_citation_tracker.csv",
    "simplerenv/simplerenv_citation_tracker.csv",
    "others/libero_plus.csv",
    "others/libero_pro.csv",
    "others/the_colossem.csv",
    "others/vlabench.csv",
    "stat_significance_sam_export_20260522T233929/sam_calvin_abc_d_official_prev_sota.csv",
    "stat_significance_sam_export_20260522T233929/sam_libero_official_prev_sota.csv",
    "stat_significance_sam_export_20260522T233929/sam_robocasa_rss24_official_prev_sota.csv",
    "stat_significance_sam_export_20260522T233929/sam_robotwin2_randomized_augmented_official_prev_sota.csv",
    "stat_significance_sam_export_20260522T233929/sam_simplerenv_widowx_bridge_official_prev_sota.csv",
}

REQUIRED_SIGNIFICANCE_CATEGORY_FILES = {
    "all_comparisons.csv",
    "classification_parameters.csv",
    "excluded_missing_scores.csv",
    "indeterminate.csv",
    "no_improvement.csv",
    "provably_not_significant.csv",
    "provably_significant.csv",
}

SIGNIFICANCE_CATEGORIES = {
    "indeterminate",
    "no_improvement",
    "provably_not_significant",
    "provably_significant",
}
COUNT_ROUNDING_METHOD = "python_round_nearest_even_matches_significance_cutoffs"

EXPECTED_SIGNIFICANCE_PARAMS = {
    ("LIBERO", "spatial"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_libero_official_prev_sota.csv",
        "libero_spatial",
        "libero_spatial_prev_sota",
        "10",
        "50",
        "1",
        "percent",
    ),
    ("LIBERO", "object"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_libero_official_prev_sota.csv",
        "libero_object",
        "libero_object_prev_sota",
        "10",
        "50",
        "1",
        "percent",
    ),
    ("LIBERO", "goal"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_libero_official_prev_sota.csv",
        "libero_goal",
        "libero_goal_prev_sota",
        "10",
        "50",
        "1",
        "percent",
    ),
    ("LIBERO", "long10"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_libero_official_prev_sota.csv",
        "libero_long10",
        "libero_long10_prev_sota",
        "10",
        "50",
        "1",
        "percent",
    ),
    ("CALVIN", "abc_d_atc"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_calvin_abc_d_official_prev_sota.csv",
        "calvin_abc_d_atc",
        "calvin_abc_d_prev_sota_atc",
        "1",
        "1000",
        "5",
        "raw_atc",
    ),
    ("SimplerEnv", "widowx_bridge"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_simplerenv_widowx_bridge_official_prev_sota.csv",
        "simplerenv_widowx_bridge_success_rate",
        "simplerenv_widowx_bridge_prev_sota_success_rate",
        "1",
        "96",
        "1",
        "percent",
    ),
    ("RoboCasa", "rss24"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_robocasa_rss24_official_prev_sota.csv",
        "robocasa_rss24_success_rate",
        "robocasa_rss24_prev_sota_success_rate",
        "1",
        "1200",
        "1",
        "percent",
    ),
    ("RoboTwin2", "hard_randomized"): (
        "leaderboards/stat_significance_sam_export_20260522T233929/sam_robotwin2_randomized_augmented_official_prev_sota.csv",
        "robotwin2_hard_randomized_success_rate",
        "robotwin2_hard_randomized_50clean_500rand_prev_sota_success_rate",
        "1",
        "5000",
        "1",
        "percent",
    ),
}

ALLOWED_EXTENSIONS = {".csv", ".json", ".yaml", ".yml", ".md", ".py"}
ALLOWED_EXTENSIONLESS = {"LICENSE", "SHA256SUMS", ".gitignore"}
EXCLUDED_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bz2",
    ".ckpt",
    ".db",
    ".gz",
    ".h5",
    ".hdf5",
    ".log",
    ".mov",
    ".mp4",
    ".mkv",
    ".npy",
    ".npz",
    ".onnx",
    ".parquet",
    ".pickle",
    ".pkl",
    ".pth",
    ".pt",
    ".safetensors",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
}
EXCLUDED_PATH_PARTS = {
    ".aws",
    ".azure",
    ".cache",
    ".conda",
    ".docker",
    ".git",
    ".gnupg",
    ".ssh",
    "browser_state",
    "cache",
    "checkpoints",
    "conda_env",
    "cookies",
    "datasets",
    "envs",
    "third_party",
    "videos",
    "wandb",
    "weights",
}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"(?i)\bAuthorization\s*:\s*(Bearer|Basic)\s+\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._=-]{20,}"),
    re.compile(r"(?i)\bWANDB_API_KEY\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+=:-]{12,}"),
    re.compile(r"(?i)extra-index-url\s+\S*://[^/\s:]+:[^@\s]+@"),
    re.compile(r"\bX-Amz-Signature=[A-Fa-f0-9]{16,}\b"),
    re.compile(r"(?i)\b(password|api[_-]?key|secret|access[_-]?token|refresh[_-]?token)\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+=:-]{12,}"),
]
MAX_TEXT_FILE_BYTES = 5_000_000
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def iter_release_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if ".git" in rel_parts:
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def load_recompute_module(root: Path) -> Any:
    sys.dont_write_bytecode = True
    script = root / "scripts" / "recompute_claims.py"
    spec = importlib.util.spec_from_file_location("recompute_claims", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import scripts/recompute_claims.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_category_generator_module(root: Path) -> Any:
    sys.dont_write_bytecode = True
    script = root / "statistical_significance" / "code" / "generate_significance_categories.py"
    spec = importlib.util.spec_from_file_location("generate_significance_categories", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import statistical_significance/code/generate_significance_categories.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_shape(root: Path, errors: list[str]) -> None:
    present = {path.name for path in root.iterdir()}
    missing = sorted(REQUIRED_TOP_LEVEL - present)
    if missing:
        errors.append(f"missing required top-level entries: {missing}")
    for required_dir in [
        "shortcut_solvability",
        "statistical_significance",
        "creeping_overfitting",
        "data_source_dependency",
        "leaderboards",
        "provenance",
        "scripts",
    ]:
        if not (root / required_dir).is_dir():
            errors.append(f"required top-level directory missing: {required_dir}")


def validate_parseability(files: list[Path], root: Path, errors: list[str]) -> dict[str, int]:
    counts = {"csv": 0, "json": 0, "yaml": 0, "md": 0, "py": 0}
    for path in files:
        rel = path.relative_to(root)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open(newline="") as f:
                rows = list(csv.reader(f))
            if not rows:
                errors.append(f"empty CSV file: {rel}")
            counts["csv"] += 1
        elif suffix == ".json":
            with path.open() as f:
                json.load(f)
            counts["json"] += 1
        elif suffix in {".yaml", ".yml"}:
            text = path.read_text()
            if yaml is not None:
                yaml.safe_load(text)
            elif "\t" in text:
                errors.append(f"YAML file contains tab indentation and PyYAML is unavailable: {rel}")
            counts["yaml"] += 1
        elif suffix == ".md":
            if not path.read_text().strip():
                errors.append(f"empty Markdown file: {rel}")
            counts["md"] += 1
        elif suffix == ".py":
            compile(path.read_text(), str(path), "exec")
            counts["py"] += 1
    return counts


def validate_artifact_types(files: list[Path], root: Path, errors: list[str]) -> None:
    for path in files:
        rel = path.relative_to(root)
        suffix = path.suffix.lower()
        if suffix in EXCLUDED_EXTENSIONS:
            errors.append(f"excluded artifact extension present: {rel}")
        if suffix and suffix not in ALLOWED_EXTENSIONS:
            errors.append(f"unexpected file extension in release: {rel}")
        if not suffix and path.name not in ALLOWED_EXTENSIONLESS:
            errors.append(f"unexpected extensionless file in release: {rel}")
        if path.stat().st_size > MAX_TEXT_FILE_BYTES:
            errors.append(f"file exceeds lightweight size limit: {rel} ({path.stat().st_size} bytes)")
        lowered_parts = {part.lower() for part in rel.parts}
        blocked = sorted((lowered_parts & EXCLUDED_PATH_PARTS) - {".git"})
        if blocked:
            errors.append(f"excluded path component {blocked} present in {rel}")


def validate_credentials(files: list[Path], root: Path, errors: list[str]) -> None:
    risky_names = {
        ".netrc",
        "credentials",
        "credentials.json",
        "cookies.sqlite",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
    }
    for path in files:
        rel = path.relative_to(root)
        if path.name.lower() in risky_names:
            errors.append(f"credential-like file name present: {rel}")
            continue
        try:
            text = path.read_text(errors="ignore")
        except UnicodeDecodeError:
            errors.append(f"non-text file could not be scanned: {rel}")
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"high-risk credential pattern matched in {rel}: {pattern.pattern}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sha256sums(files: list[Path], root: Path, errors: list[str]) -> None:
    manifest_path = root / "SHA256SUMS"
    if not manifest_path.is_file():
        errors.append("missing required top-level SHA256SUMS")
        return

    expected_files = {
        path.relative_to(root).as_posix(): path
        for path in files
        if path.relative_to(root).as_posix() != "SHA256SUMS"
    }
    entries: dict[str, str] = {}
    for line_number, line in enumerate(manifest_path.read_text().splitlines(), start=1):
        if not line.strip():
            errors.append(f"SHA256SUMS line {line_number}: blank lines are not allowed")
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            errors.append(f"SHA256SUMS line {line_number}: expected '<sha256>  <relative_path>'")
            continue
        digest, rel = parts
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            errors.append(f"SHA256SUMS line {line_number}: invalid SHA256 digest")
        if rel.startswith("./") or Path(rel).is_absolute() or ".." in Path(rel).parts:
            errors.append(f"SHA256SUMS line {line_number}: path must be a repository-relative path without leading ./")
        if rel == "SHA256SUMS":
            errors.append("SHA256SUMS must not include itself")
        if rel in entries:
            errors.append(f"SHA256SUMS line {line_number}: duplicate path {rel}")
        entries[rel] = digest

    expected = set(expected_files)
    actual = set(entries)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"SHA256SUMS missing files: {missing}")
    if extra:
        errors.append(f"SHA256SUMS has extra files: {extra}")

    for rel in sorted(expected & actual):
        actual_digest = sha256_file(expected_files[rel])
        if actual_digest != entries[rel]:
            errors.append(f"SHA256SUMS mismatch for {rel}: expected {entries[rel]}, recomputed {actual_digest}")


def validate_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    manifest = json.loads((root / "public_manifest.json").read_text())
    groups = {group["directory"]: group for group in manifest.get("artifact_groups", [])}
    for required in ["shortcut_solvability", "statistical_significance", "creeping_overfitting", "data_source_dependency", "leaderboards", "provenance"]:
        if required not in groups:
            errors.append(f"public_manifest.json missing artifact group: {required}")
    if not manifest.get("source_candidates_used"):
        errors.append("public_manifest.json must record source candidates")
    return manifest


def read_dict_csv(path: Path, required_columns: set[str], label: str, errors: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        errors.append(f"missing {label}: {path}")
        return []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(required_columns - fieldnames)
        if missing:
            errors.append(f"{label} missing required columns: {missing}")
            return []
        rows = list(reader)
    if not rows:
        errors.append(f"{label} must contain at least one row")
    return rows


def validate_leaderboards(root: Path, errors: list[str]) -> None:
    leaderboard_dir = root / "leaderboards"
    if not leaderboard_dir.is_dir():
        errors.append("missing leaderboards directory")
        return

    actual = {
        path.relative_to(leaderboard_dir).as_posix()
        for path in leaderboard_dir.rglob("*")
        if path.is_file()
    }
    missing = sorted(REQUIRED_LEADERBOARD_FILES - actual)
    extra = sorted(actual - REQUIRED_LEADERBOARD_FILES)
    if missing:
        errors.append(f"leaderboards directory missing expected files: {missing}")
    if extra:
        errors.append(f"leaderboards directory contains files outside the approved copy set: {extra}")


def validate_significance_categories(root: Path, errors: list[str]) -> dict[str, Any]:
    category_dir = root / "statistical_significance" / "significance_categories"
    if not category_dir.is_dir():
        errors.append("missing statistical_significance/significance_categories directory")
        return {}

    actual = {path.name for path in category_dir.iterdir() if path.is_file()}
    missing = sorted(REQUIRED_SIGNIFICANCE_CATEGORY_FILES - actual)
    extra = sorted(actual - REQUIRED_SIGNIFICANCE_CATEGORY_FILES)
    if missing:
        errors.append(f"significance category directory missing expected files: {missing}")
    if extra:
        errors.append(f"significance category directory contains unexpected files: {extra}")

    category_columns = {
        "benchmark",
        "track",
        "paper_name",
        "source_csv",
        "source_line",
        "current_column",
        "previous_sota_column",
        "current_score",
        "previous_sota_score",
        "reported_delta",
        "score_unit",
        "previous_sota_scaled_count",
        "current_scaled_count",
        "previous_sota_count",
        "current_count",
        "previous_sota_rounding_residual",
        "current_rounding_residual",
        "count_rounding_method",
        "count_delta",
        "T",
        "S",
        "R",
        "alpha",
        "z_critical",
        "necessary_count_delta",
        "sufficient_count_delta",
        "necessary_score_delta",
        "sufficient_score_delta",
        "category",
        "notes",
    }
    parameter_columns = {
        "benchmark",
        "track",
        "source_csv",
        "current_column",
        "previous_sota_column",
        "T",
        "S",
        "R",
        "score_unit",
        "count_rounding_method",
        "alpha",
        "z_critical",
        "categorized_rows",
        "excluded_missing_score_rows",
        "no_improvement_rows",
        "provably_not_significant_rows",
        "provably_significant_rows",
        "indeterminate_rows",
        "notes",
    }
    exclusion_columns = {
        "benchmark",
        "track",
        "source_csv",
        "source_line",
        "current_column",
        "previous_sota_column",
        "exclusion_reason",
    }

    all_rows = read_dict_csv(category_dir / "all_comparisons.csv", category_columns, "all_comparisons.csv", errors)
    parameter_rows = read_dict_csv(category_dir / "classification_parameters.csv", parameter_columns, "classification_parameters.csv", errors)
    excluded_rows = read_dict_csv(category_dir / "excluded_missing_scores.csv", exclusion_columns, "excluded_missing_scores.csv", errors)

    def key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
        return (
            row["benchmark"],
            row["track"],
            row["source_csv"],
            row["source_line"],
            row["current_column"],
        )

    def parse_int(value: str, label: str) -> int | None:
        try:
            return int(value)
        except ValueError:
            errors.append(f"{label}: expected integer, got {value!r}")
            return None

    def parse_float(value: str, label: str) -> float | None:
        try:
            return float(value)
        except ValueError:
            errors.append(f"{label}: expected float, got {value!r}")
            return None

    def parse_optional_int(value: str, label: str) -> int | None:
        if value == "unknown":
            return None
        return parse_int(value, label)

    def expected_category(row: dict[str, str]) -> str | None:
        row_label = f"all_comparisons.csv {key(row)}"
        reported_delta = parse_float(row["reported_delta"], f"{row_label} reported_delta")
        count_delta = parse_int(row["count_delta"], f"{row_label} count_delta")
        necessary = parse_optional_int(row["necessary_count_delta"], f"{row_label} necessary_count_delta")
        sufficient = parse_optional_int(row["sufficient_count_delta"], f"{row_label} sufficient_count_delta")
        if reported_delta is None or count_delta is None:
            return None
        if reported_delta <= 0:
            return "no_improvement"
        if count_delta <= 0:
            return "provably_not_significant"
        if necessary is not None and count_delta < necessary:
            return "provably_not_significant"
        if sufficient is not None and count_delta >= sufficient:
            return "provably_significant"
        return "indeterminate"

    all_by_key: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    category_counts = {category: 0 for category in SIGNIFICANCE_CATEGORIES}
    for row in all_rows:
        row_key = key(row)
        if row_key in all_by_key:
            errors.append(f"duplicate all_comparisons row key: {row_key}")
        all_by_key[row_key] = row
        category = row["category"]
        if category not in SIGNIFICANCE_CATEGORIES:
            errors.append(f"unsupported significance category {category} in all_comparisons.csv")
            continue
        expected = expected_category(row)
        if expected is not None and category != expected:
            errors.append(f"all_comparisons.csv {row_key}: category {category} should be {expected}")
        if row["count_rounding_method"] != COUNT_ROUNDING_METHOD:
            errors.append(f"all_comparisons.csv {row_key}: unsupported count_rounding_method {row['count_rounding_method']!r}")
        category_counts[category] += 1

    for category in sorted(SIGNIFICANCE_CATEGORIES):
        rows = read_dict_csv(category_dir / f"{category}.csv", category_columns, f"{category}.csv", errors)
        row_keys = {key(row) for row in rows}
        expected_keys = {row_key for row_key, row in all_by_key.items() if row["category"] == category}
        if row_keys != expected_keys:
            errors.append(f"{category}.csv does not exactly partition all_comparisons.csv")
        for row in rows:
            if row["category"] != category:
                errors.append(f"{category}.csv contains row labelled {row['category']}")

    seen_params: set[tuple[str, str]] = set()
    for row in parameter_rows:
        label = f"classification_parameters.csv {row['benchmark']} {row['track']}"
        param_key = (row["benchmark"], row["track"])
        if param_key in seen_params:
            errors.append(f"duplicate classification parameter row: {param_key}")
        seen_params.add(param_key)
        if row["count_rounding_method"] != COUNT_ROUNDING_METHOD:
            errors.append(f"{label}: unsupported count_rounding_method {row['count_rounding_method']!r}")
        expected_params = EXPECTED_SIGNIFICANCE_PARAMS.get(param_key)
        if expected_params is None:
            errors.append(f"unexpected classification parameter row: {param_key}")
        else:
            observed_params = (
                row["source_csv"],
                row["current_column"],
                row["previous_sota_column"],
                row["T"],
                row["S"],
                row["R"],
                row["score_unit"],
            )
            if observed_params != expected_params:
                errors.append(f"{label}: expected params {expected_params}, got {observed_params}")
        source_rel = row["source_csv"]
        if Path(source_rel).is_absolute() or ".." in Path(source_rel).parts:
            errors.append(f"{label}: source_csv must be repository-relative without '..'")
            continue
        source_path = root / source_rel
        if not source_path.is_file():
            errors.append(f"{label}: source_csv does not exist: {source_rel}")
            continue

        with source_path.open(newline="") as f:
            source_reader = csv.DictReader(f)
            source_count = sum(1 for _ in source_reader)

        scoped_all = [
            candidate
            for candidate in all_rows
            if candidate["benchmark"] == row["benchmark"] and candidate["track"] == row["track"]
        ]
        scoped_excluded = [
            candidate
            for candidate in excluded_rows
            if candidate["benchmark"] == row["benchmark"] and candidate["track"] == row["track"]
        ]
        categorized = parse_int(row["categorized_rows"], f"{label} categorized_rows")
        excluded = parse_int(row["excluded_missing_score_rows"], f"{label} excluded_missing_score_rows")
        if categorized is not None and len(scoped_all) != categorized:
            errors.append(f"{label}: categorized_rows={categorized} but all_comparisons has {len(scoped_all)} rows")
        if excluded is not None and len(scoped_excluded) != excluded:
            errors.append(f"{label}: excluded_missing_score_rows={excluded} but excluded_missing_scores has {len(scoped_excluded)} rows")
        if categorized is not None and excluded is not None and categorized + excluded != source_count:
            errors.append(f"{label}: categorized+excluded={categorized + excluded} but source CSV has {source_count} rows")
        for category in sorted(SIGNIFICANCE_CATEGORIES):
            expected = parse_int(row[f"{category}_rows"], f"{label} {category}_rows")
            observed = sum(1 for candidate in scoped_all if candidate["category"] == category)
            if expected is not None and observed != expected:
                errors.append(f"{label}: {category}_rows={expected} but observed {observed}")

    missing_params = sorted(set(EXPECTED_SIGNIFICANCE_PARAMS) - seen_params)
    if missing_params:
        errors.append(f"classification_parameters.csv missing expected rows: {missing_params}")

    def compare_generated_rows(label: str, generated: list[dict[str, str]], actual_rows: list[dict[str, str]]) -> None:
        if generated == actual_rows:
            return
        errors.append(f"{label} does not match regenerated output from generate_significance_categories.py")
        if len(generated) != len(actual_rows):
            errors.append(f"{label}: regenerated {len(generated)} rows, file has {len(actual_rows)} rows")
            return
        for index, (expected_row, actual_row) in enumerate(zip(generated, actual_rows), start=2):
            if expected_row != actual_row:
                errors.append(f"{label} first mismatch at row {index}: regenerated {expected_row}, file has {actual_row}")
                return

    try:
        generator = load_category_generator_module(root)
        generated_all, generated_excluded, generated_params = generator.build_rows(root, 0.05)
        compare_generated_rows("all_comparisons.csv", generated_all, all_rows)
        compare_generated_rows("excluded_missing_scores.csv", generated_excluded, excluded_rows)
        compare_generated_rows("classification_parameters.csv", generated_params, parameter_rows)
        for category in sorted(SIGNIFICANCE_CATEGORIES):
            generated_category_rows = [row for row in generated_all if row["category"] == category]
            actual_category_rows = read_dict_csv(category_dir / f"{category}.csv", category_columns, f"{category}.csv", errors)
            compare_generated_rows(f"{category}.csv", generated_category_rows, actual_category_rows)
    except BaseException as exc:  # pragma: no cover - fail loudly in validation output
        errors.append(f"could not regenerate significance category CSVs: {type(exc).__name__}: {exc}")

    return {
        "all_comparisons": len(all_rows),
        "excluded_missing_scores": len(excluded_rows),
        "category_counts": category_counts,
        "parameter_rows": len(parameter_rows),
    }


def validate_provenance(root: Path, errors: list[str]) -> dict[str, Any]:
    provenance_dir = root / "provenance"
    env_path = provenance_dir / "environment_manifest.csv"
    checkpoint_path = provenance_dir / "checkpoint_identity_manifest.csv"
    env_rows: list[dict[str, str]] = []
    checkpoint_rows: list[dict[str, str]] = []

    def read_csv(path: Path, required_columns: set[str], label: str) -> list[dict[str, str]]:
        if not path.is_file():
            errors.append(f"missing {path.relative_to(root)}")
            return []
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            missing = sorted(required_columns - fieldnames)
            if missing:
                errors.append(f"{label} missing required columns: {missing}")
                return []
            rows = list(reader)
        if not rows:
            errors.append(f"{label} must contain at least one row")
        return rows

    env_required_columns = {
        "record_id",
        "claim_ids",
        "experiments",
        "environment_status",
        "python",
        "cuda",
        "nvidia_driver",
        "pytorch",
        "key_package_versions",
        "evidence",
        "notes",
    }
    checkpoint_required_columns = {
        "record_id",
        "policy_or_model",
        "claim_ids",
        "experiment",
        "artifact_kind",
        "source_repo_or_model_id",
        "upstream_revision",
        "local_filename",
        "file_size_bytes",
        "sha256",
        "identity_status",
        "payload_included",
        "evidence",
        "notes",
    }

    env_rows = read_csv(env_path, env_required_columns, "environment_manifest.csv")
    checkpoint_rows = read_csv(checkpoint_path, checkpoint_required_columns, "checkpoint_identity_manifest.csv")

    required_claims = {
        "shortcut_libero",
        "shortcut_calvin",
        "libero_goal_pairwise_d",
        "libero_layer2",
        "simplerenv_fixed_grid",
        "simplerenv_protocol_abcde",
        "calvin_protocol1",
        "calvin_fresh_sequence",
        "widowx_scripted_dsd_91_of_96",
    }
    required_policy_by_claim = {
        "shortcut_libero": {"DINO+MLP/task-id"},
        "shortcut_calvin": {"DINO+MLP/task-id"},
        "libero_goal_pairwise_d": {"Spatial Forcing", "OpenVLA-OFT", "HiF-VLA", "SimVLA", "Pi0.5 LeRobot"},
        "libero_layer2": {"Spatial Forcing", "SimVLA", "Pi0.5 LeRobot"},
        "simplerenv_fixed_grid": {"CogACT-Base", "SpatialVLA", "InternVLA-M1", "X-VLA-WidowX", "Dexbotic / DB-MemVLA"},
        "simplerenv_protocol_abcde": {"CogACT-Base", "SpatialVLA", "InternVLA-M1", "X-VLA-WidowX", "Dexbotic / DB-MemVLA"},
        "calvin_protocol1": {"X-VLA", "GR-1", "RoboFlamingo"},
        "calvin_fresh_sequence": {"X-VLA", "GR-1", "RoboFlamingo"},
        "widowx_scripted_dsd_91_of_96": {"DINOv2 ViT-S MLP BC"},
    }
    allowed_identity_statuses = {
        "verified_local_sha256",
        "verified_hf_lfs_sha256",
        "best_effort_local_sha256_no_manifest",
        "unknown_exact_weight_files",
        "unknown_backbone_identity",
    }

    def split_claims(value: str) -> set[str]:
        return {part.strip() for part in value.split(";") if part.strip()}

    seen_ids: set[str] = set()
    env_claims: set[str] = set()
    for index, row in enumerate(env_rows, start=2):
        prefix = f"environment_manifest.csv line {index}"
        record_id = row["record_id"].strip()
        if not record_id:
            errors.append(f"{prefix}: record_id is empty")
            continue
        if record_id in seen_ids:
            errors.append(f"{prefix}: duplicate record_id {record_id}")
        seen_ids.add(record_id)
        claims = split_claims(row["claim_ids"])
        env_claims.update(claims)
        if not claims:
            errors.append(f"{prefix}: claim_ids is empty")
        for field in ["experiments", "environment_status", "python", "cuda", "nvidia_driver", "pytorch", "key_package_versions", "evidence", "notes"]:
            if not row[field].strip():
                errors.append(f"{prefix}: {field} is empty")
        if all(row[field].strip().lower() == "unknown" for field in ["python", "cuda", "nvidia_driver", "pytorch"]):
            if "unknown" not in row["environment_status"].lower() and "best_effort" not in row["environment_status"].lower():
                errors.append(f"{prefix}: unknown package fields need an unknown or best_effort environment_status")

    seen_ids.clear()
    checkpoint_claims: set[str] = set()
    observed_policy_by_claim = {claim: set() for claim in required_policy_by_claim}
    status_counts: dict[str, int] = {}
    for index, row in enumerate(checkpoint_rows, start=2):
        prefix = f"checkpoint_identity_manifest.csv line {index}"
        record_id = row["record_id"].strip()
        if not record_id:
            errors.append(f"{prefix}: record_id is empty")
            continue
        if record_id in seen_ids:
            errors.append(f"{prefix}: duplicate record_id {record_id}")
        seen_ids.add(record_id)

        claims = split_claims(row["claim_ids"])
        checkpoint_claims.update(claims)
        policy = row["policy_or_model"].strip()
        for claim in claims:
            if claim in observed_policy_by_claim:
                observed_policy_by_claim[claim].add(policy)
        for field in ["experiment", "policy_or_model", "artifact_kind", "source_repo_or_model_id", "upstream_revision", "local_filename", "file_size_bytes", "sha256", "identity_status", "payload_included", "evidence", "notes"]:
            if not row[field].strip():
                errors.append(f"{prefix}: {field} is empty")

        status = row["identity_status"].strip()
        status_counts[status] = status_counts.get(status, 0) + 1
        if status not in allowed_identity_statuses:
            errors.append(f"{prefix}: unsupported identity_status {status}")
        if row["payload_included"].strip().lower() != "false":
            errors.append(f"{prefix}: payload_included must be false")

        sha = row["sha256"].strip()
        size = row["file_size_bytes"].strip()
        if status.startswith("verified") or status == "best_effort_local_sha256_no_manifest":
            if not HEX64_RE.match(sha):
                errors.append(f"{prefix}: exact checkpoint identity rows need a lowercase 64-hex sha256")
            if not size.isdigit() or int(size) <= 0:
                errors.append(f"{prefix}: exact checkpoint identity rows need a positive integer file_size_bytes")
            if row["source_repo_or_model_id"].strip().lower() == "unknown":
                errors.append(f"{prefix}: exact checkpoint identity rows need a source_repo_or_model_id")
            if row["local_filename"].strip().lower() == "unknown":
                errors.append(f"{prefix}: exact checkpoint identity rows need a local_filename")
        elif status.startswith("unknown"):
            if sha.lower() != "unknown" or size.lower() != "unknown":
                errors.append(f"{prefix}: unknown identity rows must use unknown for sha256 and file_size_bytes")
        else:
            if sha.lower() != "unknown" and not HEX64_RE.match(sha):
                errors.append(f"{prefix}: sha256 must be unknown or lowercase 64-hex")

    missing_env_claims = sorted(required_claims - env_claims)
    if missing_env_claims:
        errors.append(f"environment_manifest.csv missing claim coverage: {missing_env_claims}")
    missing_checkpoint_claims = sorted(required_claims - checkpoint_claims)
    if missing_checkpoint_claims:
        errors.append(f"checkpoint_identity_manifest.csv missing claim coverage: {missing_checkpoint_claims}")
    for claim, required_policies in required_policy_by_claim.items():
        missing_policies = sorted(required_policies - observed_policy_by_claim[claim])
        if missing_policies:
            errors.append(f"checkpoint_identity_manifest.csv missing policies for {claim}: {missing_policies}")

    return {
        "environment_records": len(env_rows),
        "checkpoint_records": len(checkpoint_rows),
        "checkpoint_identity_status_counts": status_counts,
    }


def validate_release(root: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    validate_shape(root, errors)
    files = iter_release_files(root)
    parse_counts = validate_parseability(files, root, errors)
    validate_artifact_types(files, root, errors)
    validate_credentials(files, root, errors)
    validate_sha256sums(files, root, errors)
    manifest = validate_manifest(root, errors)
    validate_leaderboards(root, errors)
    significance_summary = validate_significance_categories(root, errors)
    provenance_summary = validate_provenance(root, errors)

    recompute = load_recompute_module(root)
    recompute_results, recompute_errors = recompute.recompute_release(root)
    errors.extend(recompute_errors)

    payload = {
        "files_scanned": len(files),
        "parse_counts": parse_counts,
        "manifest_groups": [group["directory"] for group in manifest.get("artifact_groups", [])],
        "significance_category_summary": significance_summary,
        "provenance_summary": provenance_summary,
        "recompute_results": recompute_results,
        "credential_scan_policy": "credential patterns are hard blockers; private paths/logs/hostnames/W&B links are allowed if credential-clean",
    }
    return payload, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload, errors = validate_release(args.root)
    output = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        **payload,
    }
    print(json.dumps(output, indent=2 if args.pretty else None, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
