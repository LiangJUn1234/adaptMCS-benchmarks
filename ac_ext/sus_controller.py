"""Subset Simulation controller with Phase 6B evaluator paths."""

from __future__ import annotations

import copy
import json
import math
import random
import statistics
from typing import Any, Dict, List, Mapping, Sequence

from .config import DEFAULTS
from .mcmc_sampler import LineOnlyMMHSampler
from .problem import eval_proxy, eval_single_damaged_case, sample_X


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
        self._last_sampler_stats: Dict[str, Any] | None = None

        if not (0.0 < self.p0 <= 1.0):
            raise ValueError("sus_p0 must be in (0, 1]")
        if self.truth_mode not in {"acopf", "acpf", "dcpf"}:
            raise ValueError("truth_mode must be one of: acopf, acpf, dcpf")
        if self.proxy_mode not in {"dcpf", "fdxb", "dcopf"}:
            raise ValueError("proxy_mode must be one of: dcpf, fdxb, dcopf")

    def run(self, n_samples: int, seed: int | None = None) -> dict:
        if n_samples <= 0:
            raise ValueError("n_samples must be positive")

        if self.evaluator_mode not in {"truth_only", "proxy_only", "delayed_acceptance"}:
            raise ValueError(
                "Unsupported evaluator_mode. Use truth_only, proxy_only, or delayed_acceptance."
            )

        states = self._initial_states(n_samples, seed)

        if self.evaluator_mode == "proxy_only":
            scores, init_proxy_calls = self._evaluate_states_proxy(states)
            init_truth_calls = 0
        else:
            scores, init_truth_calls = self._evaluate_states_truth(states)
            init_proxy_calls = 0

        total_proxy_calls = init_proxy_calls
        total_truth_calls = init_truth_calls
        total_attempts = 0
        total_stage1_rejects = 0
        total_stage1_pass = 0
        total_stage2_pass = 0

        current_level_meta = {
            "n_proxy_calls": init_proxy_calls,
            "n_truth_calls": init_truth_calls,
            "stage1_reject_ratio": None,
            "stage2_accept_ratio": None,
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
                }
            )
            if self._last_sampler_stats is not None:
                level_log["sampler_stats"] = copy.deepcopy(self._last_sampler_stats)
            level_logs.append(level_log)

            if math.isinf(threshold) and threshold > 0:
                return self._build_final_output(
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
                )

            if threshold >= self.target_violation:
                return self._build_final_output(
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
                )

            if level + 1 >= self.max_levels:
                return self._build_final_output(
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
                )

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
            bundle = eval_single_damaged_case(
                self.case_name,
                state,
                self.config,
                debug=False,
            )
            scores.append(float(bundle[self.truth_mode]["s_any"]))
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

            proposed_state, move, prior_ratio, proposal_ratio = sampler._propose_state(
                current_state,
                rng,
            )

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
                alpha = min(1.0, float(prior_ratio) * float(proposal_ratio))
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
            "move_counts": {"add": 0, "remove": 0, "swap": 0},
            "accepted_move_counts": {"add": 0, "remove": 0, "swap": 0},
            "n_returned": 0,
            "unique_state_count": 0,
        }

        n_proxy_calls = 0
        n_truth_calls = 0
        stage1_rejects = 0
        stage1_pass = 0
        stage2_pass = 0

        chain_idx = 0
        while len(next_states) < n_samples:
            ci = chain_idx % len(chains)
            current_state = chains[ci]
            current_score = chain_scores[ci]

            proposed_state, move, prior_ratio, proposal_ratio = sampler._propose_state(
                current_state,
                rng,
            )

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
            else:
                stage1_pass += 1
                truth_bundle = eval_single_damaged_case(
                    self.case_name,
                    proposed_state,
                    self.config,
                    debug=False,
                )
                truth_score = float(truth_bundle[self.truth_mode]["s_any"])
                n_truth_calls += 1

                if truth_score < threshold:
                    stats["constraint_rejects"] += 1
                    stats["stage2_gate_rejects"] += 1
                else:
                    stage2_pass += 1
                    alpha = min(1.0, float(prior_ratio) * float(proposal_ratio))
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

        call_meta = {
            "attempts": attempts,
            "stage1_rejects": stage1_rejects,
            "stage1_pass": stage1_pass,
            "stage2_pass": stage2_pass,
            "n_proxy_calls": n_proxy_calls,
            "n_truth_calls": n_truth_calls,
            "stage1_reject_ratio": stage1_rejects / float(attempts) if attempts > 0 else 0.0,
            "stage2_accept_ratio": stage2_pass / float(stage1_pass) if stage1_pass > 0 else 0.0,
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
