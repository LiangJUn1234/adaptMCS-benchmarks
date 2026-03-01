"""Line-only discrete MMH sampler skeleton for Phase 6A."""

from __future__ import annotations

import copy
import json
import math
import random
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .problem import eval_single_damaged_case

__all__ = ["LineOnlyMMHSampler"]


class LineOnlyMMHSampler:
    """Line-only Modified Metropolis-Hastings sampler.

    This sampler keeps the canonical state dict shape and mutates only the
    `line_out` component using Add/Remove/Swap moves.
    """

    def __init__(
        self,
        case_name: str,
        config: Mapping[str, Any],
        *,
        truth_mode: str = "acopf",
    ) -> None:
        self.case_name = case_name
        self.config = dict(config)
        self.truth_mode = truth_mode

        p = float(self.config.get("line_outage_prob", 0.01))
        if not (0.0 < p < 1.0):
            raise ValueError(
                "line_outage_prob must be strictly between 0 and 1 for MH prior ratios."
            )
        self.line_outage_prob = p

    def sample_batch(
        self,
        seed_states: Sequence[Mapping[str, Any]],
        seed_scores: Sequence[float],
        threshold: float,
        n_samples: int,
        *,
        seed: int | None = None,
    ) -> tuple[List[Dict[str, Any]], List[float], Dict[str, Any]]:
        """Generate one conditional batch of exactly ``n_samples`` states."""
        if n_samples <= 0:
            raise ValueError("n_samples must be positive")
        if len(seed_states) == 0:
            raise ValueError("seed_states must be non-empty")
        if len(seed_states) != len(seed_scores):
            raise ValueError("seed_states and seed_scores must have equal length")

        rng = random.Random(seed)

        chains = [copy.deepcopy(dict(s)) for s in seed_states]
        chain_scores = [float(s) for s in seed_scores]

        next_states: List[Dict[str, Any]] = []
        next_scores: List[float] = []

        # Preserve selected seeds exactly as first members of the next level batch.
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
        }

        chain_idx = 0
        while len(next_states) < n_samples:
            ci = chain_idx % len(chains)
            current_state = chains[ci]
            current_score = chain_scores[ci]

            proposed_state, move, prior_ratio, proposal_ratio = self._propose_state(
                current_state,
                rng,
            )

            stats["attempts"] += 1
            stats["move_counts"][move] += 1

            proposed_score = self._evaluate_score(proposed_state)

            if proposed_score < threshold:
                stats["constraint_rejects"] += 1
            else:
                alpha = min(1.0, prior_ratio * proposal_ratio)
                if rng.random() < alpha:
                    chains[ci] = proposed_state
                    chain_scores[ci] = proposed_score
                    current_state = proposed_state
                    current_score = proposed_score
                    stats["accepted"] += 1
                    stats["accepted_move_counts"][move] += 1
                else:
                    stats["mh_rejects"] += 1

            next_states.append(copy.deepcopy(current_state))
            next_scores.append(float(current_score))
            chain_idx += 1

        attempts = stats["attempts"]
        stats["acceptance_rate"] = (
            stats["accepted"] / float(attempts) if attempts > 0 else 0.0
        )
        stats["n_returned"] = len(next_states)
        stats["unique_state_count"] = len(
            {
                json.dumps(state, sort_keys=True, separators=(",", ":"))
                for state in next_states
            }
        )

        return next_states, next_scores, stats

    def _evaluate_score(self, state: Mapping[str, Any]) -> float:
        result = eval_single_damaged_case(
            self.case_name,
            state,
            self.config,
            debug=False,
        )
        payload = result[self.truth_mode]
        return float(payload["s_any"])

    def _propose_state(
        self,
        state: Mapping[str, Any],
        rng: random.Random,
    ) -> tuple[Dict[str, Any], str, float, float]:
        proposed = copy.deepcopy(dict(state))
        line_out = list(proposed["line_out"])

        m = len(line_out)
        if m == 0:
            raise ValueError("line_out cannot be empty")

        k = sum(1 for x in line_out if int(x) == 1)
        move_probs = self._move_probabilities(k, m)
        moves = list(move_probs.keys())
        move_weights = list(move_probs.values())
        move = rng.choices(moves, weights=move_weights, k=1)[0]

        open_idx = [i for i, v in enumerate(line_out) if int(v) == 1]
        closed_idx = [i for i, v in enumerate(line_out) if int(v) == 0]

        if move == "add":
            j = rng.choice(closed_idx)
            line_out[j] = 1
            prior_ratio = self.line_outage_prob / (1.0 - self.line_outage_prob)
            q_fwd = move_probs["add"] * (1.0 / len(closed_idx))
            rev_probs = self._move_probabilities(k + 1, m)
            q_rev = rev_probs["remove"] * (1.0 / (k + 1))
            proposal_ratio = q_rev / q_fwd
        elif move == "remove":
            j = rng.choice(open_idx)
            line_out[j] = 0
            prior_ratio = (1.0 - self.line_outage_prob) / self.line_outage_prob
            q_fwd = move_probs["remove"] * (1.0 / len(open_idx))
            rev_probs = self._move_probabilities(k - 1, m)
            q_rev = rev_probs["add"] * (1.0 / (m - k + 1))
            proposal_ratio = q_rev / q_fwd
        else:  # swap
            i = rng.choice(open_idx)
            j = rng.choice(closed_idx)
            line_out[i] = 0
            line_out[j] = 1
            prior_ratio = 1.0
            proposal_ratio = 1.0

        proposed["line_out"] = line_out
        return proposed, move, float(prior_ratio), float(proposal_ratio)

    @staticmethod
    def _move_probabilities(k: int, m: int) -> Dict[str, float]:
        if k == 0:
            return {"add": 1.0}
        if k == m:
            return {"remove": 1.0}
        # Uniform across legal Add/Remove/Swap when 0 < k < M.
        return {"add": 1.0 / 3.0, "remove": 1.0 / 3.0, "swap": 1.0 / 3.0}
