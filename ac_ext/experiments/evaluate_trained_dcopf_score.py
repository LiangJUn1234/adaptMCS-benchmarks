#!/usr/bin/env python3
"""Offline evaluation for A2-trained DCOPF score parameters."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from ac_ext.experiments.analyze_dcopf_flow_scores import (  # noqa: E402
    build_truth_fail_label,
    compute_abs_flow,
    compute_continuous_flow_score,
    compute_raw_success_fail_score,
    load_truth_csv,
)
from ac_ext.experiments.train_dcopf_score_parameters import (  # noqa: E402
    DEFAULT_EXPAND_FACTOR,
    DEFAULT_K_INITIAL,
    DEFAULT_MAX_EXPAND_ROUNDS,
    DEFAULT_TAIL_AUDIT,
    append_metric_rows,
    evaluate_subset,
    write_csv,
)


def parse_int_list(raw: str) -> tuple[int, ...]:
    values = []
    for part in raw.split(","):
        item = part.strip()
        if item:
            values.append(int(item))
    if not values:
        raise ValueError("expected at least one integer")
    return tuple(values)


def build_score_from_payload(
    *,
    method_family: str,
    parameters: dict[str, Any] | None,
    success: np.ndarray,
    abs_flow: np.ndarray,
) -> tuple[np.ndarray, int]:
    if method_family == "raw_success_fail":
        return compute_raw_success_fail_score(success), 0
    if not parameters:
        raise ValueError(f"missing parameters for method_family={method_family}")
    pseudo_limit = np.asarray(parameters["pseudo_limit"], dtype=np.float64)
    return compute_continuous_flow_score(
        success=success,
        abs_flow=abs_flow,
        pseudo_limit=pseudo_limit,
    )


def build_report(
    *,
    params_path: Path,
    eval_seeds: tuple[int, ...],
    records: list[dict[str, Any]],
) -> str:
    lines = [
        "# A2 DCOPF Score Evaluation",
        "",
        f"- params: `{params_path}`",
        f"- eval seeds: `{','.join(str(x) for x in eval_seeds)}`",
        "- note: if multiple line-outage probabilities are mixed in one eval split, the global failure-label guard row is a pooled diagnostic only.",
        "- the per-lop rows are the benchmark-relevant view for Level-0 screening.",
        "",
        "## Candidates",
        "",
    ]
    for record in records:
        global_row = next(row for row in record["rows"] if row["split"] == "eval_global")
        lines.extend(
            [
                f"### {record['score_name']}",
                f"- method family: `{record['method_family']}`",
                f"- AUROC: `{global_row['AUROC']:.4f}`",
                f"- AUPRC: `{global_row['AUPRC']:.4f}`",
                f"- top200_recall: `{global_row['top200_recall']:.4f}`",
                f"- K_final: `{global_row['K_final']}`",
                f"- l0_truth_calls: `{global_row['l0_truth_calls']}`",
                f"- tail_audit_failure_hits: `{global_row['tail_audit_failure_hits']}`",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--npz",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_flow_features_case118.npz"),
    )
    parser.add_argument(
        "--truth-csv",
        type=Path,
        default=Path("ac_ext/experiments/out/ml_training_data_case118.csv"),
    )
    parser.add_argument(
        "--params",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_score_params_case118_v001.json"),
    )
    parser.add_argument("--eval-seeds", type=parse_int_list, default=(300,))
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("ac_ext/experiments/out/dcopf_score_eval_case118_v001_val300"),
    )
    parser.add_argument("--k-initial", type=int, default=DEFAULT_K_INITIAL)
    parser.add_argument("--tail-audit", type=int, default=DEFAULT_TAIL_AUDIT)
    parser.add_argument("--expand-factor", type=float, default=DEFAULT_EXPAND_FACTOR)
    parser.add_argument("--max-expand-rounds", type=int, default=DEFAULT_MAX_EXPAND_ROUNDS)
    args = parser.parse_args()

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    summary_csv = out_prefix.with_name(out_prefix.name + "_summary.csv")
    per_lop_csv = out_prefix.with_name(out_prefix.name + "_per_lop.csv")
    report_md = out_prefix.with_name(out_prefix.name + "_report.md")

    payload = json.loads(args.params.read_text(encoding="utf-8"))
    d = np.load(args.npz)
    truth = load_truth_csv(args.truth_csv)

    sample_id = np.asarray(d["sample_id"], dtype=np.int64)
    seed_arr = np.asarray(d["seed"], dtype=np.int64)
    lop_arr = np.asarray(d["line_outage_prob"], dtype=np.float64)
    if not np.array_equal(sample_id, truth["sample_id"]):
        raise ValueError("sample_id mismatch between NPZ and truth CSV")
    if not np.array_equal(seed_arr, truth["seed"]):
        raise ValueError("seed mismatch between NPZ and truth CSV")
    if not np.allclose(lop_arr, truth["line_outage_prob"]):
        raise ValueError("line_outage_prob mismatch between NPZ and truth CSV")

    success = np.asarray(d["dcopf_success"], dtype=bool)
    abs_flow = compute_abs_flow(
        pf=np.asarray(d["PF"], dtype=np.float64),
        pt=np.asarray(d["PT"], dtype=np.float64),
        branch_status=np.asarray(d["branch_status"], dtype=bool),
    )
    truth_fail_label = build_truth_fail_label(
        np.asarray(truth["truth_success"], dtype=bool),
        np.asarray(truth["truth_s_any"], dtype=np.float64),
    )

    eval_mask = np.isin(seed_arr, np.asarray(args.eval_seeds, dtype=np.int64))
    if not np.any(eval_mask):
        raise ValueError("evaluation split is empty")

    candidate_payloads = [payload["best_overall"], payload["best_trained_physics"]]
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    per_lop_rows: list[dict[str, Any]] = []

    for item in candidate_payloads:
        score_name = str(item["score_name"])
        if score_name in seen:
            continue
        seen.add(score_name)
        method_family = str(item["method_family"])
        parameters = item.get("parameters")
        score, bad = build_score_from_payload(
            method_family=method_family,
            parameters=parameters,
            success=success,
            abs_flow=abs_flow,
        )
        rows_global = evaluate_subset(
            subset_name="eval_global",
            score=score,
            fail_label=truth_fail_label,
            line_outage_prob=lop_arr,
            mask=eval_mask,
            topk_values=(50, 100, 200, 500),
            k_initial=args.k_initial,
            tail_audit=args.tail_audit,
            expand_factor=args.expand_factor,
            max_expand_rounds=args.max_expand_rounds,
            per_lop=False,
        )
        rows_lop = evaluate_subset(
            subset_name="eval_per_lop",
            score=score,
            fail_label=truth_fail_label,
            line_outage_prob=lop_arr,
            mask=eval_mask,
            topk_values=(50, 100, 200, 500),
            k_initial=args.k_initial,
            tail_audit=args.tail_audit,
            expand_factor=args.expand_factor,
            max_expand_rounds=args.max_expand_rounds,
            per_lop=True,
        )
        merged_rows = rows_global + rows_lop
        for row in merged_rows:
            row_out = {
                "score_name": score_name,
                "method_family": method_family,
                "n_bad_success_flow_score": int(bad),
            }
            row_out.update(row)
            if row["split"] == "eval_global":
                summary_rows.append(row_out)
            else:
                per_lop_rows.append(row_out)
        records.append(
            {
                "score_name": score_name,
                "method_family": method_family,
                "rows": merged_rows,
            }
        )

    write_csv(summary_csv, summary_rows)
    write_csv(per_lop_csv, per_lop_rows)
    report_md.write_text(
        build_report(params_path=args.params, eval_seeds=args.eval_seeds, records=records),
        encoding="utf-8",
    )

    print(f"wrote summary: {summary_csv}")
    print(f"wrote per_lop: {per_lop_csv}")
    print(f"wrote report: {report_md}")


if __name__ == "__main__":
    main()
