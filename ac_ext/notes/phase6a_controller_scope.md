# Phase 6A Controller Scope

Phase 6A introduces scaffolding only:
- truth-only Subset Simulation controller in `ac_ext/sus_controller.py`
- line-only discrete MMH kernel in `ac_ext/mcmc_sampler.py`

Implemented in this phase:
- truth-only evaluator mode in SuS controller
- exact top-`p0` rank seed selection (`n_seed = ceil(p0 * N)`)
- level summary logs (no large raw arrays)
- line-only Add/Remove/Swap proposal moves with MH accounting and stats

Intentionally deferred:
- delayed-acceptance controller logic
- proxy-only control path
- bus-outage proposal moves
- generator-derating proposal moves

Phase 6A line-only restriction:
- conditional sampling is line-only
- bus outage probability is treated as zero in controller initialization
- generator derating is fixed and not mutated by MCMC proposals

MATLAB remains the source of truth for scalar score evaluation (`s_any`) through existing damaged-case truth interfaces.
