# A2.2b Failed-State Severity Tie-Break

- eval seeds: `300`
- generator severity status: `generator severity available`
- tested score variants: `15`
- tested guard rows: `150`
- pass_all_lops rows: `30`

## Limitation

- This v001 only adds tie-breaking among DCOPF-failed states from damage severity proxies.
- It does not reconstruct failed DCOPF flow solutions and does not claim physics severity fidelity for failed solves.

## Best Configuration

- score: `raw_success_fail`
- K_initial: `200`
- tail_audit: `25`
- expand_factor: `1.5`
- pass_all_lops: `True`
- mean_l0_truth_calls: `225.0`
- max_K_final: `200`
- max_tail_audit_failure_hits: `0`
