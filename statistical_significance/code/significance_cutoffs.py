"""Reference cutoff calculations for the statistical-significance section.

This is a lightweight reference script for the aggregate-data cutoff logic. It
does not bundle leaderboard CSV exports, generated plots, or derived tables.
"""

import math

import numpy as np
from numba import njit
from scipy.stats import norm


def normal_critical_value(alpha):
    return float(norm.ppf(1 - alpha))


def q_lower_for_gap(L, S):
    r = L % S
    return r - (r * r) / S


def _packed_square_sum(total, R):
    q, r = divmod(total, R)
    return q * R * R + r * r


def _packed_sample_count(total, R):
    if total == 0:
        return 0
    return (total + R - 1) // R


def _largest_feasible_negative_total(L, j_max, S, R):
    lo = 0
    hi = j_max
    while lo < hi:
        mid = (lo + hi + 1) // 2
        n_used = _packed_sample_count(L + mid, R) + _packed_sample_count(mid, R)
        if n_used <= S:
            lo = mid
        else:
            hi = mid - 1
    return lo


def max_task_sum_squares(a, b, S, R):
    if b < a:
        return max_task_sum_squares(b, a, S, R)
    L = b - a
    j_max = min(a, R * S - b)
    j = _largest_feasible_negative_total(L, j_max, S, R)
    return _packed_square_sum(L + j, R) + _packed_square_sum(j, R)


def task_q_max(a, b, S, R):
    d = b - a
    return max_task_sum_squares(a, b, S, R) - (d * d) / S


def make_binary_local_qmax(S):
    local_qmax = np.empty((S + 1, S + 1), dtype=np.float64)
    for a in range(S + 1):
        for b in range(S + 1):
            m_max = min(a + b, 2 * S - a - b)
            d = b - a
            local_qmax[a, b] = m_max - (d * d) / S
    return local_qmax


@njit
def compute_binary_qmax_all_numba(T, S, N, local_qmax):
    neg = -1e18
    dp = np.full((N + 1, N + 1), neg)
    dp[0, 0] = 0.0
    for t in range(T):
        max_prev = t * S
        new = np.full((N + 1, N + 1), neg)
        for A0 in range(max_prev + 1):
            for B0 in range(max_prev + 1):
                base = dp[A0, B0]
                if base < -1e17:
                    continue
                for a in range(S + 1):
                    A1 = A0 + a
                    for b in range(S + 1):
                        B1 = B0 + b
                        val = base + local_qmax[a, b]
                        if val > new[A1, B1]:
                            new[A1, B1] = val
        dp = new
    return dp


def compute_binary_qmax_all(T, S):
    N = T * S
    local_qmax = make_binary_local_qmax(S)
    return compute_binary_qmax_all_numba(T, S, N, local_qmax)


def make_local_qmax(S, R):
    max_score = R * S
    local_qmax = np.empty((max_score + 1, max_score + 1), dtype=np.float64)
    for a in range(max_score + 1):
        for b in range(max_score + 1):
            local_qmax[a, b] = task_q_max(a, b, S, R)
    return local_qmax


def compute_qmax_all(T, S, R):
    if R == 1:
        return compute_binary_qmax_all(T, S)
    max_task_score = R * S
    max_total_score = R * T * S
    local_qmax = make_local_qmax(S, R)
    neg = -1e18
    dp = np.full((max_total_score + 1, max_total_score + 1), neg)
    dp[0, 0] = 0.0
    for t in range(T):
        max_prev = t * max_task_score
        new = np.full((max_total_score + 1, max_total_score + 1), neg)
        for A0 in range(max_prev + 1):
            for B0 in range(max_prev + 1):
                base = dp[A0, B0]
                if base < -1e17:
                    continue
                for a in range(max_task_score + 1):
                    A1 = A0 + a
                    for b in range(max_task_score + 1):
                        B1 = B0 + b
                        val = base + local_qmax[a, b]
                        if val > new[A1, B1]:
                            new[A1, B1] = val
        dp = new
    return dp


def precompute_qmax(T, S, R):
    if T == 1:
        return None
    return compute_qmax_all(T, S, R)


def q_max_for_counts(A, B, T, S, R, qmax_all=None):
    if T == 1:
        return task_q_max(A, B, S, R)
    return qmax_all[A, B]


def necessary_L_for_A(A, T, S, R, z):
    max_gap = R * T * S - A
    for L in range(1, max_gap + 1):
        qmin = q_lower_for_gap(L, S)
        rhs = z * math.sqrt((S / (S - 1)) * qmin)
        if L > rhs:
            return L
    return np.nan


def sufficient_L_for_A(A, T, S, R, z, qmax_all=None):
    max_gap = R * T * S - A
    threshold = np.nan
    suffix_all_reject = True
    for L in range(max_gap, 0, -1):
        qmax = q_max_for_counts(A, A + L, T, S, R, qmax_all=qmax_all)
        rhs = z * math.sqrt((S / (S - 1)) * qmax)
        suffix_all_reject = suffix_all_reject and L > rhs
        if suffix_all_reject:
            threshold = L
    return threshold


def compute_cutoffs(mu_a, T, S, R, alpha, qmax_all=None):
    N = T * S
    A = int(round(mu_a * N))
    z = normal_critical_value(alpha)
    L_necessary = necessary_L_for_A(A, T, S, R, z)
    L_sufficient = sufficient_L_for_A(A, T, S, R, z, qmax_all=qmax_all)
    return {
        "P_A": A / N,
        "Delta_necessary": L_necessary / N,
        "Delta_sufficient": L_sufficient / N,
    }
