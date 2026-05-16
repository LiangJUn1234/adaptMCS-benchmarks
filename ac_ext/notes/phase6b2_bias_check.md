# Phase 6B.2 Paired Bias Check Scope

This phase performs a paired repeated-run stability/bias check between:
- `truth_only + acopf`
- `delayed_acceptance + dcopf + acopf`

Key design intent:
- the same seed set is used for both arms,
- the goal is to separate systematic bias effects from seed-driven noise,
- no new estimator correction is introduced in this phase.
