#!/usr/bin/env python3
"""Audit empirical DCOPF-failure certificate quality against ACOPF failure labels."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


TRAIN_SEEDS = {7, 42, 100, 200}
VAL_SEEDS = {300}
UNSEEN_SEEDS = {901, 902, 903}


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return False


def parse_float(value: Any) -> float:
    text = str(value).strip().lower()
    if text in {"inf", "+inf", "infinity", "+infinity"}:
        return float("inf")
    if text in {"-inf", "-infinity"}:
        return float("-inf")
    return float(value)


def wilson_interval(success: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    phat = success / float(total)
    denom = 1.0 + (z * z) / total
    center = (phat + (z * z) / (2.0 * total)) / denom
    spread = (z / denom) * math.sqrt((phat * (1.0 - phat) / total) + (z * z) / (4.0 * total * total))
    lo = max(0.0, center - spread)
    hi = min(1.0, center + spread)
    return lo, hi


def safe_ratio(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return num / float(den)


def split_name(seed: int) -> str:
    if seed in TRAIN_SEEDS:
        return "train"
    if seed in VAL_SEEDS:
        return "validation"
    if seed in UNSEEN_SEEDS:
        return "unseen"
    return "other"


def init_counter() -> dict[str, int]:
    return {
        "n_total": 0,
        "acopf_failed_count": 0,
        "dcopf_failed_count": 0,
        "dcopf_success_count": 0,
        "true_certificate_count": 0,
        "false_certificate_count": 0,
        "missed_acopf_failure_count": 0,
        "safe_success_count": 0,
    }


def update_counter(counter: dict[str, int], *, ac_fail: bool, dc_fail: bool) -> None:
    counter["n_total"] += 1
    if ac_fail:
        counter["acopf_failed_count"] += 1
    if dc_fail:
        counter["dcopf_failed_count"] += 1
    else:
        counter["dcopf_success_count"] += 1
    if dc_fail and ac_fail:
        counter["true_certificate_count"] += 1
    if dc_fail and (not ac_fail):
        counter["false_certificate_count"] += 1
    if ac_fail and (not dc_fail):
        counter["missed_acopf_failure_count"] += 1
    if (not dc_fail) and (not ac_fail):
        counter["safe_success_count"] += 1


def finalize_metrics(counter: dict[str, int]) -> dict[str, Any]:
    n_total = int(counter["n_total"])
    ac_fail = int(counter["acopf_failed_count"])
    dc_fail = int(counter["dcopf_failed_count"])
    true_cert = int(counter["true_certificate_count"])
    false_cert = int(counter["false_certificate_count"])
    missed = int(counter["missed_acopf_failure_count"])

    p_ac_given_dc = safe_ratio(true_cert, dc_fail)
    p_dc_given_ac = safe_ratio(true_cert, ac_fail)
    false_rate = safe_ratio(false_cert, dc_fail)
    missed_rate = safe_ratio(missed, ac_fail)
    p_ci_lo, p_ci_hi = wilson_interval(true_cert, dc_fail)
    f_ci_lo, f_ci_hi = wilson_interval(false_cert, dc_fail)

    return {
        **counter,
        "P_acopf_fail_given_dcopf_fail": p_ac_given_dc,
        "P_dcopf_fail_given_acopf_fail": p_dc_given_ac,
        "false_certificate_rate": false_rate,
        "missed_failure_rate": missed_rate,
        "P_acopf_fail_given_dcopf_fail_wilson_lo": p_ci_lo,
        "P_acopf_fail_given_dcopf_fail_wilson_hi": p_ci_hi,
        "false_certificate_rate_wilson_lo": f_ci_lo,
        "false_certificate_rate_wilson_hi": f_ci_hi,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(v: Any, nd: int = 6) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, str):
        return v
    x = float(v)
    if math.isnan(x):
        return "N/A"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return f"{x:.{nd}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--npz", type=Path, required=True)
    parser.add_argument("--out-prefix", type=Path, required=True)
    args = parser.parse_args()

    out_prefix = args.out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_csv = out_prefix.with_suffix(".csv")
    out_json = out_prefix.with_suffix(".json")
    out_md = out_prefix.with_suffix(".md")

    overall = init_counter()
    by_seed: dict[int, dict[str, int]] = defaultdict(init_counter)
    by_lop: dict[float, dict[str, int]] = defaultdict(init_counter)
    by_seed_lop: dict[tuple[int, float], dict[str, int]] = defaultdict(init_counter)
    by_split: dict[str, dict[str, int]] = defaultdict(init_counter)

    sample_id_list: list[int] = []
    seed_list: list[int] = []
    lop_list: list[float] = []
    csv_dcopf_success: list[bool] = []
    csv_ac_fail_label: list[bool] = []
    flow_valid_seen = None

    false_certificate_examples: list[dict[str, Any]] = []

    with args.csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sample_id = int(row["sample_id"])
            seed = int(row["seed"])
            lop = float(row["line_outage_prob"])
            acopf_success = parse_bool(row.get("acopf_success", "False"))
            acopf_fail_label = parse_bool(row.get("acopf_fail_label", "False"))
            dcopf_success = parse_bool(row.get("dcopf_success", "False"))
            dcopf_fail_indicator = parse_bool(row.get("dcopf_fail_indicator", "False"))
            acopf_s_any = parse_float(row.get("acopf_s_any", "inf"))
            dcopf_s_any = parse_float(row.get("dcopf_s_any", "inf"))

            acopf_failed = bool(acopf_fail_label) or (not acopf_success) or (math.isinf(acopf_s_any) and acopf_s_any > 0)
            dcopf_failed = (not dcopf_success) or bool(dcopf_fail_indicator) or (math.isinf(dcopf_s_any) and dcopf_s_any > 0)

            update_counter(overall, ac_fail=acopf_failed, dc_fail=dcopf_failed)
            update_counter(by_seed[seed], ac_fail=acopf_failed, dc_fail=dcopf_failed)
            update_counter(by_lop[lop], ac_fail=acopf_failed, dc_fail=dcopf_failed)
            update_counter(by_seed_lop[(seed, lop)], ac_fail=acopf_failed, dc_fail=dcopf_failed)
            update_counter(by_split[split_name(seed)], ac_fail=acopf_failed, dc_fail=dcopf_failed)

            if dcopf_failed and (not acopf_failed) and len(false_certificate_examples) < 50:
                false_certificate_examples.append(
                    {
                        "sample_id": sample_id,
                        "seed": seed,
                        "line_outage_prob": lop,
                        "acopf_success": acopf_success,
                        "acopf_s_any": acopf_s_any,
                        "dcopf_success": dcopf_success,
                        "dcopf_s_any": dcopf_s_any,
                    }
                )

            sample_id_list.append(sample_id)
            seed_list.append(seed)
            lop_list.append(lop)
            csv_dcopf_success.append(dcopf_success)
            csv_ac_fail_label.append(acopf_failed)

    npz = np.load(args.npz)
    npz_sample_id = np.asarray(npz["sample_id"], dtype=np.int64)
    npz_seed = np.asarray(npz["seed"], dtype=np.int64)
    npz_lop = np.asarray(npz["line_outage_prob"], dtype=np.float64)
    npz_dcopf_success = np.asarray(npz["dcopf_success"], dtype=bool)
    npz_ac_fail_label = np.asarray(npz["acopf_fail_label"], dtype=bool)
    flow_valid = np.asarray(npz["flow_valid"], dtype=bool)
    flow_valid_seen = bool(np.all(flow_valid))

    csv_sample_id = np.asarray(sample_id_list, dtype=np.int64)
    csv_seed = np.asarray(seed_list, dtype=np.int64)
    csv_lop = np.asarray(lop_list, dtype=np.float64)
    csv_dcopf_success_arr = np.asarray(csv_dcopf_success, dtype=bool)
    csv_ac_fail_arr = np.asarray(csv_ac_fail_label, dtype=bool)

    npz_checks = {
        "sample_id_exact_match": bool(np.array_equal(csv_sample_id, npz_sample_id)),
        "seed_exact_match": bool(np.array_equal(csv_seed, npz_seed)),
        "line_outage_prob_allclose": bool(np.allclose(csv_lop, npz_lop)),
        "dcopf_success_exact_match": bool(np.array_equal(csv_dcopf_success_arr, npz_dcopf_success)),
        "acopf_fail_label_exact_match": bool(np.array_equal(csv_ac_fail_arr, npz_ac_fail_label)),
        "flow_valid_all_true": flow_valid_seen,
        "n_csv_rows": int(csv_sample_id.shape[0]),
        "n_npz_rows": int(npz_sample_id.shape[0]),
    }

    rows: list[dict[str, Any]] = []

    def append_rows(group_type: str, key: str, counter: dict[str, int]) -> None:
        metrics = finalize_metrics(counter)
        rows.append({"group_type": group_type, "group_key": key, **metrics})

    append_rows("overall", "all", overall)
    for seed in sorted(by_seed.keys()):
        append_rows("by_seed", str(seed), by_seed[seed])
    for lop in sorted(by_lop.keys()):
        append_rows("by_lop", f"{lop:.6f}", by_lop[lop])
    for split in ("train", "validation", "unseen", "other"):
        if split in by_split:
            append_rows("by_split", split, by_split[split])
        else:
            append_rows("by_split", split, init_counter())
    for (seed, lop) in sorted(by_seed_lop.keys(), key=lambda x: (x[0], x[1])):
        append_rows("by_seed_lop", f"seed={seed},lop={lop:.6f}", by_seed_lop[(seed, lop)])

    write_csv(out_csv, rows)

    false_regimes = [
        {
            "seed": seed,
            "line_outage_prob": lop,
            "false_certificate_count": int(c["false_certificate_count"]),
            "dcopf_failed_count": int(c["dcopf_failed_count"]),
            "false_certificate_rate": safe_ratio(
                int(c["false_certificate_count"]), int(c["dcopf_failed_count"])
            ),
        }
        for (seed, lop), c in by_seed_lop.items()
        if int(c["false_certificate_count"]) > 0
    ]

    overall_metrics = finalize_metrics(overall)
    summary = {
        "stage": "certificate_audit_v001",
        "inputs": {
            "csv": str(args.csv),
            "npz": str(args.npz),
        },
        "npz_cross_checks": npz_checks,
        "overall": overall_metrics,
        "false_certificate_regimes": sorted(false_regimes, key=lambda x: (x["seed"], x["line_outage_prob"])),
        "false_certificate_examples_head": false_certificate_examples[:10],
    }
    out_json.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    by_lop_rows = [r for r in rows if r["group_type"] == "by_lop"]
    by_seed_rows = [r for r in rows if r["group_type"] == "by_seed"]
    by_seed_lop_rows = [r for r in rows if r["group_type"] == "by_seed_lop"]
    by_split_rows = [r for r in rows if r["group_type"] == "by_split"]

    md_lines = [
        "# DCOPF Failure Certificate Audit (case118 v001)",
        "",
        "## 1. Purpose",
        "",
        "Audit whether `DCOPF failed` empirically implies `ACOPF failed` on existing case118 data.",
        "",
        "## 2. Data Sources",
        "",
        f"- CSV: `{args.csv}`",
        f"- NPZ: `{args.npz}`",
        f"- rows: `{npz_checks['n_csv_rows']}`",
        "",
        "## 3. Overall Certificate Result",
        "",
        f"- `dcopf_failed_count`: `{overall_metrics['dcopf_failed_count']}`",
        f"- `acopf_failed_count`: `{overall_metrics['acopf_failed_count']}`",
        f"- `true_certificate_count`: `{overall_metrics['true_certificate_count']}`",
        f"- `false_certificate_count`: `{overall_metrics['false_certificate_count']}`",
        f"- `P(ACOPF fail | DCOPF fail)`: `{fmt(overall_metrics['P_acopf_fail_given_dcopf_fail'])}`",
        f"- Wilson 95% CI: `[{fmt(overall_metrics['P_acopf_fail_given_dcopf_fail_wilson_lo'])}, {fmt(overall_metrics['P_acopf_fail_given_dcopf_fail_wilson_hi'])}]`",
        f"- `false_certificate_rate`: `{fmt(overall_metrics['false_certificate_rate'])}`",
        f"- `missed_failure_rate`: `{fmt(overall_metrics['missed_failure_rate'])}`",
        "",
        "## 4. By-lop Table",
        "",
        "| lop | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | false_rate |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(by_lop_rows, key=lambda x: float(x["group_key"])):
        md_lines.append(
            f"| {row['group_key']} | {row['n_total']} | {row['dcopf_failed_count']} | {row['acopf_failed_count']} | {row['false_certificate_count']} | {fmt(row['P_acopf_fail_given_dcopf_fail'])} | {fmt(row['false_certificate_rate'])} |"
        )

    md_lines.extend(
        [
            "",
            "## 5. By-seed Table",
            "",
            "| seed | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | false_rate |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(by_seed_rows, key=lambda x: int(x["group_key"])):
        md_lines.append(
            f"| {row['group_key']} | {row['n_total']} | {row['dcopf_failed_count']} | {row['acopf_failed_count']} | {row['false_certificate_count']} | {fmt(row['P_acopf_fail_given_dcopf_fail'])} | {fmt(row['false_certificate_rate'])} |"
        )

    md_lines.extend(
        [
            "",
            "## 6. By seed x lop Table",
            "",
            "| seed,lop | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | false_rate |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in by_seed_lop_rows:
        md_lines.append(
            f"| {row['group_key']} | {row['n_total']} | {row['dcopf_failed_count']} | {row['acopf_failed_count']} | {row['false_certificate_count']} | {fmt(row['P_acopf_fail_given_dcopf_fail'])} | {fmt(row['false_certificate_rate'])} |"
        )

    md_lines.extend(
        [
            "",
            "## 6b. By split Table",
            "",
            "| split | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | availability |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in by_split_rows:
        availability = "available" if int(row["n_total"]) > 0 else "not_available"
        md_lines.append(
            f"| {row['group_key']} | {row['n_total']} | {row['dcopf_failed_count']} | {row['acopf_failed_count']} | {row['false_certificate_count']} | {fmt(row['P_acopf_fail_given_dcopf_fail'])} | {availability} |"
        )

    md_lines.extend(
        [
            "",
            "## 7. False Certificate Cases",
            "",
        ]
    )
    if overall_metrics["false_certificate_count"] == 0:
        md_lines.append("- No false certificate cases found in this dataset.")
    else:
        md_lines.append(f"- False certificate total: `{overall_metrics['false_certificate_count']}`.")
        md_lines.append("- Regimes with nonzero false certificate count:")
        for reg in summary["false_certificate_regimes"]:
            md_lines.append(
                f"- seed={reg['seed']} lop={reg['line_outage_prob']}: false={reg['false_certificate_count']} / dc_fail={reg['dcopf_failed_count']} ({fmt(reg['false_certificate_rate'])})"
            )

    md_lines.extend(
        [
            "",
            "## 8. Interpretation",
            "",
        ]
    )
    if overall_metrics["false_certificate_count"] == 0:
        md_lines.append(
            "- This dataset supports a high-precision empirical certificate (`DCOPF failed => ACOPF failed`), but this is not a theorem."
        )
    else:
        md_lines.append(
            "- DCOPF failure is not universally safe as a certificate in this dataset; the nonzero false-certificate regimes above must be excluded or further modeled."
        )
    md_lines.extend(
        [
            "",
            "## 9. Implication for DA",
            "",
        ]
    )
    if overall_metrics["false_certificate_count"] == 0:
        md_lines.append(
            "- High empirical certificate precision suggests a controlled `certified_dcopf_failure_shortcut` experiment may be reasonable in selected regimes."
        )
    else:
        md_lines.append(
            "- A4 parameterization should focus on separating high-confidence DCOPF failures from uncertain failures before any shortcut attempt."
        )

    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"wrote csv: {out_csv}")
    print(f"wrote json: {out_json}")
    print(f"wrote md: {out_md}")


if __name__ == "__main__":
    main()
