"""Train XGBoost failure classifier and evaluate recall metrics."""

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
    parser = argparse.ArgumentParser(description="Train ML failure classifier")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parent / "out" / "ml_training_data_case118.csv"),
    )
    parser.add_argument(
        "--output-model",
        default=str(Path(__file__).resolve().parent / "out" / "ml_failure_classifier_case118.joblib"),
    )
    parser.add_argument(
        "--output-eval",
        default=str(Path(__file__).resolve().parent / "out" / "ml_failure_classifier_eval_case118.json"),
    )
    parser.add_argument("--test-seeds", nargs="+", type=int, default=[300])
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    return parser.parse_args()


def _load_data(path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y_fail, seeds, line_outage_probs) from training CSV."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    X_list: List[List[float]] = []
    y_list: List[int] = []
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

        fail = 1 if (row["s_any"] == "inf" or row["success"] != "True") else 0
        y_list.append(fail)

    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.int32),
        np.array(seed_list, dtype=np.int64),
        np.array(lop_list, dtype=np.float64),
    )


def _topk_recall(y_true: np.ndarray, y_prob: np.ndarray, k: int) -> float:
    """Among the top-K predicted-most-likely failures, what fraction are actual failures."""
    if k <= 0 or len(y_true) == 0:
        return float("nan")
    n_true_fail = int(y_true.sum())
    if n_true_fail == 0:
        return float("nan")
    top_k_idx = np.argsort(y_prob)[::-1][:k]
    recalled = int(y_true[top_k_idx].sum())
    return recalled / n_true_fail


def _cohort_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    seeds: np.ndarray,
    lops: np.ndarray,
) -> list[Dict]:
    """Per-cohort (seed x lop) metrics."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    results = []
    cohorts = sorted({(int(s), float(l)) for s, l in zip(seeds, lops)})
    for seed, lop in cohorts:
        mask = (seeds == seed) & np.isclose(lops, lop)
        yt = y_true[mask]
        yp = y_prob[mask]
        n_total = len(yt)
        n_fail = int(yt.sum())

        row: Dict = {
            "seed": seed,
            "line_outage_prob": lop,
            "n_samples": n_total,
            "n_fail": n_fail,
            "fail_rate": n_fail / n_total if n_total > 0 else 0.0,
        }

        if n_fail > 0 and n_fail < n_total:
            row["auroc"] = float(roc_auc_score(yt, yp))
            row["auprc"] = float(average_precision_score(yt, yp))
        else:
            row["auroc"] = None
            row["auprc"] = None

        for k in [50, 100, 200]:
            row[f"top{k}_recall"] = float(_topk_recall(yt, yp, min(k, n_total)))

        results.append(row)
    return results


def main() -> None:
    args = _parse_args()
    print(f"Loading data from {args.input}")
    X, y, seeds, lops = _load_data(args.input)
    n_fail = int(y.sum())
    n_safe = len(y) - n_fail
    print(f"  total: {len(X)}, fail: {n_fail} ({n_fail/len(y)*100:.1f}%), safe: {n_safe}")

    test_seed_set = set(args.test_seeds)
    train_mask = np.array([s not in test_seed_set for s in seeds])
    test_mask = ~train_mask

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    test_seeds = seeds[test_mask]
    test_lops = lops[test_mask]

    n_train_fail = int(y_train.sum())
    n_test_fail = int(y_test.sum())
    print(f"  train: {len(X_train)} (fail={n_train_fail}), test: {len(X_test)} (fail={n_test_fail})")

    if len(X_train) == 0 or len(X_test) == 0:
        print("ERROR: empty train or test split")
        sys.exit(1)

    scale_pos_weight = float(n_safe) / max(n_fail, 1)
    print(f"  scale_pos_weight: {scale_pos_weight:.2f}")

    import xgboost as xgb

    model = xgb.XGBClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        scale_pos_weight=scale_pos_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="aucpr",
        tree_method="hist",
        random_state=42,
        verbosity=1,
    )
    print("Training XGBoost classifier ...")
    model.fit(X_train, y_train)

    y_prob_train = model.predict_proba(X_train)[:, 1]
    y_prob_test = model.predict_proba(X_test)[:, 1]

    from sklearn.metrics import average_precision_score, roc_auc_score

    auroc_test = float(roc_auc_score(y_test, y_prob_test)) if n_test_fail > 0 and n_test_fail < len(y_test) else None
    auprc_test = float(average_precision_score(y_test, y_prob_test)) if n_test_fail > 0 and n_test_fail < len(y_test) else None
    auroc_train = float(roc_auc_score(y_train, y_prob_train)) if n_train_fail > 0 and n_train_fail < len(y_train) else None
    auprc_train = float(average_precision_score(y_train, y_prob_train)) if n_train_fail > 0 and n_train_fail < len(y_train) else None

    cohort_results = _cohort_metrics(y_test, y_prob_test, test_seeds, test_lops)

    eval_results = {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_train_fail": n_train_fail,
        "n_test_fail": n_test_fail,
        "test_seeds": args.test_seeds,
        "scale_pos_weight": scale_pos_weight,
        "auroc_test": auroc_test,
        "auprc_test": auprc_test,
        "auroc_train": auroc_train,
        "auprc_train": auprc_train,
        "top50_recall_test": float(_topk_recall(y_test, y_prob_test, 50)),
        "top100_recall_test": float(_topk_recall(y_test, y_prob_test, 100)),
        "top200_recall_test": float(_topk_recall(y_test, y_prob_test, 200)),
        "cohort_metrics": cohort_results,
        "xgb_n_estimators": args.n_estimators,
        "xgb_max_depth": args.max_depth,
        "xgb_learning_rate": args.learning_rate,
    }

    print("\n=== Evaluation ===")
    print(f"  AUROC test:  {auroc_test}")
    print(f"  AUPRC test:  {auprc_test}")
    print(f"  AUROC train: {auroc_train}")
    print(f"  AUPRC train: {auprc_train}")
    print(f"  Top-50  recall (test): {eval_results['top50_recall_test']:.4f}")
    print(f"  Top-100 recall (test): {eval_results['top100_recall_test']:.4f}")
    print(f"  Top-200 recall (test): {eval_results['top200_recall_test']:.4f}")

    print(f"\n=== Cohort Metrics ===")
    print(f"{'seed':>6} {'lop':>8} {'n':>6} {'fail':>6} {'auroc':>8} {'auprc':>8} {'top50':>8} {'top100':>8} {'top200':>8}")
    for c in cohort_results:
        print(
            f"{c['seed']:>6} {c['line_outage_prob']:>8.3f} {c['n_samples']:>6} {c['n_fail']:>6} "
            f"{str(c.get('auroc', 'N/A') or 'N/A'):>8} "
            f"{str(c.get('auprc', 'N/A') or 'N/A'):>8} "
            f"{c['top50_recall']:>8.3f} {c['top100_recall']:>8.3f} {c['top200_recall']:>8.3f}"
        )

    model_path = Path(args.output_model).resolve()
    eval_path = Path(args.output_eval).resolve()
    model_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, model_path)
    print(f"\nModel saved: {model_path}")

    with eval_path.open("w", encoding="utf-8") as fh:
        json.dump(eval_results, fh, indent=2)
    print(f"Eval saved: {eval_path}")


if __name__ == "__main__":
    main()
