"""Proxy-vs-truth diagnostics for single-case damaged-state samples.

Phase-5 helper script:
- samples damaged states once,
- evaluates truth and proxy per state,
- writes per-state CSV,
- prints rank/correlation diagnostics,
- saves two matplotlib figures.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import matplotlib.pyplot as plt

from ac_ext.config import DEFAULTS
from ac_ext.problem import eval_proxy, eval_single_damaged_case, sample_X


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run proxy diagnostics on damaged AC states.")
    parser.add_argument("--case", dest="case_name", default="case14")
    parser.add_argument("--N", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--truth", choices=("acopf", "acpf", "dcpf"), default="acopf")
    parser.add_argument("--proxy", choices=("dcpf", "fdxb"), default="dcpf")
    parser.add_argument("--line-outage-prob", type=float, default=None)
    parser.add_argument("--bus-outage-prob", type=float, default=None)
    parser.add_argument("--outdir", default="ac_ext/outputs/proxy_diagnostics")
    return parser.parse_args()


def _merged_config(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if args.line_outage_prob is not None:
        cfg["line_outage_prob"] = float(args.line_outage_prob)
    if args.bus_outage_prob is not None:
        cfg["bus_outage_prob"] = float(args.bus_outage_prob)
    return cfg


def _extract_scalar_payload(payload: Mapping[str, Any]) -> Dict[str, float | bool]:
    required = ("success", "s_line", "s_volt", "s_any")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"Missing scalar fields in payload: {missing}")
    return {
        "success": bool(payload["success"]),
        "s_line": float(payload["s_line"]),
        "s_volt": float(payload["s_volt"]),
        "s_any": float(payload["s_any"]),
    }


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs)
    den_y = sum((y - mean_y) ** 2 for y in ys)
    if den_x <= 0.0 or den_y <= 0.0:
        return None
    return num / math.sqrt(den_x * den_y)


def _average_ranks(values: Sequence[float]) -> List[float]:
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = ((i + 1) + (j + 1)) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return _pearson(_average_ranks(xs), _average_ranks(ys))


def _topk_overlap_jaccard(truth_scores: Sequence[float], proxy_scores: Sequence[float]) -> Dict[str, float | int]:
    n = len(truth_scores)
    if n == 0:
        return {"k": 0, "overlap": 0, "overlap_rate": 0.0, "jaccard": 0.0}

    k = max(1, int(math.ceil(0.1 * n)))
    truth_top = set(sorted(range(n), key=lambda i: truth_scores[i], reverse=True)[:k])
    proxy_top = set(sorted(range(n), key=lambda i: proxy_scores[i], reverse=True)[:k])

    overlap = len(truth_top.intersection(proxy_top))
    union = len(truth_top.union(proxy_top))

    return {
        "k": k,
        "overlap": overlap,
        "overlap_rate": overlap / float(k),
        "jaccard": overlap / float(union) if union > 0 else 0.0,
    }


def _quantile_bucket_summary(proxy_scores: Sequence[float], truth_scores: Sequence[float], buckets: int = 10) -> List[Dict[str, Any]]:
    n = len(proxy_scores)
    if n == 0:
        return []

    order = sorted(range(n), key=lambda i: proxy_scores[i])
    rows: List[Dict[str, Any]] = []

    for b in range(buckets):
        start = (b * n) // buckets
        end = ((b + 1) * n) // buckets
        if end <= start:
            continue

        idx = order[start:end]
        pvals = [proxy_scores[i] for i in idx]
        tvals = [truth_scores[i] for i in idx]

        finite_truth = [v for v in tvals if math.isfinite(v)]
        truth_mean = statistics.fmean(finite_truth) if finite_truth else None

        rows.append(
            {
                "bucket": b + 1,
                "count": len(idx),
                "proxy_min": min(pvals),
                "proxy_max": max(pvals),
                "truth_mean": truth_mean,
            }
        )

    return rows


def _write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    fieldnames = [
        "state_id",
        "truth_success",
        "truth_s_line",
        "truth_s_volt",
        "truth_s_any",
        "proxy_success",
        "proxy_s_line",
        "proxy_s_volt",
        "proxy_s_any",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _plot_scatter(path: Path, truth_scores: Sequence[float], proxy_scores: Sequence[float]) -> None:
    finite_pairs = [(t, p) for t, p in zip(truth_scores, proxy_scores) if math.isfinite(t) and math.isfinite(p)]

    plt.figure(figsize=(7, 6))
    if finite_pairs:
        tx = [t for t, _ in finite_pairs]
        px = [p for _, p in finite_pairs]
        plt.scatter(tx, px, alpha=0.6, s=18)
        low = min(min(tx), min(px))
        high = max(max(tx), max(px))
        plt.plot([low, high], [low, high], linestyle="--")
    else:
        plt.text(0.5, 0.5, "No finite score pairs", ha="center", va="center")

    plt.xlabel("truth_s_any")
    plt.ylabel("proxy_s_any")
    plt.title("Truth vs Proxy (s_any)")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _plot_quantile_means(path: Path, bucket_summary: Sequence[Mapping[str, Any]]) -> None:
    xs = [int(row["bucket"]) for row in bucket_summary]
    ys = [float("nan") if row["truth_mean"] is None else float(row["truth_mean"]) for row in bucket_summary]

    plt.figure(figsize=(8, 4.5))
    plt.plot(xs, ys, marker="o")
    plt.xlabel("Proxy quantile bucket (1=lowest risk)")
    plt.ylabel("Mean truth_s_any")
    plt.title("Proxy quantile vs truth mean")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def main() -> None:
    args = _parse_args()
    config = _merged_config(args)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    states = sample_X(args.case_name, config=config, n=args.N, seed=args.seed)
    if not isinstance(states, list):
        states = list(states)

    csv_rows: List[Dict[str, Any]] = []
    truth_any: List[float] = []
    proxy_any: List[float] = []

    for i, state in enumerate(states):
        bundle = eval_single_damaged_case(args.case_name, state, config, debug=False)
        if args.truth not in bundle:
            raise ValueError(f"Truth mode '{args.truth}' is unavailable.")

        truth = _extract_scalar_payload(bundle[args.truth])

        if args.proxy in bundle:
            proxy = _extract_scalar_payload(bundle[args.proxy])
        else:
            proxy_request = {
                "case_name": args.case_name,
                "state": state,
                "mode": args.proxy,
            }
            proxy_result = eval_proxy(
                args.case_name,
                state,
                config,
                proxy_mode=args.proxy,
            )
            if isinstance(proxy_result, Mapping) and args.proxy in proxy_result and isinstance(proxy_result[args.proxy], Mapping):
                proxy_result = proxy_result[args.proxy]
            proxy = _extract_scalar_payload(proxy_result)


        truth_any.append(float(truth["s_any"]))
        proxy_any.append(float(proxy["s_any"]))

        csv_rows.append(
            {
                "state_id": i,
                "truth_success": truth["success"],
                "truth_s_line": truth["s_line"],
                "truth_s_volt": truth["s_volt"],
                "truth_s_any": truth["s_any"],
                "proxy_success": proxy["success"],
                "proxy_s_line": proxy["s_line"],
                "proxy_s_volt": proxy["s_volt"],
                "proxy_s_any": proxy["s_any"],
            }
        )

    csv_path = outdir / "proxy_diagnostics.csv"
    scatter_path = outdir / "truth_vs_proxy_scatter.png"
    quantile_plot_path = outdir / "proxy_quantile_truth_mean.png"

    _write_csv(csv_path, csv_rows)

    finite_pairs = [(t, p) for t, p in zip(truth_any, proxy_any) if math.isfinite(t) and math.isfinite(p)]
    finite_truth = [t for t, _ in finite_pairs]
    finite_proxy = [p for _, p in finite_pairs]

    pearson = _pearson(finite_truth, finite_proxy)
    spearman = _spearman(finite_truth, finite_proxy)
    overlap = _topk_overlap_jaccard(truth_any, proxy_any)
    bucket_summary = _quantile_bucket_summary(proxy_any, truth_any, buckets=10)

    _plot_scatter(scatter_path, truth_any, proxy_any)
    _plot_quantile_means(quantile_plot_path, bucket_summary)

    summary = {
        "case": args.case_name,
        "N": args.N,
        "seed": args.seed,
        "truth": args.truth,
        "proxy": args.proxy,
        "pearson_s_any": pearson,
        "spearman_s_any": spearman,
        "top10pct": overlap,
        "quantile_buckets": bucket_summary,
        "finite_pair_count": len(finite_pairs),
        "csv_path": str(csv_path),
        "scatter_path": str(scatter_path),
        "quantile_plot_path": str(quantile_plot_path),
    }

    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
