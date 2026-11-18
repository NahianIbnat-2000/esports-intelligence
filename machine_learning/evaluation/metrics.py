"""Evaluation metrics for probabilistic binary predictions.

Brier score:  BS = (1/N) * sum_i (p_i - y_i)^2   (lower is better; 0.25 = coin flip)
Log loss:     LL = -(1/N) * sum_i [y_i log p_i + (1 - y_i) log(1 - p_i)]
Accuracy, precision, recall and F1 use a 0.5 threshold with "blue side wins"
as the positive class.
Expected calibration error (ECE): sum over 10 equal-width probability bins of
(share of games in the bin) x |mean predicted - observed frequency|.
A model that always predicts one value (a baseline) has no ranking ability, so
its ROC-AUC is reported as null rather than 0.5.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, brier_score_loss, confusion_matrix, f1_score, log_loss,
                             precision_score, recall_score, roc_auc_score, roc_curve)

EPS = 1e-12


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def summary(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y).astype(int)
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    yhat = (p >= 0.5).astype(int)
    two_classes = len(np.unique(y)) == 2 and len(np.unique(p)) > 1
    return {
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, yhat)),
        "precision": float(precision_score(y, yhat, zero_division=0)),
        "recall": float(recall_score(y, yhat, zero_division=0)),
        "f1": float(f1_score(y, yhat, zero_division=0)),
        "ece": expected_calibration_error(y, p),
        "roc_auc": float(roc_auc_score(y, p)) if two_classes else None,
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "base_rate_blue_win": float(y.mean()),
    }


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        mask = idx == b
        if mask.any():
            ece += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return float(ece)


def probability_histogram(p: np.ndarray, n_bins: int = 20) -> list[dict]:
    counts, edges = np.histogram(np.asarray(p, dtype=float), bins=n_bins, range=(0, 1))
    return [{"lower": float(edges[i]), "upper": float(edges[i + 1]), "n": int(c)} for i, c in enumerate(counts)]


def calibration_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict]:
    """Equal-width bins on [0, 1]; empty bins are reported with n = 0 and null means."""
    y, p = np.asarray(y), np.asarray(p)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = idx == b
        rows.append({"bin_lower": float(edges[b]), "bin_upper": float(edges[b + 1]), "n": int(mask.sum()),
                     "mean_predicted": float(p[mask].mean()) if mask.any() else None,
                     "observed_frequency": float(y[mask].mean()) if mask.any() else None})
    return rows


def roc_points(y: np.ndarray, p: np.ndarray, max_points: int = 101) -> list[dict]:
    if len(np.unique(y)) < 2:
        return []
    fpr, tpr, _ = roc_curve(y, p)
    if len(fpr) > max_points:
        keep = np.unique(np.linspace(0, len(fpr) - 1, max_points).astype(int))
        fpr, tpr = fpr[keep], tpr[keep]
    return [{"fpr": float(a), "tpr": float(b)} for a, b in zip(fpr, tpr)]


def confusion(y: np.ndarray, p: np.ndarray) -> dict:
    tn, fp, fn, tp = confusion_matrix(np.asarray(y).astype(int), (np.asarray(p) >= 0.5).astype(int),
                                      labels=[0, 1]).ravel()
    return {"true_negative": int(tn), "false_positive": int(fp), "false_negative": int(fn), "true_positive": int(tp)}


def paired_bootstrap_diff(y: np.ndarray, p_model: np.ndarray, p_base: np.ndarray, metric: str = "brier",
                          n_boot: int = 2000, seed: int = 0, clusters: np.ndarray | None = None) -> dict:
    """Bootstrap CI for metric(model) - metric(base) on the same observations.
    Negative values mean the model has a lower (better) Brier / log loss.

    With `clusters` (e.g. a series id), whole clusters are resampled, so
    dependence between games of the same series is respected."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    pm = np.clip(np.asarray(p_model), EPS, 1 - EPS)
    pb = np.clip(np.asarray(p_base), EPS, 1 - EPS)

    def loss(p, yy):
        if metric == "brier":
            return (p - yy) ** 2
        return -(yy * np.log(p) + (1 - yy) * np.log(1 - p))

    d = loss(pm, y) - loss(pb, y)
    n = len(d)
    if clusters is None:
        boots = np.array([d[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
        n_clusters = n
    else:
        codes, uniq = pd.factorize(pd.Series(clusters))
        k = len(uniq)
        sums = np.bincount(codes, weights=d, minlength=k)
        sizes = np.bincount(codes, minlength=k)
        boots = np.empty(n_boot)
        for b in range(n_boot):
            pick = rng.integers(0, k, k)
            boots[b] = sums[pick].sum() / sizes[pick].sum()
        n_clusters = k
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"metric": metric, "difference": float(d.mean()), "ci95_low": float(lo), "ci95_high": float(hi),
            "share_bootstrap_model_better": float((boots < 0).mean()), "n_boot": n_boot,
            "resampling_unit": "single game" if clusters is None else "series (cluster bootstrap)",
            "n_units": int(n_clusters)}


def breakdown(df: pd.DataFrame, by: str, prob_cols: dict[str, str], y_col: str = "blue_won",
              min_n: int = 30) -> list[dict]:
    rows = []
    for key, g in df.groupby(by, sort=True):
        if len(g) < min_n:
            continue
        row = {by: str(key), "n": int(len(g))}
        for name, col in prob_cols.items():
            row[f"{name}_brier"] = brier(g[y_col], g[col])
            row[f"{name}_accuracy"] = float(((g[col] >= 0.5).astype(int) == g[y_col]).mean())
        rows.append(row)
    return rows
