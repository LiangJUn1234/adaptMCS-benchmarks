"""Subset Simulation controller with Phase 6B evaluator paths."""

from __future__ import annotations

import copy
import json
import logging
import math
import random
import statistics
import time
from typing import Any, Dict, List, Mapping, Sequence

from .config import DEFAULTS
from .mcmc_sampler import LineOnlyMMHSampler
from .problem import eval_proxy, eval_truth, sample_X

LOGGER = logging.getLogger(__name__)


class SuSController:
    """Subset Simulation controller (Phase 6A/6B scaffolding)."""

    def __init__(self, case_name: str, config: Mapping[str, Any]):
        if not case_name:
            raise ValueError("case_name must be non-empty")

        merged = dict(DEFAULTS)
        merged.update(dict(config))

        self.case_name = case_name
        self.config: Dict[str, Any] = merged
        self.target_violation = float(self.config.get("target_violation", 0.0))
        self.p0 = float(self.config.get("sus_p0", 0.1))
        self.max_levels = int(self.config.get("max_levels", 20))
        self.evaluator_mode = str(self.config.get("evaluator_mode", "truth_only"))
        self.truth_mode = str(self.config.get("truth_mode", "acopf"))
        self.proxy_mode = str(self.config.get("proxy_mode", self.config.get("proxy", "dcpf")))
        self.audit_shadow_prob = float(self.config.get("audit_shadow_prob", 0.0))
        self.enable_hastings_correction = bool(
            self.config.get("enable_hastings_correction", True)
        )
        self.enable_level0_prescreen = bool(
            self.config.get("enable_level0_prescreen", True)
        )
        self.level0_prescreen_proxy_mode = str(
            self.config.get("level0_prescreen_proxy_mode", "fdxb")
        )
        self.level0_guard_mode = str(
            self.config.get("level0_guard_mode", "legacy_truth_score")
        )
        self.level0_prescreen_K = int(self.config.get("level0_prescreen_K", 200))
        self.level0_prescreen_tail_audit = int(
            self.config.get("level0_prescreen_tail_audit", 50)
        )
        self.level0_prescreen_expand_factor = float(
            self.config.get("level0_prescreen_expand_factor", 1.5)
        )
        self.level0_prescreen_max_expand_rounds = int(
            self.config.get("level0_prescreen_max_expand_rounds", 3)
        )
        self.level0_prescreen_fallback_full_truth = bool(
            self.config.get("level0_prescreen_fallback_full_truth", True)
        )
        self.da_debug_print = bool(self.config.get("da_debug_print", False))
        self.da_debug_max_logs = int(self.config.get("da_debug_max_logs", 20))
        self._last_sampler_stats: Dict[str, Any] | None = None
        self._truth_engine_time = 0.0
        self.stats: Dict[str, Any] = {}

        if not (0.0 < self.p0 <= 1.0):
            raise ValueError("sus_p0 must be in (0, 1]")
        if self.truth_mode not in {"acopf", "acpf", "dcpf"}:
            raise ValueError("truth_mode must be one of: acopf, acpf, dcpf")
        if self.proxy_mode not in {"dcpf", "fdxb", "dcopf", "ml_surrogate", "ml_failure"}:
            raise ValueError("proxy_mode must be one of: dcpf, fdxb, dcopf, ml_surrogate, ml_failure")
        if self.level0_prescreen_proxy_mode not in {"dcpf", "fdxb", "dcopf", "ml_surrogate", "ml_failure"}:
            raise ValueError(
                "level0_prescreen_proxy_mode must be one of: dcpf, fdxb, dcopf, ml_surrogate, ml_failure"
            )
        if self.level0_guard_mode not in {"legacy_truth_score", "failure_label"}:
            raise ValueError(
                "level0_guard_mode must be one of: legacy_truth_score, failure_label"
            )
        if not (0.0 <= self.audit_shadow_prob <= 1.0):
            raise ValueError("audit_shadow_prob must be in [0, 1]")
        if self.da_debug_max_logs < 0:
            raise ValueError("da_debug_max_logs must be >= 0")
        if self.level0_prescreen_K <= 0:
            raise ValueError("level0_prescreen_K must be > 0")
        if self.level0_prescreen_tail_audit < 0:
            raise ValueError("level0_prescreen_tail_audit must be >= 0")
        if self.level0_prescreen_expand_factor <= 1.0:
            raise ValueError("level0_prescreen_expand_factor must be > 1.0")
        if self.level0_prescreen_max_expand_rounds < 0:
            raise ValueError("level0_prescreen_max_expand_rounds must be >= 0")

    def run(self, n_samples: int, seed: int | None = None) -> dict:
        if n_samples <= 0:
            raise ValueError("n_samples must be positive")

        if self.evaluator_mode not in {"truth_only", "proxy_only", "delayed_acceptance"}:
            raise ValueError(
                "Unsupported evaluator_mode. Use truth_only, proxy_only, or delayed_acceptance."
            )

        run_started = time.perf_counter()
        self._truth_engine_time = 0.0
        self._last_sampler_stats = None
        self.stats = {}

        def finalize(output: Dict[str, Any]) -> Dict[str, Any]:
            total_wall_clock_time = time.perf_counter() - run_started
            output["total_wall_clock_time"] = float(total_wall_clock_time)
            output["truth_engine_time"] = float(self._truth_engine_time)
            l0_log = {}
            level_logs = list(output.get("level_logs", []))
            if level_logs:
                l0_log = dict(level_logs[0])
            self.stats = {
                "case_name": self.case_name,
                "evaluator_mode": self.evaluator_mode,
                "proxy_mode": output.get("proxy_mode"),
                "truth_mode": self.truth_mode,
                "pf_hat": output.get("pf_hat"),
                "n_levels": output.get("n_levels"),
                "termination_reason": output.get("termination_reason"),
                "n_proxy_calls": output.get("n_proxy_calls"),
                "n_truth_calls": output.get("n_truth_calls"),
                "total_wall_clock_time": float(total_wall_clock_time),
                "truth_engine_time": float(self._truth_engine_time),
                "stage1_reject_total": output.get("stage1_reject_total"),
                "level_logs": copy.deepcopy(output.get("level_logs", [])),
                "l0_prescreen_enabled": l0_log.get("l0_prescreen_enabled"),
                "l0_proxy_calls": l0_log.get("l0_proxy_calls"),
                "l0_truth_calls": l0_log.get("l0_truth_calls"),
                "l0_guard_active": l0_log.get("l0_guard_active"),
                "l0_guard_mode": l0_log.get("l0_guard_mode"),
                "l0_prescreen_K_initial": l0_log.get("l0_prescreen_K_initial"),
                "l0_prescreen_K_final": l0_log.get("l0_prescreen_K_final"),
                "l0_prescreen_expand_rounds": l0_log.get("l0_prescreen_expand_rounds"),
                "l0_tail_audit_count": l0_log.get("l0_tail_audit_count"),
                "l0_tail_audit_failure_hits": l0_log.get("l0_tail_audit_failure_hits"),
                "l0_rank_inversion_hits": l0_log.get("l0_rank_inversion_hits"),
                "l0_failure_recall_inside_final_k": l0_log.get(
                    "l0_failure_recall_inside_final_k"
                ),
                "l0_failure_recall_inside_final_k_observed": l0_log.get(
                    "l0_failure_recall_inside_final_k_observed"
                ),
                "l0_failure_label_rank_inversion_hits": l0_log.get(
                    "l0_failure_label_rank_inversion_hits"
                ),
                "l0_failure_label_guard_passed": l0_log.get(
                    "l0_failure_label_guard_passed"
                ),
                "l0_failure_label_fallback_reason": l0_log.get(
                    "l0_failure_label_fallback_reason"
                ),
                "l0_guard_passed": l0_log.get("l0_guard_passed"),
                "l0_gamma1_mode": l0_log.get("l0_gamma1_mode"),
                "l0_gamma1_candidate": l0_log.get("l0_gamma1_candidate"),
                "l0_fallback_triggered": l0_log.get("l0_fallback_triggered"),
                "l0_fallback_reason": l0_log.get("l0_fallback_reason"),
                "l0_tail_audit_truth_fail_count": l0_log.get("l0_tail_audit_truth_fail_count"),
                "l0_tail_audit_hit_fail_count": l0_log.get("l0_tail_audit_hit_fail_count"),
                "l0_tail_audit_hit_line_count": l0_log.get("l0_tail_audit_hit_line_count"),
                "l0_tail_audit_hit_volt_count": l0_log.get("l0_tail_audit_hit_volt_count"),
                "l0_proxy_fail_count": l0_log.get("l0_proxy_fail_count"),
                "l0_proxy_inf_count": l0_log.get("l0_proxy_inf_count"),
                "l0_proxy_fail_in_topk_count": l0_log.get("l0_proxy_fail_in_topk_count"),
                "l0_proxy_inf_in_topk_count": l0_log.get("l0_proxy_inf_in_topk_count"),
                "l0_proxy_fail_in_audit_count": l0_log.get("l0_proxy_fail_in_audit_count"),
                "l0_proxy_inf_in_audit_count": l0_log.get("l0_proxy_inf_in_audit_count"),
            }
            return output

        states = self._initial_states(n_samples, seed)
        n_seed_init = int(math.ceil(self.p0 * n_samples))
        l0_meta = self._default_l0_meta()

        if self.evaluator_mode == "proxy_only":
            scores, init_proxy_calls = self._evaluate_states_proxy(states)
            init_truth_calls = 0
        elif self.evaluator_mode == "delayed_acceptance" and self.enable_level0_prescreen:
            (
                scores,
                init_truth_calls,
                init_proxy_calls,
                l0_meta,
            ) = self._evaluate_states_level0_prescreen(
                states,
                n_seed=n_seed_init,
                seed=seed,
            )
        else:
            scores, init_truth_calls = self._evaluate_states_truth(states)
            init_proxy_calls = 0
            l0_meta = {
                **self._default_l0_meta(),
                "l0_prescreen_enabled": False,
                "l0_proxy_calls": int(init_proxy_calls),
                "l0_truth_calls": int(init_truth_calls),
                "l0_guard_active": False,
                "l0_guard_mode": "not_applicable",
                "l0_gamma1_mode": "full_truth",
                "l0_guard_passed": True,
                "l0_fallback_triggered": False,
                "l0_fallback_reason": "not_applicable",
            }

        total_proxy_calls = init_proxy_calls
        total_truth_calls = init_truth_calls
        total_attempts = 0
        total_stage1_rejects = 0
        total_stage1_pass = 0
        total_stage2_pass = 0
        total_stage1_reject_shadow_eval_count = 0
        total_stage1_reject_shadow_truth_pass_count = 0
        total_stage1_reject_shadow_truth_fail_count = 0

        current_level_meta = {
            "n_proxy_calls": init_proxy_calls,
            "n_truth_calls": init_truth_calls,
            "stage1_reject_ratio": None,
            "stage2_accept_ratio": None,
            "stage1_reject_total": 0,
            "stage1_reject_shadow_eval_count": 0,
            "stage1_reject_shadow_truth_pass_count": 0,
            "stage1_reject_shadow_truth_fail_count": 0,
            "stage1_reject_shadow_truth_accept_rate": None,
        }

        level_logs: List[Dict[str, Any]] = []
        level = 0

        while True:
            n_seed = int(math.ceil(self.p0 * n_samples))
            seed_idx = self._select_top_seed_indices(scores, n_seed)
            threshold = float(scores[seed_idx[-1]])

            level_log = self._build_level_log(level, threshold, scores, n_samples, n_seed)
            level_log.update(
                {
                    "evaluator_mode": self.evaluator_mode,
                    "proxy_mode": self.proxy_mode if self.evaluator_mode != "truth_only" else None,
                    "truth_mode": self.truth_mode,
                    "n_proxy_calls": int(current_level_meta["n_proxy_calls"]),
                    "n_truth_calls": int(current_level_meta["n_truth_calls"]),
                    "stage1_reject_ratio": current_level_meta["stage1_reject_ratio"],
                    "stage2_accept_ratio": current_level_meta["stage2_accept_ratio"],
                    "stage1_reject_total": int(current_level_meta["stage1_reject_total"]),
                    "stage1_reject_shadow_eval_count": int(
                        current_level_meta["stage1_reject_shadow_eval_count"]
                    ),
                    "stage1_reject_shadow_truth_pass_count": int(
                        current_level_meta["stage1_reject_shadow_truth_pass_count"]
                    ),
                    "stage1_reject_shadow_truth_fail_count": int(
                        current_level_meta["stage1_reject_shadow_truth_fail_count"]
                    ),
                    "stage1_reject_shadow_truth_accept_rate": current_level_meta[
                        "stage1_reject_shadow_truth_accept_rate"
                    ],
                }
            )
            if level == 0:
                level_log.update(dict(l0_meta))
            else:
                level_log.update(self._default_l0_meta())
            if self._last_sampler_stats is not None:
                level_log["sampler_stats"] = copy.deepcopy(self._last_sampler_stats)
            level_logs.append(level_log)

            if math.isinf(threshold) and threshold > 0:
                return finalize(self._build_final_output(
                    n_samples=n_samples,
                    level=level,
                    scores=scores,
                    level_logs=level_logs,
                    termination_reason="threshold_reached_infinite",
                    n_proxy_calls=total_proxy_calls,
                    n_truth_calls=total_truth_calls,
                    total_attempts=total_attempts,
                    total_stage1_rejects=total_stage1_rejects,
                    total_stage1_pass=total_stage1_pass,
                    total_stage2_pass=total_stage2_pass,
                    total_stage1_reject_shadow_eval_count=total_stage1_reject_shadow_eval_count,
                    total_stage1_reject_shadow_truth_pass_count=total_stage1_reject_shadow_truth_pass_count,
                    total_stage1_reject_shadow_truth_fail_count=total_stage1_reject_shadow_truth_fail_count,
                ))

            if threshold >= self.target_violation:
                return finalize(self._build_final_output(
                    n_samples=n_samples,
                    level=level,
                    scores=scores,
                    level_logs=level_logs,
                    termination_reason="target_threshold_reached",
                    n_proxy_calls=total_proxy_calls,
                    n_truth_calls=total_truth_calls,
                    total_attempts=total_attempts,
                    total_stage1_rejects=total_stage1_rejects,
                    total_stage1_pass=total_stage1_pass,
                    total_stage2_pass=total_stage2_pass,
                    total_stage1_reject_shadow_eval_count=total_stage1_reject_shadow_eval_count,
                    total_stage1_reject_shadow_truth_pass_count=total_stage1_reject_shadow_truth_pass_count,
                    total_stage1_reject_shadow_truth_fail_count=total_stage1_reject_shadow_truth_fail_count,
                ))

            if level + 1 >= self.max_levels:
                return finalize(self._build_final_output(
                    n_samples=n_samples,
                    level=level,
                    scores=scores,
                    level_logs=level_logs,
                    termination_reason="max_levels_reached",
                    n_proxy_calls=total_proxy_calls,
                    n_truth_calls=total_truth_calls,
                    total_attempts=total_attempts,
                    total_stage1_rejects=total_stage1_rejects,
                    total_stage1_pass=total_stage1_pass,
                    total_stage2_pass=total_stage2_pass,
                    total_stage1_reject_shadow_eval_count=total_stage1_reject_shadow_eval_count,
                    total_stage1_reject_shadow_truth_pass_count=total_stage1_reject_shadow_truth_pass_count,
                    total_stage1_reject_shadow_truth_fail_count=total_stage1_reject_shadow_truth_fail_count,
                ))

            seed_states = [states[i] for i in seed_idx]
            seed_scores = [scores[i] for i in seed_idx]

            if self.evaluator_mode == "truth_only":
                states, scores, evolve_meta = self._evolve_next_level_truth_only(
                    seed_states=seed_states,
                    seed_scores=seed_scores,
                    threshold=threshold,
                    n_samples=n_samples,
                    seed=None if seed is None else seed + level + 1,
                )
            elif self.evaluator_mode == "proxy_only":
                states, scores, evolve_meta = self._evolve_next_level_proxy_only(
                    seed_states=seed_states,
                    seed_scores=seed_scores,
                    threshold=threshold,
                    n_samples=n_samples,
                    seed=None if seed is None else seed + level + 1,
                )
            else:
                states, scores, evolve_meta = self._evolve_next_level_delayed_acceptance(
                    seed_states=seed_states,
                    seed_scores=seed_scores,
                    threshold=threshold,
                    n_samples=n_samples,
                    seed=None if seed is None else seed + level + 1,
                )

            if len(states) != n_samples or len(scores) != n_samples:
                raise RuntimeError("_evolve_next_level must return exactly N states and N scores")

            total_proxy_calls += int(evolve_meta["n_proxy_calls"])
            total_truth_calls += int(evolve_meta["n_truth_calls"])
            total_attempts += int(evolve_meta["attempts"])
            total_stage1_rejects += int(evolve_meta["stage1_rejects"])
            total_stage1_pass += int(evolve_meta["stage1_pass"])
            total_stage2_pass += int(evolve_meta["stage2_pass"])
            total_stage1_reject_shadow_eval_count += int(
                evolve_meta.get("stage1_reject_shadow_eval_count", 0)
            )
            total_stage1_reject_shadow_truth_pass_count += int(
                evolve_meta.get("stage1_reject_shadow_truth_pass_count", 0)
            )
            total_stage1_reject_shadow_truth_fail_count += int(
                evolve_meta.get("stage1_reject_shadow_truth_fail_count", 0)
            )

            current_level_meta = {
                "n_proxy_calls": int(evolve_meta["n_proxy_calls"]),
                "n_truth_calls": int(evolve_meta["n_truth_calls"]),
                "stage1_reject_ratio": (
                    float(evolve_meta["stage1_reject_ratio"])
                    if self.evaluator_mode == "delayed_acceptance"
                    else None
                ),
                "stage2_accept_ratio": (
                    float(evolve_meta["stage2_accept_ratio"])
                    if self.evaluator_mode == "delayed_acceptance"
                    else None
                ),
                "stage1_reject_total": int(evolve_meta["stage1_rejects"]),
                "stage1_reject_shadow_eval_count": int(
                    evolve_meta.get("stage1_reject_shadow_eval_count", 0)
                ),
                "stage1_reject_shadow_truth_pass_count": int(
                    evolve_meta.get("stage1_reject_shadow_truth_pass_count", 0)
                ),
                "stage1_reject_shadow_truth_fail_count": int(
                    evolve_meta.get("stage1_reject_shadow_truth_fail_count", 0)
                ),
                "stage1_reject_shadow_truth_accept_rate": evolve_meta.get(
                    "stage1_reject_shadow_truth_accept_rate", None
                ),
            }
            self._last_sampler_stats = copy.deepcopy(evolve_meta["sampler_stats"])
            level += 1

    def _build_final_output(
        self,
        *,
        n_samples: int,
        level: int,
        scores: Sequence[float],
        level_logs: Sequence[Mapping[str, Any]],
        termination_reason: str,
        n_proxy_calls: int,
        n_truth_calls: int,
        total_attempts: int,
        total_stage1_rejects: int,
        total_stage1_pass: int,
        total_stage2_pass: int,
        total_stage1_reject_shadow_eval_count: int,
        total_stage1_reject_shadow_truth_pass_count: int,
        total_stage1_reject_shadow_truth_fail_count: int,
    ) -> Dict[str, Any]:
        n_fail_like = sum(1 for s in scores if s >= self.target_violation)
        pf_hat = (self.p0 ** level) * (n_fail_like / float(n_samples))
        if self.evaluator_mode == "delayed_acceptance" and total_attempts > 0:
            stage1_reject_ratio: float | None = total_stage1_rejects / float(total_attempts)
            stage2_accept_ratio: float | None = (
                total_stage2_pass / float(total_stage1_pass) if total_stage1_pass > 0 else 0.0
            )
        else:
            stage1_reject_ratio = None
            stage2_accept_ratio = None
        stage1_reject_shadow_truth_accept_rate = (
            total_stage1_reject_shadow_truth_pass_count
            / float(total_stage1_reject_shadow_eval_count)
            if total_stage1_reject_shadow_eval_count > 0
            else None
        )

        return {
            "evaluator_mode": self.evaluator_mode,
            "proxy_mode": self.proxy_mode if self.evaluator_mode != "truth_only" else None,
            "truth_mode": self.truth_mode,
            "target_violation": self.target_violation,
            "n_samples": n_samples,
            "n_levels": level + 1,
            "pf_hat": pf_hat,
            "termination_reason": termination_reason,
            "n_proxy_calls": int(n_proxy_calls),
            "n_truth_calls": int(n_truth_calls),
            "stage1_reject_ratio": stage1_reject_ratio,
            "stage2_accept_ratio": stage2_accept_ratio,
            "stage1_reject_total": int(total_stage1_rejects),
            "stage1_reject_shadow_eval_count": int(total_stage1_reject_shadow_eval_count),
            "stage1_reject_shadow_truth_pass_count": int(
                total_stage1_reject_shadow_truth_pass_count
            ),
            "stage1_reject_shadow_truth_fail_count": int(
                total_stage1_reject_shadow_truth_fail_count
            ),
            "stage1_reject_shadow_truth_accept_rate": stage1_reject_shadow_truth_accept_rate,
            "level_logs": list(level_logs),
        }

    def _initial_states(self, n_samples: int, seed: int | None) -> List[Dict[str, Any]]:
        # Phase 6A/6B restriction: line-only conditional sampling.
        cfg = dict(self.config)
        cfg["bus_outage_prob"] = 0.0
        cfg["gen_derate_state_values"] = (1.0,)
        cfg["gen_derate_state_probs"] = (1.0,)

        sampled = sample_X(self.case_name, cfg, n=n_samples, seed=seed)
        return [self._normalize_line_only_state(s) for s in sampled]

    def _evaluate_states_truth(
        self,
        states: Sequence[Mapping[str, Any]],
    ) -> tuple[List[float], int]:
        scores: List[float] = []
        calls = 0
        for state in states:
            scores.append(self._timed_truth_score(state))
            calls += 1
        return scores, calls

    def _evaluate_states_proxy(
        self,
        states: Sequence[Mapping[str, Any]],
    ) -> tuple[List[float], int]:
        scores: List[float] = []
        calls = 0
        for state in states:
            payload = eval_proxy(
                self.case_name,
                state,
                self.config,
                proxy_mode=self.proxy_mode,
                debug=False,
            )
            scores.append(float(payload["s_any"]))
            calls += 1
        return scores, calls

    def _default_l0_meta(self) -> Dict[str, Any]:
        return {
            "l0_prescreen_enabled": False,
            "l0_proxy_calls": 0,
            "l0_truth_calls": 0,
            "l0_guard_active": False,
            "l0_guard_mode": "not_applicable",
            "l0_prescreen_K_initial": None,
            "l0_prescreen_K_final": None,
            "l0_prescreen_expand_rounds": 0,
            "l0_tail_audit_count": 0,
            "l0_tail_audit_failure_hits": "not_applicable",
            "l0_rank_inversion_hits": 0,
            "l0_failure_recall_inside_final_k": "not_applicable",
            "l0_failure_recall_inside_final_k_observed": "not_applicable",
            "l0_failure_label_rank_inversion_hits": "not_applicable",
            "l0_failure_label_guard_passed": "not_applicable",
            "l0_failure_label_fallback_reason": "not_applicable",
            "l0_guard_passed": None,
            "l0_gamma1_mode": "full_truth",
            "l0_gamma1_candidate": None,
            "l0_fallback_triggered": False,
            "l0_fallback_reason": "not_applicable",
            "l0_tail_audit_truth_fail_count": 0,
            "l0_tail_audit_hit_fail_count": 0,
            "l0_tail_audit_hit_line_count": 0,
            "l0_tail_audit_hit_volt_count": 0,
            "l0_proxy_fail_count": 0,
            "l0_proxy_inf_count": 0,
            "l0_proxy_fail_in_topk_count": 0,
            "l0_proxy_inf_in_topk_count": 0,
            "l0_proxy_fail_in_audit_count": 0,
            "l0_proxy_inf_in_audit_count": 0,
        }

    def _evaluate_states_level0_prescreen(
        self,
        states: Sequence[Mapping[str, Any]],
        *,
        n_seed: int,
        seed: int | None,
    ) -> tuple[List[float], int, int, Dict[str, Any]]:
        _ = seed
        n_samples = len(states)
        if n_samples <= 0:
            return [], 0, 0, self._default_l0_meta()

        proxy_payloads: List[Dict[str, Any]] = []
        proxy_scores: List[float] = []
        proxy_fail_count = 0
        proxy_inf_count = 0
        for state in states:
            payload = eval_proxy(
                self.case_name,
                state,
                self.config,
                proxy_mode=self.level0_prescreen_proxy_mode,
                debug=False,
            )
            proxy_payloads.append(dict(payload))
            score = float(payload["s_any"])
            proxy_scores.append(score)
            if not bool(payload.get("success", False)):
                proxy_fail_count += 1
            if math.isinf(score) and score > 0:
                proxy_inf_count += 1
        proxy_calls = n_samples

        ranking = sorted(range(n_samples), key=lambda i: proxy_scores[i], reverse=True)
        k_initial = min(n_samples, max(int(n_seed), int(self.level0_prescreen_K)))
        k_current = k_initial

        truth_payloads: List[Dict[str, Any] | None] = [None for _ in range(n_samples)]
        truth_scores: List[float | None] = [None for _ in range(n_samples)]
        truth_failed_flags: List[bool | None] = [None for _ in range(n_samples)]
        truth_calls = 0
        rank_inversion_hits = 0
        failure_label_rank_inversion_hits = 0
        tail_audit_count = 0
        tail_audit_truth_fail_count = 0
        tail_audit_hit_fail_count = 0
        tail_audit_hit_line_count = 0
        tail_audit_hit_volt_count = 0
        expand_rounds = 0
        guard_passed = False
        failure_label_guard_passed: bool | str = False
        gamma_candidate: float | None = None
        gamma_mode = "prescreen_guarded"
        fallback_triggered = False
        fallback_reason = "none"
        failure_label_fallback_reason = "not_applicable"
        audited_indices_seen: set[int] = set()
        failure_label_guard_active = self.level0_guard_mode == "failure_label"
        if not failure_label_guard_active:
            failure_label_guard_passed = "not_applicable"

        def as_float(value: Any) -> float:
            try:
                return float(value)
            except Exception:
                return float("-inf")

        def ensure_truth_payload(idx: int) -> Dict[str, Any]:
            nonlocal truth_calls
            cached = truth_payloads[idx]
            if cached is not None:
                return dict(cached)
            payload = self._timed_truth_payload(states[idx])
            truth_payloads[idx] = dict(payload)
            truth_scores[idx] = as_float(payload.get("s_any", float("inf")))
            truth_failed_flags[idx] = (not bool(payload.get("success", False))) or math.isinf(
                truth_scores[idx]
            )
            truth_calls += 1
            return dict(payload)

        def ensure_truth(idx: int) -> float:
            payload = ensure_truth_payload(idx)
            return as_float(payload.get("s_any", float("inf")))

        def ensure_truth_failed(idx: int) -> bool:
            ensure_truth_payload(idx)
            return bool(truth_failed_flags[idx])

        def failure_recall_inside(final_k: int) -> float | None:
            if final_k <= 0:
                return None
            if any(flag is None for flag in truth_failed_flags):
                return None
            truth_fail_total = int(sum(1 for flag in truth_failed_flags if flag))
            if truth_fail_total <= 0:
                return None
            topk_indices = ranking[:final_k]
            fail_hits = sum(1 for idx in topk_indices if ensure_truth_failed(idx))
            return fail_hits / float(truth_fail_total)

        def failure_recall_inside_observed(final_k: int) -> float | None:
            if final_k <= 0:
                return None
            observed_fail_total = int(sum(1 for flag in truth_failed_flags if flag is True))
            if observed_fail_total <= 0:
                return None
            topk_indices = ranking[:final_k]
            fail_hits = sum(1 for idx in topk_indices if truth_failed_flags[idx] is True)
            return fail_hits / float(observed_fail_total)

        while True:
            for idx in ranking[:k_current]:
                ensure_truth(idx)

            if self.level0_guard_mode == "legacy_truth_score":
                evaluated_indices = [idx for idx in ranking[:k_current] if truth_scores[idx] is not None]
                evaluated_sorted = sorted(
                    evaluated_indices,
                    key=lambda i: float(truth_scores[i]),
                    reverse=True,
                )
                if len(evaluated_sorted) < n_seed:
                    gamma_mode = "full_truth_fallback"
                    fallback_triggered = True
                    fallback_reason = "insufficient_topk_truth"
                    if failure_label_guard_active:
                        failure_label_fallback_reason = "insufficient_topk_truth"
                    break

                gamma_candidate = float(truth_scores[evaluated_sorted[n_seed - 1]])
            else:
                gamma_candidate = None

            audit_start = k_current
            audit_end = min(n_samples, audit_start + self.level0_prescreen_tail_audit)
            audit_indices = ranking[audit_start:audit_end]
            tail_audit_count += len(audit_indices)
            audited_indices_seen.update(audit_indices)

            hits_this_round = 0
            failure_hits_this_round = 0
            for idx in audit_indices:
                payload = ensure_truth_payload(idx)
                score = as_float(payload.get("s_any", float("inf")))
                truth_failed = ensure_truth_failed(idx)
                if truth_failed:
                    tail_audit_truth_fail_count += 1
                    failure_hits_this_round += 1
                if self.level0_guard_mode == "legacy_truth_score":
                    if score >= gamma_candidate:
                        hits_this_round += 1
                        if truth_failed:
                            tail_audit_hit_fail_count += 1
                        if as_float(payload.get("s_line", float("-inf"))) >= gamma_candidate:
                            tail_audit_hit_line_count += 1
                        if as_float(payload.get("s_volt", float("-inf"))) >= gamma_candidate:
                            tail_audit_hit_volt_count += 1
                elif truth_failed:
                    hits_this_round += 1
                    tail_audit_hit_fail_count += 1

            rank_inversion_hits += hits_this_round
            failure_label_rank_inversion_hits += failure_hits_this_round

            if failure_label_guard_active and failure_label_guard_passed is not True and failure_hits_this_round == 0:
                failure_label_guard_passed = True
                failure_label_fallback_reason = "none"

            if hits_this_round == 0:
                guard_passed = True
                break

            if expand_rounds >= self.level0_prescreen_max_expand_rounds or k_current >= n_samples:
                gamma_mode = "full_truth_fallback"
                fallback_triggered = True
                fallback_reason = "rank_inversion_guard_exceeded"
                if failure_label_guard_active and failure_label_guard_passed is not True:
                    failure_label_fallback_reason = "rank_inversion_guard_exceeded"
                break

            expand_rounds += 1
            expanded = int(math.ceil(k_current * self.level0_prescreen_expand_factor))
            k_current = min(n_samples, max(k_current + 1, expanded))

        if not guard_passed:
            if not self.level0_prescreen_fallback_full_truth:
                fallback_triggered = True
                if fallback_reason == "none":
                    fallback_reason = "guard_failed_no_full_truth_fallback"
                guard_passed = False
            else:
                for idx in range(n_samples):
                    ensure_truth(idx)
                out_scores = [float(score) for score in truth_scores if score is not None]
                final_k = n_samples
                topk_indices = ranking[:final_k]
                meta = {
                    **self._default_l0_meta(),
                    "l0_prescreen_enabled": True,
                    "l0_proxy_calls": int(proxy_calls),
                    "l0_truth_calls": int(truth_calls),
                    "l0_guard_active": True,
                    "l0_guard_mode": self.level0_guard_mode,
                    "l0_prescreen_K_initial": int(k_initial),
                    "l0_prescreen_K_final": int(n_samples),
                    "l0_prescreen_expand_rounds": int(expand_rounds),
                    "l0_tail_audit_count": int(tail_audit_count),
                    "l0_tail_audit_failure_hits": int(tail_audit_truth_fail_count),
                    "l0_rank_inversion_hits": int(rank_inversion_hits),
                    "l0_failure_recall_inside_final_k": failure_recall_inside(n_samples),
                    "l0_failure_recall_inside_final_k_observed": failure_recall_inside_observed(
                        n_samples
                    ),
                    "l0_failure_label_rank_inversion_hits": int(
                        failure_label_rank_inversion_hits
                    ),
                    "l0_failure_label_guard_passed": failure_label_guard_passed
                    if failure_label_guard_active
                    else "not_applicable",
                    "l0_failure_label_fallback_reason": failure_label_fallback_reason,
                    "l0_guard_passed": False,
                    "l0_gamma1_mode": gamma_mode,
                    "l0_gamma1_candidate": float(gamma_candidate)
                    if gamma_candidate is not None
                    else None,
                    "l0_fallback_triggered": True,
                    "l0_fallback_reason": fallback_reason,
                    "l0_tail_audit_truth_fail_count": int(tail_audit_truth_fail_count),
                    "l0_tail_audit_hit_fail_count": int(tail_audit_hit_fail_count),
                    "l0_tail_audit_hit_line_count": int(tail_audit_hit_line_count),
                    "l0_tail_audit_hit_volt_count": int(tail_audit_hit_volt_count),
                    "l0_proxy_fail_count": int(proxy_fail_count),
                    "l0_proxy_inf_count": int(proxy_inf_count),
                    "l0_proxy_fail_in_topk_count": int(
                        sum(
                            1
                            for i in topk_indices
                            if not bool(proxy_payloads[i].get("success", False))
                        )
                    ),
                    "l0_proxy_inf_in_topk_count": int(
                        sum(
                            1
                            for i in topk_indices
                            if math.isinf(proxy_scores[i]) and float(proxy_scores[i]) > 0
                        )
                    ),
                    "l0_proxy_fail_in_audit_count": int(
                        sum(
                            1
                            for i in audited_indices_seen
                            if not bool(proxy_payloads[i].get("success", False))
                        )
                    ),
                    "l0_proxy_inf_in_audit_count": int(
                        sum(
                            1
                            for i in audited_indices_seen
                            if math.isinf(proxy_scores[i]) and float(proxy_scores[i]) > 0
                        )
                    ),
                }
                return out_scores, truth_calls, proxy_calls, meta

        evaluated_truth = [
            float(score) for score in truth_scores if score is not None and math.isfinite(float(score))
        ]
        sentinel = (min(evaluated_truth) - 1.0) if evaluated_truth else -1.0
        out_scores = [float(sentinel) for _ in range(n_samples)]
        for idx, score in enumerate(truth_scores):
            if score is not None:
                out_scores[idx] = float(score)

        final_k = k_current
        topk_indices = ranking[:final_k]
        meta = {
            **self._default_l0_meta(),
            "l0_prescreen_enabled": True,
            "l0_proxy_calls": int(proxy_calls),
            "l0_truth_calls": int(truth_calls),
            "l0_guard_active": True,
            "l0_guard_mode": self.level0_guard_mode,
            "l0_prescreen_K_initial": int(k_initial),
            "l0_prescreen_K_final": int(k_current),
            "l0_prescreen_expand_rounds": int(expand_rounds),
            "l0_tail_audit_count": int(tail_audit_count),
            "l0_tail_audit_failure_hits": int(tail_audit_truth_fail_count),
            "l0_rank_inversion_hits": int(rank_inversion_hits),
            "l0_failure_recall_inside_final_k": failure_recall_inside(k_current),
            "l0_failure_recall_inside_final_k_observed": failure_recall_inside_observed(
                k_current
            ),
            "l0_failure_label_rank_inversion_hits": int(failure_label_rank_inversion_hits),
            "l0_failure_label_guard_passed": failure_label_guard_passed
            if failure_label_guard_active
            else "not_applicable",
            "l0_failure_label_fallback_reason": failure_label_fallback_reason,
            "l0_guard_passed": bool(guard_passed),
            "l0_gamma1_mode": gamma_mode,
            "l0_fallback_triggered": bool(fallback_triggered),
            "l0_fallback_reason": fallback_reason,
            "l0_tail_audit_truth_fail_count": int(tail_audit_truth_fail_count),
            "l0_tail_audit_hit_fail_count": int(tail_audit_hit_fail_count),
            "l0_tail_audit_hit_line_count": int(tail_audit_hit_line_count),
            "l0_tail_audit_hit_volt_count": int(tail_audit_hit_volt_count),
            "l0_proxy_fail_count": int(proxy_fail_count),
            "l0_proxy_inf_count": int(proxy_inf_count),
            "l0_proxy_fail_in_topk_count": int(
                sum(
                    1
                    for i in topk_indices
                    if not bool(proxy_payloads[i].get("success", False))
                )
            ),
            "l0_proxy_inf_in_topk_count": int(
                sum(
                    1
                    for i in topk_indices
                    if math.isinf(proxy_scores[i]) and float(proxy_scores[i]) > 0
                )
            ),
            "l0_proxy_fail_in_audit_count": int(
                sum(
                    1
                    for i in audited_indices_seen
                    if not bool(proxy_payloads[i].get("success", False))
                )
            ),
            "l0_proxy_inf_in_audit_count": int(
                sum(
                    1
                    for i in audited_indices_seen
                    if math.isinf(proxy_scores[i]) and float(proxy_scores[i]) > 0
                )
            ),
        }
        if gamma_candidate is not None:
            meta["l0_gamma1_candidate"] = float(gamma_candidate)
        return out_scores, truth_calls, proxy_calls, meta

    def _select_top_seed_indices(self, scores: Sequence[float], n_seed: int) -> List[int]:
        ranking = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return ranking[:n_seed]

    def _build_level_log(
        self,
        level: int,
        threshold: float,
        scores: Sequence[float],
        n_samples: int,
        n_seed: int,
    ) -> Dict[str, Any]:
        finite_scores = [float(s) for s in scores if math.isfinite(float(s))]
        n_finite = len(finite_scores)
        n_infinite = int(len(scores) - n_finite)
        mean_finite_score = (
            float(statistics.fmean(finite_scores)) if n_finite > 0 else None
        )
        return {
            "level": level,
            "threshold": float(threshold),
            "n_samples": int(n_samples),
            "n_seed": int(n_seed),
            "min_score": float(min(scores)),
            "max_score": float(max(scores)),
            "mean_score": float(statistics.fmean(scores)),
            "n_infinite_score": n_infinite,
            "mean_finite_score": mean_finite_score,
            "finite_fraction": (n_finite / float(n_samples)) if n_samples > 0 else 0.0,
            "n_fail_like": int(sum(1 for s in scores if s >= self.target_violation)),
        }

    def _evolve_next_level_truth_only(
        self,
        *,
        seed_states: Sequence[Mapping[str, Any]],
        seed_scores: Sequence[float],
        threshold: float,
        n_samples: int,
        seed: int | None,
    ) -> tuple[List[Dict[str, Any]], List[float], Dict[str, Any]]:
        sampler = LineOnlyMMHSampler(
            self.case_name,
            self.config,
            truth_mode=self.truth_mode,
        )
        sampler._evaluate_score = self._timed_truth_score  # type: ignore[method-assign]
        next_states, next_scores, sampler_stats = sampler.sample_batch(
            seed_states,
            seed_scores,
            threshold,
            n_samples,
            seed=seed,
        )

        attempts = int(sampler_stats.get("attempts", 0))
        stage1_rejects = int(sampler_stats.get("constraint_rejects", 0))
        stage1_pass = int(max(0, attempts - stage1_rejects))
        stage2_pass = int(sampler_stats.get("accepted", 0))

        call_meta = {
            "attempts": attempts,
            "stage1_rejects": stage1_rejects,
            "stage1_pass": stage1_pass,
            "stage2_pass": stage2_pass,
            "n_proxy_calls": 0,
            "n_truth_calls": attempts,
            "stage1_reject_ratio": None,
            "stage2_accept_ratio": None,
            "stage1_reject_shadow_eval_count": 0,
            "stage1_reject_shadow_truth_pass_count": 0,
            "stage1_reject_shadow_truth_fail_count": 0,
            "stage1_reject_shadow_truth_accept_rate": None,
            "sampler_stats": sampler_stats,
        }
        return next_states, next_scores, call_meta

    def _evolve_next_level_proxy_only(
        self,
        *,
        seed_states: Sequence[Mapping[str, Any]],
        seed_scores: Sequence[float],
        threshold: float,
        n_samples: int,
        seed: int | None,
    ) -> tuple[List[Dict[str, Any]], List[float], Dict[str, Any]]:
        sampler = LineOnlyMMHSampler(
            self.case_name,
            self.config,
            truth_mode=self.truth_mode,
        )
        rng = random.Random(seed)

        chains = [copy.deepcopy(dict(s)) for s in seed_states]
        chain_scores = [float(s) for s in seed_scores]

        next_states: List[Dict[str, Any]] = []
        next_scores: List[float] = []

        for s, sc in zip(chains, chain_scores):
            if len(next_states) >= n_samples:
                break
            next_states.append(copy.deepcopy(s))
            next_scores.append(float(sc))

        stats = {
            "attempts": 0,
            "accepted": 0,
            "acceptance_rate": 0.0,
            "constraint_rejects": 0,
            "mh_rejects": 0,
            "move_counts": {"add": 0, "remove": 0, "swap": 0},
            "accepted_move_counts": {"add": 0, "remove": 0, "swap": 0},
            "n_returned": 0,
            "unique_state_count": 0,
        }

        n_proxy_calls = 0
        stage1_rejects = 0
        stage1_pass = 0
        stage2_pass = 0

        chain_idx = 0
        while len(next_states) < n_samples:
            ci = chain_idx % len(chains)
            current_state = chains[ci]
            current_score = chain_scores[ci]

            proposed_state, proposal_terms = sampler._propose_state(
                current_state,
                rng,
            )
            move = str(proposal_terms["move"])
            prior_ratio = float(proposal_terms["prior_ratio"])
            q_ratio = float(proposal_terms["q_ratio"])

            stats["attempts"] += 1
            stats["move_counts"][move] += 1

            proxy_payload = eval_proxy(
                self.case_name,
                proposed_state,
                self.config,
                proxy_mode=self.proxy_mode,
                debug=False,
            )
            proposed_score = float(proxy_payload["s_any"])
            n_proxy_calls += 1

            if proposed_score < threshold:
                stage1_rejects += 1
                stats["constraint_rejects"] += 1
            else:
                stage1_pass += 1
                alpha = min(1.0, prior_ratio * q_ratio)
                if rng.random() < alpha:
                    chains[ci] = proposed_state
                    chain_scores[ci] = proposed_score
                    current_state = proposed_state
                    current_score = proposed_score
                    stats["accepted"] += 1
                    stats["accepted_move_counts"][move] += 1
                    stage2_pass += 1
                else:
                    stats["mh_rejects"] += 1

            next_states.append(copy.deepcopy(current_state))
            next_scores.append(float(current_score))
            chain_idx += 1

        attempts = int(stats["attempts"])
        stats["acceptance_rate"] = (
            stats["accepted"] / float(attempts) if attempts > 0 else 0.0
        )
        stats["n_returned"] = len(next_states)
        stats["unique_state_count"] = self._unique_state_count(next_states)

        call_meta = {
            "attempts": attempts,
            "stage1_rejects": stage1_rejects,
            "stage1_pass": stage1_pass,
            "stage2_pass": stage2_pass,
            "n_proxy_calls": n_proxy_calls,
            "n_truth_calls": 0,
            "stage1_reject_ratio": None,
            "stage2_accept_ratio": None,
            "stage1_reject_shadow_eval_count": 0,
            "stage1_reject_shadow_truth_pass_count": 0,
            "stage1_reject_shadow_truth_fail_count": 0,
            "stage1_reject_shadow_truth_accept_rate": None,
            "sampler_stats": stats,
        }
        return next_states, next_scores, call_meta

    def _evolve_next_level_delayed_acceptance(
        self,
        *,
        seed_states: Sequence[Mapping[str, Any]],
        seed_scores: Sequence[float],
        threshold: float,
        n_samples: int,
        seed: int | None,
    ) -> tuple[List[Dict[str, Any]], List[float], Dict[str, Any]]:
        sampler = LineOnlyMMHSampler(
            self.case_name,
            self.config,
            truth_mode=self.truth_mode,
        )
        rng = random.Random(seed)

        chains = [copy.deepcopy(dict(s)) for s in seed_states]
        chain_scores = [float(s) for s in seed_scores]  # truth scores

        next_states: List[Dict[str, Any]] = []
        next_scores: List[float] = []

        for s, sc in zip(chains, chain_scores):
            if len(next_states) >= n_samples:
                break
            next_states.append(copy.deepcopy(s))
            next_scores.append(float(sc))

        stats = {
            "attempts": 0,
            "accepted": 0,
            "acceptance_rate": 0.0,
            "constraint_rejects": 0,
            "mh_rejects": 0,
            "stage2_gate_rejects": 0,
            "reverse_proxy_rejects": 0,
            "move_counts": {"add": 0, "remove": 0, "swap": 0},
            "accepted_move_counts": {"add": 0, "remove": 0, "swap": 0},
            "n_returned": 0,
            "unique_state_count": 0,
            "da_hastings_debug": [],
        }

        n_proxy_calls = 0
        n_truth_calls = 0
        stage1_rejects = 0
        stage1_pass = 0
        stage2_pass = 0
        stage1_reject_shadow_eval_count = 0
        stage1_reject_shadow_truth_pass_count = 0
        stage1_reject_shadow_truth_fail_count = 0

        chain_idx = 0
        while len(next_states) < n_samples:
            ci = chain_idx % len(chains)
            current_state = chains[ci]
            current_score = chain_scores[ci]

            proposed_state, proposal_terms = sampler._propose_state(
                current_state,
                rng,
            )
            move = str(proposal_terms["move"])
            prior_ratio = float(proposal_terms["prior_ratio"])
            q_forward = float(proposal_terms["q_forward"])
            q_reverse = float(proposal_terms["q_reverse"])
            q_ratio = float(proposal_terms["q_ratio"])

            stats["attempts"] += 1
            stats["move_counts"][move] += 1

            proxy_payload = eval_proxy(
                self.case_name,
                proposed_state,
                self.config,
                proxy_mode=self.proxy_mode,
                debug=False,
            )
            proxy_score = float(proxy_payload["s_any"])
            n_proxy_calls += 1

            if proxy_score < threshold:
                stage1_rejects += 1
                stats["constraint_rejects"] += 1
                if self.audit_shadow_prob > 0.0 and rng.random() < self.audit_shadow_prob:
                    truth_shadow_score = self._timed_truth_score(proposed_state)
                    n_truth_calls += 1
                    stage1_reject_shadow_eval_count += 1
                    if truth_shadow_score >= threshold:
                        stage1_reject_shadow_truth_pass_count += 1
                    else:
                        stage1_reject_shadow_truth_fail_count += 1
            else:
                stage1_pass += 1
                truth_score = self._timed_truth_score(proposed_state)
                n_truth_calls += 1

                if truth_score < threshold:
                    stats["constraint_rejects"] += 1
                    stats["stage2_gate_rejects"] += 1
                else:
                    alpha_raw = prior_ratio * q_ratio
                    reverse_proxy_score: float | None = None
                    reverse_proxy_pass = True

                    if self.enable_hastings_correction:
                        reverse_proxy_payload = eval_proxy(
                            self.case_name,
                            current_state,
                            self.config,
                            proxy_mode=self.proxy_mode,
                            debug=False,
                        )
                        reverse_proxy_score = float(reverse_proxy_payload["s_any"])
                        reverse_proxy_pass = reverse_proxy_score >= threshold
                        n_proxy_calls += 1

                    reverse_gate_ratio = 1.0 if reverse_proxy_pass else 0.0
                    alpha = min(1.0, alpha_raw * reverse_gate_ratio)

                    debug_record = {
                        "attempt": int(stats["attempts"]),
                        "move": move,
                        "threshold": float(threshold),
                        "q_forward": q_forward,
                        "q_reverse": q_reverse,
                        "q_ratio": q_ratio,
                        "prior_ratio": prior_ratio,
                        "forward_proxy_score": proxy_score,
                        "reverse_proxy_score": reverse_proxy_score,
                        "reverse_proxy_pass": reverse_proxy_pass,
                        "truth_score": truth_score,
                        "alpha_raw": alpha_raw,
                        "alpha": alpha,
                        "enable_hastings_correction": self.enable_hastings_correction,
                    }
                    stats["da_hastings_debug"].append(debug_record)

                    if self.da_debug_print and len(stats["da_hastings_debug"]) <= self.da_debug_max_logs:
                        LOGGER.debug(
                            "DA Hastings attempt=%s move=%s threshold=%.6g "
                            "alpha_raw=%.6g reverse_proxy_pass=%s alpha=%.6g details=%s",
                            debug_record["attempt"],
                            move,
                            float(threshold),
                            alpha_raw,
                            reverse_proxy_pass,
                            alpha,
                            json.dumps(debug_record, sort_keys=True),
                        )

                    if self.enable_hastings_correction and not reverse_proxy_pass:
                        stats["reverse_proxy_rejects"] += 1

                    stage2_pass += 1
                    if rng.random() < alpha:
                        chains[ci] = proposed_state
                        chain_scores[ci] = truth_score
                        current_state = proposed_state
                        current_score = truth_score
                        stats["accepted"] += 1
                        stats["accepted_move_counts"][move] += 1
                    else:
                        stats["mh_rejects"] += 1

            next_states.append(copy.deepcopy(current_state))
            next_scores.append(float(current_score))
            chain_idx += 1

        attempts = int(stats["attempts"])
        stats["acceptance_rate"] = (
            stats["accepted"] / float(attempts) if attempts > 0 else 0.0
        )
        stats["n_returned"] = len(next_states)
        stats["unique_state_count"] = self._unique_state_count(next_states)
        stats["stage1_reject_shadow_eval_count"] = stage1_reject_shadow_eval_count
        stats["stage1_reject_shadow_truth_pass_count"] = stage1_reject_shadow_truth_pass_count
        stats["stage1_reject_shadow_truth_fail_count"] = stage1_reject_shadow_truth_fail_count
        stats["stage1_reject_shadow_truth_accept_rate"] = (
            stage1_reject_shadow_truth_pass_count / float(stage1_reject_shadow_eval_count)
            if stage1_reject_shadow_eval_count > 0
            else None
        )

        call_meta = {
            "attempts": attempts,
            "stage1_rejects": stage1_rejects,
            "stage1_pass": stage1_pass,
            "stage2_pass": stage2_pass,
            "n_proxy_calls": n_proxy_calls,
            "n_truth_calls": n_truth_calls,
            "stage1_reject_ratio": stage1_rejects / float(attempts) if attempts > 0 else 0.0,
            "stage2_accept_ratio": stage2_pass / float(stage1_pass) if stage1_pass > 0 else 0.0,
            "stage1_reject_shadow_eval_count": stage1_reject_shadow_eval_count,
            "stage1_reject_shadow_truth_pass_count": stage1_reject_shadow_truth_pass_count,
            "stage1_reject_shadow_truth_fail_count": stage1_reject_shadow_truth_fail_count,
            "stage1_reject_shadow_truth_accept_rate": stats[
                "stage1_reject_shadow_truth_accept_rate"
            ],
            "sampler_stats": stats,
        }
        return next_states, next_scores, call_meta

    @staticmethod
    def _normalize_line_only_state(state: Mapping[str, Any]) -> Dict[str, Any]:
        out = copy.deepcopy(dict(state))
        out["line_out"] = [int(v) for v in out.get("line_out", [])]

        bus_out = list(out.get("bus_out", []))
        out["bus_out"] = [0 for _ in bus_out]

        gen_scale = list(out.get("gen_scale", []))
        out["gen_scale"] = [1.0 for _ in gen_scale]

        gen_derate = list(out.get("gen_derate_state", []))
        out["gen_derate_state"] = [0 for _ in gen_derate]

        return out

    @staticmethod
    def _unique_state_count(states: Sequence[Mapping[str, Any]]) -> int:
        return len(
            {
                json.dumps(dict(s), sort_keys=True, separators=(",", ":"))
                for s in states
            }
        )

    def _timed_truth_score(self, state: Mapping[str, Any]) -> float:
        payload = self._timed_truth_payload(state)
        return float(payload["s_any"])

    def _timed_truth_payload(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        try:
            return eval_truth(
                self.case_name,
                state,
                self.config,
                truth_mode=self.truth_mode,
                debug=False,
            )
        finally:
            self._truth_engine_time += time.perf_counter() - started
