#!/usr/bin/env python3
"""Generate public aggregate-data significance category CSVs.

The input CSVs are the Sam official-protocol previous-SOTA exports copied under
leaderboards/stat_significance_sam_export_20260522T233929/. The cutoff logic mirrors
significance_cutoffs.py but avoids scipy/numba so the released tables can be
regenerated in a lightweight environment. For T > 1 binary suites, numpy is used
for the dynamic program.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Iterable


NO_IMPROVEMENT = "no_improvement"
PROVABLY_NOT_SIGNIFICANT = "provably_not_significant"
PROVABLY_SIGNIFICANT = "provably_significant"
INDETERMINATE = "indeterminate"
CATEGORIES = [
    NO_IMPROVEMENT,
    PROVABLY_NOT_SIGNIFICANT,
    PROVABLY_SIGNIFICANT,
    INDETERMINATE,
]
COUNT_ROUNDING_METHOD = "python_round_nearest_even_matches_significance_cutoffs"


@dataclass(frozen=True)
class BenchmarkParams:
    benchmark: str
    track: str
    source_csv: str
    current_column: str
    previous_column: str
    T: int
    S: int
    R: int
    score_unit: str
    score_multiplier: float
    notes: str


PARAMS: list[BenchmarkParams] = [
    BenchmarkParams(
        "LIBERO",
        "spatial",
        "sam_libero_official_prev_sota.csv",
        "libero_spatial",
        "libero_spatial_prev_sota",
        T=10,
        S=50,
        R=1,
        score_unit="percent",
        score_multiplier=100.0,
        notes="Per-suite binary success rate over 10 tasks x 50 official trials.",
    ),
    BenchmarkParams(
        "LIBERO",
        "object",
        "sam_libero_official_prev_sota.csv",
        "libero_object",
        "libero_object_prev_sota",
        T=10,
        S=50,
        R=1,
        score_unit="percent",
        score_multiplier=100.0,
        notes="Per-suite binary success rate over 10 tasks x 50 official trials.",
    ),
    BenchmarkParams(
        "LIBERO",
        "goal",
        "sam_libero_official_prev_sota.csv",
        "libero_goal",
        "libero_goal_prev_sota",
        T=10,
        S=50,
        R=1,
        score_unit="percent",
        score_multiplier=100.0,
        notes="Per-suite binary success rate over 10 tasks x 50 official trials.",
    ),
    BenchmarkParams(
        "LIBERO",
        "long10",
        "sam_libero_official_prev_sota.csv",
        "libero_long10",
        "libero_long10_prev_sota",
        T=10,
        S=50,
        R=1,
        score_unit="percent",
        score_multiplier=100.0,
        notes="Per-suite binary success rate over 10 tasks x 50 official trials.",
    ),
    BenchmarkParams(
        "CALVIN",
        "abc_d_atc",
        "sam_calvin_abc_d_official_prev_sota.csv",
        "calvin_abc_d_atc",
        "calvin_abc_d_prev_sota_atc",
        T=1,
        S=1000,
        R=5,
        score_unit="raw_atc",
        score_multiplier=1.0,
        notes="Aggregate ABC-D average-tasks-completed score over 1000 sequences; each sequence contributes 0..5.",
    ),
    BenchmarkParams(
        "SimplerEnv",
        "widowx_bridge",
        "sam_simplerenv_widowx_bridge_official_prev_sota.csv",
        "simplerenv_widowx_bridge_success_rate",
        "simplerenv_widowx_bridge_prev_sota_success_rate",
        T=1,
        S=96,
        R=1,
        score_unit="percent",
        score_multiplier=100.0,
        notes="Protocol-level binary success rate over 4 tasks x 24 trials; per-task scores are not used in this public aggregate audit.",
    ),
    BenchmarkParams(
        "RoboCasa",
        "rss24",
        "sam_robocasa_rss24_official_prev_sota.csv",
        "robocasa_rss24_success_rate",
        "robocasa_rss24_prev_sota_success_rate",
        T=1,
        S=1200,
        R=1,
        score_unit="percent",
        score_multiplier=100.0,
        notes="Protocol-level binary success rate over 24 tasks x 50 trials; per-task scores are not used in this public aggregate audit.",
    ),
    BenchmarkParams(
        "RoboTwin2",
        "hard_randomized",
        "sam_robotwin2_randomized_augmented_official_prev_sota.csv",
        "robotwin2_hard_randomized_success_rate",
        "robotwin2_hard_randomized_50clean_500rand_prev_sota_success_rate",
        T=1,
        S=5000,
        R=1,
        score_unit="percent",
        score_multiplier=100.0,
        notes="Protocol-level binary success rate over 50 tasks x 100 trials; per-task scores are not used in this public aggregate audit.",
    ),
]


def q_lower_for_gap(L: int, S: int) -> float:
    r = L % S
    return r - (r * r) / S


def packed_square_sum(total: int, R: int) -> int:
    q, r = divmod(total, R)
    return q * R * R + r * r


def packed_sample_count(total: int, R: int) -> int:
    if total == 0:
        return 0
    return (total + R - 1) // R


def largest_feasible_negative_total(L: int, j_max: int, S: int, R: int) -> int:
    lo = 0
    hi = j_max
    while lo < hi:
        mid = (lo + hi + 1) // 2
        n_used = packed_sample_count(L + mid, R) + packed_sample_count(mid, R)
        if n_used <= S:
            lo = mid
        else:
            hi = mid - 1
    return lo


def max_task_sum_squares(a: int, b: int, S: int, R: int) -> int:
    if b < a:
        return max_task_sum_squares(b, a, S, R)
    L = b - a
    j_max = min(a, R * S - b)
    j = largest_feasible_negative_total(L, j_max, S, R)
    return packed_square_sum(L + j, R) + packed_square_sum(j, R)


def task_q_max(a: int, b: int, S: int, R: int) -> float:
    d = b - a
    return max_task_sum_squares(a, b, S, R) - (d * d) / S


def compute_binary_qmax_all(T: int, S: int):
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("numpy is required to regenerate LIBERO T>1 category cutoffs") from exc

    N = T * S
    local_qmax = np.empty((S + 1, S + 1), dtype=np.float64)
    for a in range(S + 1):
        for b in range(S + 1):
            m_max = min(a + b, 2 * S - a - b)
            d = b - a
            local_qmax[a, b] = m_max - (d * d) / S

    neg = -1e18
    dp = np.full((N + 1, N + 1), neg, dtype=np.float64)
    dp[0, 0] = 0.0
    for t in range(T):
        max_prev = t * S
        new = np.full((N + 1, N + 1), neg, dtype=np.float64)
        previous = dp[: max_prev + 1, : max_prev + 1]
        for a in range(S + 1):
            for b in range(S + 1):
                block = new[a : a + max_prev + 1, b : b + max_prev + 1]
                np.maximum(block, previous + local_qmax[a, b], out=block)
        dp = new
    return dp


def q_max_for_counts(A: int, B: int, params: BenchmarkParams, qmax_all=None) -> float:
    if params.T == 1:
        return task_q_max(A, B, params.S, params.R)
    if qmax_all is None:
        raise RuntimeError(f"missing qmax table for {params.benchmark} {params.track}")
    return float(qmax_all[A, B])


def necessary_L_for_A(A: int, params: BenchmarkParams, z: float) -> int | None:
    max_gap = params.R * params.T * params.S - A
    for L in range(1, max_gap + 1):
        qmin = q_lower_for_gap(L, params.S)
        rhs = z * math.sqrt((params.S / (params.S - 1)) * qmin)
        if L > rhs:
            return L
    return None


def sufficient_L_for_A(A: int, params: BenchmarkParams, z: float, qmax_all=None) -> int | None:
    max_gap = params.R * params.T * params.S - A
    threshold: int | None = None
    suffix_all_reject = True
    for L in range(max_gap, 0, -1):
        qmax = max(q_max_for_counts(A, A + L, params, qmax_all=qmax_all), 0.0)
        rhs = z * math.sqrt((params.S / (params.S - 1)) * qmax)
        suffix_all_reject = suffix_all_reject and L > rhs
        if suffix_all_reject:
            threshold = L
    return threshold


def parse_score(value: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def score_to_scaled_count(score: float, params: BenchmarkParams) -> float:
    N = params.T * params.S
    if params.score_unit == "percent":
        if not 0.0 <= score <= 100.0:
            raise ValueError(f"{params.benchmark} {params.track}: percent score out of range: {score}")
        return (score / 100.0) * N
    if params.score_unit == "raw_atc":
        if not 0.0 <= score <= params.R:
            raise ValueError(f"{params.benchmark} {params.track}: raw ATC score out of range: {score}")
        return score * N
    raise ValueError(f"unsupported score unit: {params.score_unit}")


def score_to_count(score: float, params: BenchmarkParams) -> int:
    return int(round(score_to_scaled_count(score, params)))


def count_delta_to_score_delta(count_delta: int | None, params: BenchmarkParams) -> str:
    if count_delta is None:
        return "unknown"
    N = params.T * params.S
    return format_float((count_delta / N) * params.score_multiplier)


def format_float(value: float) -> str:
    return f"{value:.10g}"


def category_for(
    reported_delta: float,
    A: int,
    B: int,
    params: BenchmarkParams,
    z: float,
    qmax_all=None,
) -> tuple[str, int | None, int | None]:
    L = B - A
    necessary = necessary_L_for_A(A, params, z)
    sufficient = sufficient_L_for_A(A, params, z, qmax_all=qmax_all)
    if reported_delta <= 0:
        return NO_IMPROVEMENT, necessary, sufficient
    if L <= 0:
        return PROVABLY_NOT_SIGNIFICANT, necessary, sufficient
    if necessary is not None and L < necessary:
        return PROVABLY_NOT_SIGNIFICANT, necessary, sufficient
    if sufficient is not None and L >= sufficient:
        return PROVABLY_SIGNIFICANT, necessary, sufficient
    return INDETERMINATE, necessary, sufficient


def source_rows(input_dir: Path, params: BenchmarkParams) -> Iterable[tuple[int, dict[str, str]]]:
    path = input_dir / params.source_csv
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"paper_name", params.current_column, params.previous_column}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"{path}: missing columns {missing}")
        yield from enumerate(reader, start=2)


def build_rows(root: Path, alpha: float) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    input_dir = root / "leaderboards" / "stat_significance_sam_export_20260522T233929"
    z = NormalDist().inv_cdf(1 - alpha)
    qmax_by_shape = {}
    categorized: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    parameter_rows: list[dict[str, str]] = []

    for params in PARAMS:
        key = (params.T, params.S, params.R)
        if params.T > 1 and key not in qmax_by_shape:
            if params.R != 1:
                raise ValueError(f"only binary T>1 qmax precompute is implemented, got {params}")
            qmax_by_shape[key] = compute_binary_qmax_all(params.T, params.S)
        qmax_all = qmax_by_shape.get(key)

        category_counts = {category: 0 for category in CATEGORIES}
        excluded_count = 0
        for source_line, row in source_rows(input_dir, params):
            current = parse_score(row[params.current_column])
            previous = parse_score(row[params.previous_column])
            base = {
                "benchmark": params.benchmark,
                "track": params.track,
                "paper_name": row["paper_name"].strip(),
                "source_csv": f"leaderboards/stat_significance_sam_export_20260522T233929/{params.source_csv}",
                "source_line": str(source_line),
                "current_column": params.current_column,
                "previous_sota_column": params.previous_column,
                "current_score": "" if current is None else format_float(current),
                "previous_sota_score": "" if previous is None else format_float(previous),
                "score_unit": params.score_unit,
                "T": str(params.T),
                "S": str(params.S),
                "R": str(params.R),
                "alpha": format_float(alpha),
                "z_critical": format_float(z),
                "notes": params.notes,
            }
            if current is None or previous is None:
                excluded_count += 1
                excluded.append(
                    {
                        **base,
                        "exclusion_reason": "missing_current_or_previous_sota_score",
                    }
                )
                continue

            A = score_to_count(previous, params)
            B = score_to_count(current, params)
            previous_scaled = score_to_scaled_count(previous, params)
            current_scaled = score_to_scaled_count(current, params)
            reported_delta = current - previous
            category, necessary, sufficient = category_for(reported_delta, A, B, params, z, qmax_all=qmax_all)
            category_counts[category] += 1
            categorized.append(
                {
                    **base,
                    "reported_delta": format_float(reported_delta),
                    "previous_sota_scaled_count": format_float(previous_scaled),
                    "current_scaled_count": format_float(current_scaled),
                    "previous_sota_count": str(A),
                    "current_count": str(B),
                    "previous_sota_rounding_residual": format_float(previous_scaled - A),
                    "current_rounding_residual": format_float(current_scaled - B),
                    "count_rounding_method": COUNT_ROUNDING_METHOD,
                    "count_delta": str(B - A),
                    "necessary_count_delta": "unknown" if necessary is None else str(necessary),
                    "sufficient_count_delta": "unknown" if sufficient is None else str(sufficient),
                    "necessary_score_delta": count_delta_to_score_delta(necessary, params),
                    "sufficient_score_delta": count_delta_to_score_delta(sufficient, params),
                    "category": category,
                }
            )

        parameter_rows.append(
            {
                "benchmark": params.benchmark,
                "track": params.track,
                "source_csv": f"leaderboards/stat_significance_sam_export_20260522T233929/{params.source_csv}",
                "current_column": params.current_column,
                "previous_sota_column": params.previous_column,
                "T": str(params.T),
                "S": str(params.S),
                "R": str(params.R),
                "score_unit": params.score_unit,
                "count_rounding_method": COUNT_ROUNDING_METHOD,
                "alpha": format_float(alpha),
                "z_critical": format_float(z),
                "categorized_rows": str(sum(category_counts.values())),
                "excluded_missing_score_rows": str(excluded_count),
                **{f"{category}_rows": str(category_counts[category]) for category in CATEGORIES},
                "notes": params.notes,
            }
        )

    return categorized, excluded, parameter_rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()

    root = args.root
    out_dir = root / "statistical_significance" / "significance_categories"
    categorized, excluded, parameter_rows = build_rows(root, args.alpha)

    category_fieldnames = [
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
    ]
    write_csv(out_dir / "all_comparisons.csv", categorized, category_fieldnames)
    for category in CATEGORIES:
        rows = [row for row in categorized if row["category"] == category]
        write_csv(out_dir / f"{category}.csv", rows, category_fieldnames)

    exclusion_fieldnames = [
        "benchmark",
        "track",
        "paper_name",
        "source_csv",
        "source_line",
        "current_column",
        "previous_sota_column",
        "current_score",
        "previous_sota_score",
        "score_unit",
        "T",
        "S",
        "R",
        "alpha",
        "z_critical",
        "exclusion_reason",
        "notes",
    ]
    write_csv(out_dir / "excluded_missing_scores.csv", excluded, exclusion_fieldnames)

    parameter_fieldnames = [
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
        *[f"{category}_rows" for category in CATEGORIES],
        "notes",
    ]
    write_csv(out_dir / "classification_parameters.csv", parameter_rows, parameter_fieldnames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
