"""Truth-only Subset Simulation controller skeleton (Phase 6A)."""

from __future__ import annotations

import copy
import math
import random
import statistics
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .config import DEFAULTS
from .mcmc_sampler import LineOnlyMMHSampler
from .problem import eval_single_damaged_case, sample_X


class SuSController:
    """Subset Simulation controller (Phase 6A scope)."""

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
        self._last_sampler_stats: Dict[str, Any] | None = None

        if not (0.0 < self.p0 <= 1.0):
            raise ValueError("p0 must be in (0, 1]")
        if self.truth_mode not in {"acopf", "acpf", "dcpf"}:
            raise ValueError("truth_mode must be one of: acopf, acpf, dcpf")

    def run(self, n_samples: int, seed: int | None = None) -> dict:
        if n_samples <= 0:
            raise ValueError("n_samples must be positive")

        if self.evaluator_mode == "delayed_acceptance":
            raise NotImplementedError(
                "delayed_acceptance mode is intentionally deferred in Phase 6A."
            )
        if self.evaluator_mode == "proxy_only":
            raise NotImplementedError(
                "proxy_only mode is not implemented in Phase 6A."
            )
        if self.evaluator_mode != "truth_only":
            raise ValueError(
                "Unsupported evaluator_mode. Use truth_only, proxy_only, or delayed_acceptance."
            )

        states = self._initial_states(n_samples, seed)
        scores = self._evaluate_states(states)

        level_logs: List[Dict[str, Any]] = []
        level = 0

        while True:
            n_seed = int(math.ceil(self.p0 * n_samples))
            seed_idx = self._select_top_seed_indices(scores, n_seed)
            threshold = float(scores[seed_idx[-1]])

            level_log = self._build_level_log(level, threshold, scores, n_samples, n_seed)
            if self._last_sampler_stats is not None:
                level_log["sampler_stats"] = copy.deepcopy(self._last_sampler_stats)
            level_logs.append(level_log)

            if math.isinf(threshold) and threshold > 0:
                n_fail_like = sum(1 for s in scores if s >= self.target_violation)
                pf_hat = (self.p0 ** level) * (n_fail_like / float(n_samples))
                return {
                    "mode": self.evaluator_mode,
                    "truth_mode": self.truth_mode,
                    "target_violation": self.target_violation,
                    "n_samples": n_samples,
                    "n_levels": level + 1,
                    "pf_hat": pf_hat,
                    "termination_reason": "threshold_reached_infinite",
                    "level_logs": level_logs,
                }

            if threshold >= self.target_violation:
                n_fail_like = sum(1 for s in scores if s >= self.target_violation)
                pf_hat = (self.p0 ** level) * (n_fail_like / float(n_samples))
                return {
                    "mode": self.evaluator_mode,
                    "truth_mode": self.truth_mode,
                    "target_violation": self.target_violation,
                    "n_samples": n_samples,
                    "n_levels": level + 1,
                    "pf_hat": pf_hat,
                    "termination_reason": "target_threshold_reached",
                    "level_logs": level_logs,
                }

            if level + 1 >= self.max_levels:
                n_fail_like = sum(1 for s in scores if s >= self.target_violation)
                pf_hat = (self.p0 ** level) * (n_fail_like / float(n_samples))
                return {
                    "mode": self.evaluator_mode,
                    "truth_mode": self.truth_mode,
                    "target_violation": self.target_violation,
                    "n_samples": n_samples,
                    "n_levels": level + 1,
                    "pf_hat": pf_hat,
                    "termination_reason": "max_levels_reached",
                    "level_logs": level_logs,
                }

            seed_states = [states[i] for i in seed_idx]
            seed_scores = [scores[i] for i in seed_idx]
            states, scores = self._evolve_next_level(
                seed_states=seed_states,
                seed_scores=seed_scores,
                threshold=threshold,
                n_samples=n_samples,
                seed=None if seed is None else seed + level + 1,
            )
            level += 1

    def _initial_states(self, n_samples: int, seed: int | None) -> List[Dict[str, Any]]:
        # Phase 6A restriction: line-only conditional sampling.
        cfg = dict(self.config)
        cfg["bus_outage_prob"] = 0.0
        cfg["gen_derate_state_values"] = (1.0,)
        cfg["gen_derate_state_probs"] = (1.0,)

        sampled = sample_X(self.case_name, cfg, n=n_samples, seed=seed)
        states = [self._normalize_line_only_state(s) for s in sampled]
        return states

    def _evaluate_states(self, states: Sequence[Mapping[str, Any]]) -> List[float]:
        scores: List[float] = []
        for state in states:
            bundle = eval_single_damaged_case(
                self.case_name,
                state,
                self.config,
                debug=False,
            )
            scores.append(float(bundle[self.truth_mode]["s_any"]))
        return scores

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

    def _evolve_next_level(
        self,
        *,
        seed_states: Sequence[Mapping[str, Any]],
        seed_scores: Sequence[float],
        threshold: float,
        n_samples: int,
        seed: int | None,
    ) -> tuple[List[Dict[str, Any]], List[float]]:
        sampler = LineOnlyMMHSampler(
            self.case_name,
            self.config,
            truth_mode=self.truth_mode,
        )
        next_states, next_scores, sampler_stats = sampler.sample_batch(
            seed_states,
            seed_scores,
            threshold,
            n_samples,
            seed=seed,
        )

        if len(next_states) != n_samples or len(next_scores) != n_samples:
            raise RuntimeError("_evolve_next_level must return exactly N states and N scores")

        self._last_sampler_stats = sampler_stats
        return next_states, next_scores

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
