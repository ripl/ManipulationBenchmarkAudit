#!/usr/bin/env python3
"""Recompute public manipulation benchmark audit claims from included files."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

TOL = 1e-6
SIGNIFICANCE_CATEGORY_HEADLINES = {
    "no_improvement": 497,
    "provably_not_significant": 145,
    "provably_significant": 331,
    "indeterminate": 376,
}
SIGNIFICANCE_EXCLUDED_MISSING_SCORES = 212


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def read_rows(path: Path) -> list[list[str]]:
    with path.open(newline="") as f:
        return list(csv.reader(f))


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def close(actual: float, expected: float, tol: float = TOL) -> bool:
    return math.isclose(actual, expected, rel_tol=tol, abs_tol=tol)


def parse_success(value: str) -> int:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return 1
    if normalized in {"0", "false", "no", ""}:
        return 0
    raise ValueError(f"cannot parse success value {value!r}")


def parse_timeout(value: str) -> int:
    normalized = str(value).strip().lower()
    if normalized in {"", "0", "false", "none"}:
        return 0
    return 1


def rate(successes: int, total: int) -> float:
    if total <= 0:
        raise ValueError("total must be positive")
    return successes / total


def compare_int(errors: list[str], label: str, actual: int, expected: Any) -> None:
    if actual != int(expected):
        fail(errors, f"{label}: expected {expected}, recomputed {actual}")


def compare_float(errors: list[str], label: str, actual: float, expected: Any, tol: float = TOL) -> None:
    if not close(actual, float(expected), tol=tol):
        fail(errors, f"{label}: expected {expected}, recomputed {actual:.10f}")


def recompute_dsd(root: Path, errors: list[str]) -> dict[str, Any]:
    base = root / "data_source_dependency" / "results" / "scripted_widowx"
    trials = read_csv(base / "trials.csv")
    summary_rows = read_csv(base / "results.csv")
    aggregate = load_json(base / "aggregate_summary.json")

    by_task: dict[str, dict[str, int]] = defaultdict(lambda: {"successes": 0, "trials": 0})
    for row in trials:
        task = row["task"]
        by_task[task]["trials"] += 1
        by_task[task]["successes"] += parse_success(row["success"])

    for row in summary_rows:
        task = row["task"]
        stats = by_task[task]
        compare_int(errors, f"DSD {task} successes", stats["successes"], row["successes"])
        compare_int(errors, f"DSD {task} trials", stats["trials"], row["trials"])
        compare_float(errors, f"DSD {task} success_rate", rate(stats["successes"], stats["trials"]), row["success_rate"])

    total_successes = sum(stats["successes"] for stats in by_task.values())
    total_trials = sum(stats["trials"] for stats in by_task.values())
    compare_int(errors, "DSD overall successes", total_successes, aggregate["overall"]["successes"])
    compare_int(errors, "DSD overall trials", total_trials, aggregate["overall"]["trials"])
    compare_float(errors, "DSD overall success_rate", rate(total_successes, total_trials), aggregate["overall"]["success_rate"])
    compare_int(errors, "DSD headline successes", total_successes, 91)
    compare_int(errors, "DSD headline trials", total_trials, 96)

    return {
        "overall": {
            "successes": total_successes,
            "trials": total_trials,
            "success_rate": rate(total_successes, total_trials),
        },
        "tasks": by_task,
    }


def summarize_simplerenv_rows(rows: list[dict[str, str]], keys: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, int]]:
    out: dict[tuple[str, ...], dict[str, int]] = defaultdict(lambda: {"successes": 0, "total": 0, "error_rows": 0, "timeout_rows": 0})
    for row in rows:
        key = tuple(row[k] for k in keys)
        out[key]["total"] += 1
        out[key]["successes"] += parse_success(row["success"])
        if row.get("error", "").strip():
            out[key]["error_rows"] += 1
        out[key]["timeout_rows"] += parse_timeout(row.get("timeout", ""))
    return out


def check_simplerenv_summary(
    rows: list[dict[str, str]],
    summary_path: Path,
    keys: tuple[str, ...],
    errors: list[str],
    label: str,
) -> list[dict[str, str]]:
    summary_rows = read_csv(summary_path)
    grouped = summarize_simplerenv_rows(rows, keys)
    for row in summary_rows:
        key = tuple(row[k] for k in keys)
        if key not in grouped:
            fail(errors, f"{label} missing recomputed group {key}")
            continue
        stats = grouped[key]
        compare_int(errors, f"{label} {key} successes", stats["successes"], row["successes"])
        total_col = "total" if "total" in row else "rows"
        compare_int(errors, f"{label} {key} total", stats["total"], row[total_col])
        compare_float(errors, f"{label} {key} success_rate", rate(stats["successes"], stats["total"]), row["success_rate"])
        if "error_rows" in row:
            compare_int(errors, f"{label} {key} error_rows", stats["error_rows"], row["error_rows"])
        if "timeout_rows" in row:
            compare_int(errors, f"{label} {key} timeout_rows", stats["timeout_rows"], row["timeout_rows"])
    return summary_rows


def recompute_simplerenv(root: Path, errors: list[str]) -> dict[str, Any]:
    base = root / "creeping_overfitting" / "results" / "simplerenv"
    fixed_base = base / "fixed_grid_calibration"
    dist_base = base / "distribution_overfitting"

    fixed_rows = read_csv(fixed_base / "per_episode_results_all.csv")
    fixed_report = load_json(fixed_base / "validation_report.json")
    if len(fixed_rows) != int(fixed_report["row_counts"]["full"]):
        fail(errors, f"SimplerEnv fixed rows: validation report says {fixed_report['row_counts']['full']}, found {len(fixed_rows)}")
    fixed_policy = check_simplerenv_summary(fixed_rows, fixed_base / "per_policy_summary.csv", ("policy",), errors, "SimplerEnv fixed per-policy")
    check_simplerenv_summary(fixed_rows, fixed_base / "per_task_summary.csv", ("policy", "task"), errors, "SimplerEnv fixed per-task")

    dist_rows = read_csv(dist_base / "per_episode_results_all.csv")
    dist_report = load_json(dist_base / "validation_report.json")
    compare_int(errors, "SimplerEnv Protocol A-E total rows", len(dist_rows), dist_report["expected_total_rows"])
    compare_int(errors, "SimplerEnv Protocol A-E actual rows", len(dist_rows), dist_report["actual_total_rows"])
    dist_policy = check_simplerenv_summary(dist_rows, dist_base / "per_policy_summary.csv", ("policy",), errors, "SimplerEnv Protocol A-E per-policy")
    check_simplerenv_summary(dist_rows, dist_base / "per_condition_summary.csv", ("condition",), errors, "SimplerEnv Protocol A-E per-condition")
    check_simplerenv_summary(dist_rows, dist_base / "per_policy_condition_summary.csv", ("policy", "condition"), errors, "SimplerEnv Protocol A-E per-policy-condition")

    return {
        "fixed_grid": {
            "rows": len(fixed_rows),
            "per_policy": fixed_policy,
        },
        "protocol_abcde": {
            "rows": len(dist_rows),
            "per_policy": dist_policy,
        },
    }


def group_calvin(rows: list[dict[str, str]], keys: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, float]]:
    out: dict[tuple[str, ...], dict[str, float]] = defaultdict(lambda: {"rows": 0, "tasks_completed": 0.0, "chain_success": 0.0})
    for row in rows:
        key = tuple(row[k] for k in keys)
        out[key]["rows"] += 1
        out[key]["tasks_completed"] += float(row["tasks_completed"])
        out[key]["chain_success"] += float(row["chain_success"])
    return out


def mean_metric(stats: dict[str, float], metric: str) -> float:
    return stats[metric] / stats["rows"]


def recompute_calvin(root: Path, errors: list[str]) -> dict[str, Any]:
    base = root / "creeping_overfitting" / "results" / "calvin"
    combined = load_json(base / "combined_summary.json")

    resampled_rows = read_csv(base / "resampled_pose_per_sequence.csv")
    resampled_grouped = group_calvin(resampled_rows, ("policy", "condition"))
    distribution_summary = read_csv(base / "distribution_overfitting_summary.csv")
    for row in distribution_summary:
        policy = row["policy"]
        calibration = resampled_grouped[(policy, "calibration")]
        altered_conditions = [key for key in resampled_grouped if key[0] == policy and key[1] != "calibration"]
        if len(altered_conditions) != 1:
            fail(errors, f"CALVIN {policy}: expected one altered condition, found {altered_conditions}")
            continue
        altered = resampled_grouped[altered_conditions[0]]
        compare_int(errors, f"CALVIN {policy} calibration rows", int(calibration["rows"]), row["num_sequences"])
        compare_int(errors, f"CALVIN {policy} altered rows", int(altered["rows"]), row["num_sequences"])
        cal_atc = mean_metric(calibration, "tasks_completed")
        alt_atc = mean_metric(altered, "tasks_completed")
        cal_chain = mean_metric(calibration, "chain_success")
        alt_chain = mean_metric(altered, "chain_success")
        compare_float(errors, f"CALVIN {policy} calibration_atc", cal_atc, row["calibration_atc"])
        compare_float(errors, f"CALVIN {policy} resampled_pose_atc", alt_atc, row["resampled_pose_atc"])
        compare_float(errors, f"CALVIN {policy} atc_drop", cal_atc - alt_atc, row["atc_drop_calibration_minus_resampled"])
        compare_float(errors, f"CALVIN {policy} calibration_chain_success", cal_chain, row["calibration_chain_success_rate"])
        compare_float(errors, f"CALVIN {policy} resampled_chain_success", alt_chain, row["resampled_pose_chain_success_rate"])
        compare_float(errors, f"CALVIN {policy} chain_success_drop_pp", (cal_chain - alt_chain) * 100.0, row["chain_success_drop_percentage_points"], tol=1e-5)

    fresh_rows = read_csv(base / "fresh_sequence_per_sequence.csv")
    fresh_grouped = group_calvin(fresh_rows, ("policy", "fresh_seed"))
    fresh_summary = read_csv(base / "fresh_sequence_summary.csv")
    for row in fresh_summary:
        policy = row["policy"]
        seed = row["fresh_seed"]
        calibration = resampled_grouped[(policy, "calibration")]
        cal_atc = mean_metric(calibration, "tasks_completed")
        if seed == "pooled":
            seed_groups = [stats for key, stats in fresh_grouped.items() if key[0] == policy]
            rows = sum(stats["rows"] for stats in seed_groups)
            tasks = sum(stats["tasks_completed"] for stats in seed_groups)
            fresh_atc = tasks / rows
        else:
            stats = fresh_grouped[(policy, seed)]
            rows = int(stats["rows"])
            fresh_atc = mean_metric(stats, "tasks_completed")
        compare_int(errors, f"CALVIN {policy} fresh {seed} rows", int(rows), row["num_fresh_sequences"])
        compare_float(errors, f"CALVIN {policy} fresh {seed} calibration_atc", cal_atc, row["calibration_atc"])
        compare_float(errors, f"CALVIN {policy} fresh {seed} fresh_atc", fresh_atc, row["fresh_atc"])
        compare_float(errors, f"CALVIN {policy} fresh {seed} atc_drop", cal_atc - fresh_atc, row["atc_drop_calibration_minus_fresh"])

    combined_dist = {row["policy"]: row for row in combined["distribution_overfitting"]}
    for row in distribution_summary:
        combined_row = combined_dist[row["policy"]]
        for field in [
            "calibration_atc",
            "resampled_pose_atc",
            "atc_drop_calibration_minus_resampled",
            "calibration_chain_success_rate",
            "resampled_pose_chain_success_rate",
            "chain_success_drop_percentage_points",
        ]:
            compare_float(errors, f"CALVIN combined distribution {row['policy']} {field}", float(row[field]), combined_row[field])

    combined_sample = {(row["policy"], str(row["fresh_seed"])): row for row in combined["sample_overfitting"]}
    for row in fresh_summary:
        combined_row = combined_sample[(row["policy"], row["fresh_seed"])]
        for field in ["calibration_atc", "fresh_atc", "atc_drop_calibration_minus_fresh"]:
            compare_float(errors, f"CALVIN combined sample {row['policy']} {row['fresh_seed']} {field}", float(row[field]), combined_row[field])

    return {
        "resampled_pose_rows": len(resampled_rows),
        "fresh_sequence_rows": len(fresh_rows),
        "distribution_summary": distribution_summary,
        "fresh_sequence_summary": fresh_summary,
    }


def count_error_rows(rows: list[dict[str, str]], field: str = "error_type") -> int:
    return sum(1 for row in rows if row.get(field, "").strip())


def recompute_statistical_significance(root: Path, errors: list[str]) -> dict[str, Any]:
    base = root / "statistical_significance" / "libero_goal_5x5k"
    summary_rows = read_csv(base / "policy_success_summary.csv")
    pair_rows = read_csv(base / "pairwise_disagreement.csv")
    status = load_json(root / "statistical_significance" / "libero_goal_pairwise_status.json")
    manifest = load_json(base / "shared" / "init_state_goal_5000_MANIFEST.json")

    expected_rows = 5000
    compare_int(errors, "Statistical LIBERO Goal manifest total_episodes", int(manifest["total_episodes"]), expected_rows)

    summary_by_policy = {row["policy_slug"]: row for row in summary_rows}
    policy_dirs = sorted(path.name for path in (base / "policies").iterdir() if path.is_dir())
    summary_policies = sorted(summary_by_policy)
    if policy_dirs != summary_policies:
        fail(errors, f"Statistical LIBERO Goal policy directories {policy_dirs} do not match summary policies {summary_policies}")

    outcomes_by_policy: dict[str, dict[str, int]] = {}
    task_by_policy_instance: dict[str, dict[str, str]] = {}
    reference_instances: set[str] | None = None
    reference_task_by_instance: dict[str, str] | None = None

    for policy in summary_policies:
        policy_dir = base / "policies" / policy
        rows = read_csv(policy_dir / "episodes_combined.csv")
        policy_summary = load_json(policy_dir / "policy_summary.json")
        summary_row = summary_by_policy[policy]

        instance_ids = [row["instance_id"] for row in rows]
        unique_instances = set(instance_ids)
        successes = sum(parse_success(row["success"]) for row in rows)
        errors_count = count_error_rows(rows)

        compare_int(errors, f"Statistical {policy} rows", len(rows), expected_rows)
        compare_int(errors, f"Statistical {policy} unique instance_ids", len(unique_instances), expected_rows)
        compare_int(errors, f"Statistical {policy} summary rows", len(rows), summary_row["rows"])
        compare_int(errors, f"Statistical {policy} summary unique_instance_ids", len(unique_instances), summary_row["unique_instance_ids"])
        compare_int(errors, f"Statistical {policy} summary successes", successes, summary_row["successes"])
        compare_int(errors, f"Statistical {policy} summary errors", errors_count, summary_row["errors"])
        compare_float(errors, f"Statistical {policy} summary success_rate", rate(successes, len(rows)), summary_row["success_rate"])
        compare_float(errors, f"Statistical {policy} summary success_percent", rate(successes, len(rows)) * 100.0, summary_row["success_percent"])

        for field, actual in [
            ("rows", len(rows)),
            ("unique_instance_ids", len(unique_instances)),
            ("successes", successes),
            ("errors", errors_count),
        ]:
            compare_int(errors, f"Statistical {policy} policy_summary {field}", actual, policy_summary[field])
        compare_float(errors, f"Statistical {policy} policy_summary success_rate", rate(successes, len(rows)), policy_summary["success_rate"])
        compare_float(errors, f"Statistical {policy} policy_summary success_percent", rate(successes, len(rows)) * 100.0, policy_summary["success_percent"])

        task_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "successes": 0, "errors": 0})
        task_by_instance: dict[str, str] = {}
        outcomes: dict[str, int] = {}
        for row in rows:
            if row.get("package_policy_slug") != policy:
                fail(errors, f"Statistical {policy}: row has package_policy_slug={row.get('package_policy_slug')!r}")
            instance_id = row["instance_id"]
            task_id = row["task_id"]
            outcome = parse_success(row["success"])
            outcomes[instance_id] = outcome
            task_by_instance[instance_id] = task_id
            task_stats[task_id]["rows"] += 1
            task_stats[task_id]["successes"] += outcome
            if row.get("error_type", "").strip():
                task_stats[task_id]["errors"] += 1

        for task in policy_summary.get("tasks", []):
            task_id = str(task["task_id"])
            stats = task_stats[task_id]
            compare_int(errors, f"Statistical {policy} task {task_id} rows", stats["rows"], task["rows"])
            compare_int(errors, f"Statistical {policy} task {task_id} successes", stats["successes"], task["successes"])
            compare_int(errors, f"Statistical {policy} task {task_id} errors", stats["errors"], task["errors"])
            compare_float(errors, f"Statistical {policy} task {task_id} success_rate", rate(stats["successes"], stats["rows"]), task["success_rate"])

        if reference_instances is None:
            reference_instances = unique_instances
            reference_task_by_instance = task_by_instance
        elif unique_instances != reference_instances:
            fail(errors, f"Statistical {policy}: instance_id set does not match the first policy")
        if reference_task_by_instance is not None and task_by_instance != reference_task_by_instance:
            fail(errors, f"Statistical {policy}: task_id by instance_id does not match the first policy")

        outcomes_by_policy[policy] = outcomes
        task_by_policy_instance[policy] = task_by_instance

    expected_pairs = {
        tuple(sorted((summary_policies[i], summary_policies[j])))
        for i in range(len(summary_policies))
        for j in range(i + 1, len(summary_policies))
    }
    seen_pairs: set[tuple[str, str]] = set()
    recomputed_ds: list[float] = []

    for row in pair_rows:
        policy_a = row["policy_a"]
        policy_b = row["policy_b"]
        if policy_a not in outcomes_by_policy or policy_b not in outcomes_by_policy:
            fail(errors, f"Statistical pair {policy_a}/{policy_b}: unknown policy")
            continue
        pair_key = tuple(sorted((policy_a, policy_b)))
        if pair_key in seen_pairs:
            fail(errors, f"Statistical pair {policy_a}/{policy_b}: duplicate unordered pair")
        seen_pairs.add(pair_key)

        shared_instances = sorted(set(outcomes_by_policy[policy_a]) & set(outcomes_by_policy[policy_b]))
        disagreements = sum(
            1
            for instance_id in shared_instances
            if outcomes_by_policy[policy_a][instance_id] != outcomes_by_policy[policy_b][instance_id]
        )
        d_value = disagreements / len(shared_instances)
        recomputed_ds.append(d_value)
        compare_int(errors, f"Statistical pair {policy_a}/{policy_b} n", len(shared_instances), row["n"])
        compare_int(errors, f"Statistical pair {policy_a}/{policy_b} disagreements", disagreements, row["disagreements"])
        compare_float(errors, f"Statistical pair {policy_a}/{policy_b} D", d_value, row["D"])

        task_ids = sorted({task_by_policy_instance[policy_a][instance_id] for instance_id in shared_instances}, key=int)
        for task_id in task_ids:
            column = f"task_{task_id}_D"
            if column not in row:
                fail(errors, f"Statistical pair {policy_a}/{policy_b}: missing {column}")
                continue
            task_instances = [
                instance_id
                for instance_id in shared_instances
                if task_by_policy_instance[policy_a][instance_id] == task_id
            ]
            task_disagreements = sum(
                1
                for instance_id in task_instances
                if outcomes_by_policy[policy_a][instance_id] != outcomes_by_policy[policy_b][instance_id]
            )
            compare_float(
                errors,
                f"Statistical pair {policy_a}/{policy_b} {column}",
                task_disagreements / len(task_instances),
                row[column],
            )

    if seen_pairs != expected_pairs:
        fail(errors, f"Statistical pair rows {sorted(seen_pairs)} do not match expected pairs {sorted(expected_pairs)}")

    mean_d = mean(recomputed_ds)
    median_d = median(recomputed_ds)
    compare_float(errors, "Statistical LIBERO Goal mean pairwise D", mean_d, 0.03528)
    compare_float(errors, "Statistical LIBERO Goal median pairwise D", median_d, 0.0354)

    if status.get("public_recompute_available") is not True:
        fail(errors, "Statistical significance status must mark public_recompute_available=true")
    if status.get("public_status") != "public_recomputed_from_release_files":
        fail(errors, "Unexpected statistical significance public status")
    paper_summary = status.get("paper_facing_summary", {})
    compare_int(errors, "Statistical status num_policies", len(summary_policies), paper_summary.get("num_policies"))
    compare_int(errors, "Statistical status rollouts_per_policy", expected_rows, paper_summary.get("rollouts_per_policy"))
    compare_float(errors, "Statistical status mean_pairwise_disagreement_d", mean_d, paper_summary.get("mean_pairwise_disagreement_d"))
    compare_float(errors, "Statistical status median_pairwise_disagreement_d", median_d, paper_summary.get("median_pairwise_disagreement_d"))

    return {
        "package": "statistical_significance/libero_goal_5x5k",
        "num_policies": len(summary_policies),
        "rollouts_per_policy": expected_rows,
        "pairwise_rows": len(pair_rows),
        "mean_pairwise_disagreement_d": mean_d,
        "median_pairwise_disagreement_d": median_d,
    }


def recompute_statistical_significance_categories(root: Path, errors: list[str]) -> dict[str, Any]:
    base = root / "statistical_significance" / "significance_categories"
    all_rows = read_csv(base / "all_comparisons.csv")
    counts = {category: 0 for category in SIGNIFICANCE_CATEGORY_HEADLINES}
    for row in all_rows:
        category = row["category"]
        if category not in counts:
            fail(errors, f"Significance categories: unexpected category {category!r}")
            continue
        counts[category] += 1

    for category, expected_count in SIGNIFICANCE_CATEGORY_HEADLINES.items():
        category_rows = read_csv(base / f"{category}.csv")
        compare_int(errors, f"Significance category {category} all_comparisons count", counts[category], expected_count)
        compare_int(errors, f"Significance category {category} file rows", len(category_rows), expected_count)
        for row in category_rows:
            if row.get("category") != category:
                fail(errors, f"Significance category file {category}.csv has row labelled {row.get('category')!r}")

    excluded_rows = read_csv(base / "excluded_missing_scores.csv")
    compare_int(errors, "Significance categories excluded_missing_scores rows", len(excluded_rows), SIGNIFICANCE_EXCLUDED_MISSING_SCORES)
    compare_int(errors, "Significance categories all comparable rows", len(all_rows), sum(SIGNIFICANCE_CATEGORY_HEADLINES.values()))

    return {
        "package": "statistical_significance/significance_categories",
        "all_comparisons": len(all_rows),
        "category_counts": counts,
        "excluded_missing_scores": len(excluded_rows),
    }


def compare_libero_policy_summaries(
    policy_rows: list[dict[str, str]],
    suite_rows: list[dict[str, str]],
    errors: list[str],
    label: str,
) -> dict[str, dict[str, int]]:
    suite_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"successes": 0, "rows": 0, "errors": 0, "suites": 0})
    for row in suite_rows:
        policy = row["policy"]
        successes = int(row["successes"])
        rows = int(row["rows"])
        errors_count = int(row["errors"])
        compare_float(errors, f"{label} {policy} {row['suite']} success_rate", rate(successes, rows), row["success_rate"])
        suite_totals[policy]["successes"] += successes
        suite_totals[policy]["rows"] += rows
        suite_totals[policy]["errors"] += errors_count
        suite_totals[policy]["suites"] += 1

    policy_totals: dict[str, dict[str, int]] = {}
    for row in policy_rows:
        policy = row["policy"]
        stats = suite_totals[policy]
        compare_int(errors, f"{label} {policy} suite count", stats["suites"], 4)
        compare_int(errors, f"{label} {policy} successes", stats["successes"], row["successes"])
        compare_int(errors, f"{label} {policy} rows", stats["rows"], row["rows"])
        compare_int(errors, f"{label} {policy} errors", stats["errors"], row["errors"])
        compare_float(errors, f"{label} {policy} success_rate", rate(stats["successes"], stats["rows"]), row["success_rate"])
        policy_totals[policy] = {
            "successes": stats["successes"],
            "rows": stats["rows"],
            "errors": stats["errors"],
        }
    if sorted(policy_totals) != sorted(suite_totals):
        fail(errors, f"{label} policy rows {sorted(policy_totals)} do not match suite rows {sorted(suite_totals)}")
    return policy_totals


def recompute_libero_layer2(root: Path, errors: list[str]) -> dict[str, Any]:
    base = root / "creeping_overfitting" / "results" / "libero"
    official_totals = compare_libero_policy_summaries(
        read_csv(base / "official_calibration" / "selected_policy_summary.csv"),
        read_csv(base / "official_calibration" / "selected_policy_suite_summary.csv"),
        errors,
        "LIBERO Layer 2 official calibration",
    )
    fresh_totals = compare_libero_policy_summaries(
        read_csv(base / "fresh_init_state" / "policy_summary.csv"),
        read_csv(base / "fresh_init_state" / "policy_suite_summary.csv"),
        errors,
        "LIBERO Layer 2 fresh init state",
    )

    sample_rows = read_csv(base / "sample_overfitting_summary.csv")
    expected_headlines = {
        "spatial_forcing": ("Spatial Forcing", 9718, 10000, 0.9718),
        "simvla": ("SimVLA", 9760, 10000, 0.9760),
        "pi05_lerobot": ("Pi05 / LeRobot", 9741, 10000, 0.9741),
    }
    for row in sample_rows:
        policy = row["policy"]
        if policy not in expected_headlines:
            fail(errors, f"LIBERO Layer 2 sample summary has unexpected policy {policy}")
            continue
        label, expected_successes, expected_rows, expected_rate = expected_headlines[policy]
        if row["policy_label"] != label:
            fail(errors, f"LIBERO Layer 2 {policy}: expected label {label!r}, found {row['policy_label']!r}")
        official = official_totals[policy]
        fresh = fresh_totals[policy]
        compare_int(errors, f"LIBERO Layer 2 {policy} official_successes", official["successes"], row["official_successes"])
        compare_int(errors, f"LIBERO Layer 2 {policy} official_rows", official["rows"], row["official_rows"])
        compare_float(errors, f"LIBERO Layer 2 {policy} official_rate", rate(official["successes"], official["rows"]), row["official_rate"])
        compare_int(errors, f"LIBERO Layer 2 {policy} fresh_successes", fresh["successes"], row["fresh_successes"])
        compare_int(errors, f"LIBERO Layer 2 {policy} fresh_rows", fresh["rows"], row["fresh_rows"])
        compare_float(errors, f"LIBERO Layer 2 {policy} fresh_rate", rate(fresh["successes"], fresh["rows"]), row["fresh_rate"])
        compare_float(errors, f"LIBERO Layer 2 {policy} drop_pp", (rate(official["successes"], official["rows"]) - rate(fresh["successes"], fresh["rows"])) * 100.0, row["drop_pp"])
        compare_int(errors, f"LIBERO Layer 2 {policy} headline successes", fresh["successes"], expected_successes)
        compare_int(errors, f"LIBERO Layer 2 {policy} headline rows", fresh["rows"], expected_rows)
        compare_float(errors, f"LIBERO Layer 2 {policy} headline rate", rate(fresh["successes"], fresh["rows"]), expected_rate)

    if sorted(row["policy"] for row in sample_rows) != sorted(expected_headlines):
        fail(errors, "LIBERO Layer 2 sample summary policies do not match expected headline policies")

    return {
        "fresh_policy_rates": {
            policy: {
                "successes": stats["successes"],
                "rows": stats["rows"],
                "success_rate": rate(stats["successes"], stats["rows"]),
            }
            for policy, stats in fresh_totals.items()
        }
    }


def recompute_shortcut(root: Path, errors: list[str]) -> dict[str, Any]:
    base = root / "shortcut_solvability" / "results"

    libero_rows = read_csv(base / "libero" / "results.csv")
    for row in libero_rows:
        artifact_dir = row["artifact_dir"]
        summary = load_json(base / "libero" / "best_checkpoint" / artifact_dir / "summary.json")
        trials = read_rows(base / "libero" / "best_checkpoint" / artifact_dir / "trials.csv")
        successes = sum(int(trial[3]) for trial in trials)
        total = len(trials)
        compare_int(errors, f"Shortcut LIBERO {artifact_dir} successes", successes, row["successes"])
        compare_int(errors, f"Shortcut LIBERO {artifact_dir} trials", total, row["trials"])
        compare_int(errors, f"Shortcut LIBERO {artifact_dir} summary successes", successes, summary["num_successes"])
        compare_int(errors, f"Shortcut LIBERO {artifact_dir} summary trials", total, summary["num_trials"])
        compare_float(errors, f"Shortcut LIBERO {artifact_dir} success_rate", rate(successes, total), row["success_rate"])
        compare_float(errors, f"Shortcut LIBERO {artifact_dir} summary success_rate", rate(successes, total), summary["success_rate"])

    calvin_rows = read_csv(base / "calvin" / "results.csv")
    for row in calvin_rows:
        artifact_dir = row["artifact_dir"]
        summary = load_json(base / "calvin" / "best_checkpoint" / artifact_dir / "summary.json")
        trials = read_rows(base / "calvin" / "best_checkpoint" / artifact_dir / "trials.csv")
        completed = [int(trial[1]) for trial in trials]
        total = len(completed)
        atc = sum(completed) / total
        compare_int(errors, f"Shortcut CALVIN {artifact_dir} sequences", total, row["num_sequences"])
        compare_int(errors, f"Shortcut CALVIN {artifact_dir} summary sequences", total, summary["num_sequences"])
        compare_float(errors, f"Shortcut CALVIN {artifact_dir} ATC", atc, row["avg_seq_len_atc"])
        compare_float(errors, f"Shortcut CALVIN {artifact_dir} summary ATC", atc, summary["avg_seq_len"])
        for threshold in range(1, 6):
            chain_rate = sum(1 for value in completed if value >= threshold) / total
            compare_float(errors, f"Shortcut CALVIN {artifact_dir} chain_sr_{threshold}", chain_rate, row[f"chain_sr_{threshold}"])
            compare_float(errors, f"Shortcut CALVIN {artifact_dir} summary chain_sr_{threshold}", chain_rate, summary["chain_sr"][str(threshold)])

    return {"libero": libero_rows, "calvin": calvin_rows}


def recompute_release(root: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    statistical_results = recompute_statistical_significance(root, errors)
    statistical_results["aggregate_category_counts"] = recompute_statistical_significance_categories(root, errors)
    results = {
        "shortcut_solvability": recompute_shortcut(root, errors),
        "data_source_dependency": recompute_dsd(root, errors),
        "creeping_overfitting": {
            "simplerenv": recompute_simplerenv(root, errors),
            "calvin": recompute_calvin(root, errors),
            "libero": recompute_libero_layer2(root, errors),
        },
        "statistical_significance": statistical_results,
    }
    return results, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    results, errors = recompute_release(args.root)
    payload = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "results": results,
    }
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
