"""Train XGBoost surrogate and evaluate Rank Consistency."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train ML surrogate for Level 0 proxy")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parent / "out" / "ml_training_data_case118.csv"),
    )
    parser.add_argument(
        "--output-model",
        default=str(Path(__file__).resolve().parent / "out" / "ml_surrogate_case118.joblib"),
    )
    parser.add_argument(
        "--output-eval",
        default=str(Path(__file__).resolve().parent / "out" / "ml_surrogate_eval_case118.json"),
    )
    parser.add_argument("--test-seeds", nargs="+", type=int, default=[300])
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--tail-weight-percentile", type=float, default=90.0)
    parser.add_argument("--tail-weight-multiplier", type=float, default=10.0)
    return parser.parse_args()


def _load_data(path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y, seeds, line_outage_probs) from training CSV."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    X_list: List[List[float]] = []
    y_list: List[float] = []
    seed_list: List[int] = []
    lop_list: List[float] = []

    for row in rows:
        line_out = json.loads(row["line_out_json"])
        bus_out = json.loads(row["bus_out_json"])
        gen_scale = json.loads(row["gen_scale_json"])
        features = [float(v) for v in line_out] + [float(v) for v in bus_out] + [float(v) for v in gen_scale]
        X_list.append(features)
        seed_list.append(int(row["seed"]))
        lop_list.append(float(row["line_outage_prob"]))

        s_any = row["s_any"]
        if s_any == "inf":
            y_list.append(np.nan)
        else:
            y_list.append(float(s_any))

    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.float64),
        np.array(seed_list, dtype=np.int64),
        np.array(lop_list, dtype=np.float64),
    )


def _rank_consistency(y_true: np.ndarray, y_pred: np.ndarray, k: int, m: int) -> float:
    """Fraction of true Top-K that appear in predicted Top-M."""
    if k <= 0 or m <= 0:
        return float("nan")
    true_topk = set(np.argsort(y_true)[::-1][:k])
    pred_topm = set(np.argsort(y_pred)[::-1][:m])
    return len(true_topk & pred_topm) / k


def _cohort_rank_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    seeds: np.ndarray,
    line_outage_probs: np.ndarray,
) -> list[Dict[str, float]]:
    """Evaluate rank consistency on benchmark-like 1000-sample cohorts."""
    rows: list[Dict[str, float]] = []
    cohorts = sorted({(int(seed), float(lop)) for seed, lop in zip(seeds, line_outage_probs)})
    for seed, lop in cohorts:
        mask = (seeds == seed) & np.isclose(line_outage_probs, lop)
        cohort_true = y_true[mask]
        cohort_pred = y_pred[mask]
        if len(cohort_true) == 0:
            continue
        k = min(150, len(cohort_true))
        m = min(200, len(cohort_true))
        rows.append(
            {
                "seed": seed,
                "line_outage_prob": lop,
                "n_samples": int(len(cohort_true)),
                "rank_consistency_150_200": float(
                    _rank_consistency(cohort_true, cohort_pred, k, m)
                ),
            }
        )
    return rows


def main() -> None:
    args = _parse_args()
    print(f"Loading data from {args.input}")
    X, y_raw, seeds, line_outage_probs = _load_data(args.input)
    print(f"  total samples: {len(X)}")

    finite_mask = np.isfinite(y_raw)
    n_inf = int(np.sum(~finite_mask))
    print(f"  inf samples: {n_inf}")

    if finite_mask.any():
        cap_value = float(np.nanmax(y_raw[finite_mask]) * 2.0)
    else:
        cap_value = 1e6
    y = np.where(finite_mask, y_raw, cap_value)
    print(f"  cap_value for inf: {cap_value:.4f}")

    test_seed_set = set(args.test_seeds)
    train_mask = np.array([s not in test_seed_set for s in seeds])
    test_mask = ~train_mask

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    test_seeds = seeds[test_mask]
    test_lops = line_outage_probs[test_mask]
    print(f"  train: {len(X_train)}, test: {len(X_test)}")

    if len(X_train) == 0 or len(X_test) == 0:
        print("ERROR: empty train or test split")
        sys.exit(1)

    p_thresh = np.percentile(y_train, args.tail_weight_percentile)
    weights = np.where(y_train > p_thresh, args.tail_weight_multiplier, 1.0)
    print(f"  tail threshold (p{args.tail_weight_percentile:.0f}): {p_thresh:.4f}")
    print(f"  tail samples in train: {int(np.sum(y_train > p_thresh))}")

    import xgboost as xgb

    model = xgb.XGBRegressor(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="reg:squarederror",
        tree_method="hist",
        random_state=42,
        verbosity=1,
    )
    print("Training XGBoost ...")
    model.fit(X_train, y_train, sample_weight=weights)

    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    from scipy.stats import spearmanr

    n_test = len(y_test)
    k_150 = min(150, n_test)
    m_200 = min(200, n_test)

    rc_150_200 = _rank_consistency(y_test, y_pred_test, k_150, m_200)
    rc_150_300 = _rank_consistency(y_test, y_pred_test, k_150, min(300, n_test))
    cohort_metrics = _cohort_rank_metrics(y_test, y_pred_test, test_seeds, test_lops)
    cohort_rc_values = [row["rank_consistency_150_200"] for row in cohort_metrics]
    cohort_rc_mean = float(np.mean(cohort_rc_values)) if cohort_rc_values else None
    cohort_rc_min = float(np.min(cohort_rc_values)) if cohort_rc_values else None
    spearman_test, _ = spearmanr(y_test, y_pred_test)
    spearman_train, _ = spearmanr(y_train, y_pred_train)

    mae_test = float(np.mean(np.abs(y_test - y_pred_test)))
    mae_train = float(np.mean(np.abs(y_train - y_pred_train)))

    test_finite = np.isfinite(y_raw[test_mask])
    test_y_raw = y_raw[test_mask]
    if test_finite.any():
        finite_vals = test_y_raw[test_finite]
        median_val = float(np.median(finite_vals))
        p95_val = float(np.percentile(finite_vals, 95))
    else:
        median_val = 0.0
        p95_val = 0.0

    low_mask = y_test <= median_val
    mid_mask = (y_test > median_val) & (y_test <= p95_val)
    high_mask = y_test > p95_val

    mae_low = float(np.mean(np.abs(y_test[low_mask] - y_pred_test[low_mask]))) if low_mask.any() else None
    mae_mid = float(np.mean(np.abs(y_test[mid_mask] - y_pred_test[mid_mask]))) if mid_mask.any() else None
    mae_high = float(np.mean(np.abs(y_test[high_mask] - y_pred_test[high_mask]))) if high_mask.any() else None

    eval_results = {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_inf_total": n_inf,
        "cap_value": cap_value,
        "test_seeds": args.test_seeds,
        "rank_consistency_150_200": rc_150_200,
        "rank_consistency_150_300": rc_150_300,
        "cohort_rank_metrics": cohort_metrics,
        "cohort_rank_consistency_150_200_mean": cohort_rc_mean,
        "cohort_rank_consistency_150_200_min": cohort_rc_min,
        "spearman_test": float(spearman_test),
        "spearman_train": float(spearman_train),
        "mae_test": mae_test,
        "mae_train": mae_train,
        "mae_test_low": mae_low,
        "mae_test_mid": mae_mid,
        "mae_test_high": mae_high,
        "tail_weight_percentile": args.tail_weight_percentile,
        "tail_weight_multiplier": args.tail_weight_multiplier,
        "xgb_n_estimators": args.n_estimators,
        "xgb_max_depth": args.max_depth,
        "xgb_learning_rate": args.learning_rate,
    }

    print("\n=== Evaluation ===")
    for key, value in eval_results.items():
        print(f"  {key}: {value}")

    passed = bool(cohort_rc_values) and min(cohort_rc_values) >= 0.80
    eval_results["rank_consistency_passed"] = passed
    print(
        "\n  PASS: "
        f"{passed}  (threshold: min cohort rank_consistency_150_200 >= 0.80)"
    )

    model_path = Path(args.output_model).resolve()
    eval_path = Path(args.output_eval).resolve()
    model_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, model_path)
    print(f"\nModel saved: {model_path}")

    with eval_path.open("w", encoding="utf-8") as file_obj:
        json.dump(eval_results, file_obj, indent=2)
    print(f"Eval saved: {eval_path}")


if __name__ == "__main__":
    main()
