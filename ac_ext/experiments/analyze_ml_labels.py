"""Analyze ML training data label distribution for failure classification."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze ML label distribution")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parent / "out" / "ml_training_data_case118.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rows = list(csv.DictReader(open(args.input, encoding="utf-8")))
    n = len(rows)
    print(f"Total samples: {n}")

    n_success = sum(1 for r in rows if r["success"] == "True")
    n_fail_success = n - n_success
    print(f"\nsuccess == True: {n_success} ({n_success/n*100:.1f}%)")
    print(f"success == False: {n_fail_success} ({n_fail_success/n*100:.1f}%)")

    n_inf = sum(1 for r in rows if r["s_any"] == "inf")
    n_neg_inf = sum(1 for r in rows if r["s_any"] == "-inf")
    finite_vals = [float(r["s_any"]) for r in rows if r["s_any"] not in ("inf", "-inf")]
    n_finite = len(finite_vals)
    print(f"\ns_any == +inf: {n_inf} ({n_inf/n*100:.1f}%)")
    print(f"s_any == -inf: {n_neg_inf} ({n_neg_inf/n*100:.1f}%)")
    print(f"s_any finite:  {n_finite} ({n_finite/n*100:.1f}%)")

    if finite_vals:
        arr = np.array(finite_vals)
        print(f"\nFinite s_any stats:")
        print(f"  min:  {arr.min():.6e}")
        print(f"  max:  {arr.max():.6e}")
        print(f"  mean: {arr.mean():.6e}")
        print(f"  std:  {arr.std():.6e}")
        for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
            print(f"  p{p:02d}:  {np.percentile(arr, p):.6e}")

    # fail label: 1 if s_any == inf or success == False, else 0
    labels = []
    for r in rows:
        fail = 1 if (r["s_any"] == "inf" or r["success"] != "True") else 0
        labels.append(fail)
    labels = np.array(labels)
    n_fail = int(labels.sum())
    n_safe = n - n_fail
    print(f"\n=== Fail Label Distribution ===")
    print(f"  fail=1: {n_fail} ({n_fail/n*100:.1f}%)")
    print(f"  fail=0: {n_safe} ({n_safe/n*100:.1f}%)")

    print(f"\n=== Stratified by seed x line_outage_prob ===")
    print(f"{'seed':>6} {'lop':>8} {'n':>6} {'fail':>6} {'rate':>8}")
    cohorts = sorted({(int(r["seed"]), float(r["line_outage_prob"])) for r in rows})
    for seed, lop in cohorts:
        subset = [
            1 if (r["s_any"] == "inf" or r["success"] != "True") else 0
            for r in rows
            if int(r["seed"]) == seed and float(r["line_outage_prob"]) == lop
        ]
        n_sub = len(subset)
        f_sub = sum(subset)
        print(f"{seed:>6} {lop:>8.3f} {n_sub:>6} {f_sub:>6} {f_sub/n_sub*100:>7.1f}%")

    # Summary by lop
    print(f"\n=== Summary by line_outage_prob ===")
    print(f"{'lop':>8} {'n':>6} {'fail':>6} {'rate':>8}")
    for lop in sorted(set(float(r["line_outage_prob"]) for r in rows)):
        subset = [
            1 if (r["s_any"] == "inf" or r["success"] != "True") else 0
            for r in rows
            if float(r["line_outage_prob"]) == lop
        ]
        n_sub = len(subset)
        f_sub = sum(subset)
        print(f"{lop:>8.3f} {n_sub:>6} {f_sub:>6} {f_sub/n_sub*100:>7.1f}%")


if __name__ == "__main__":
    main()
