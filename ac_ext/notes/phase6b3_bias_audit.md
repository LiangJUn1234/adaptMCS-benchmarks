# Phase 6B.3A Stage-1 False-Reject Audit

This phase audits only Stage-1 false rejects in delayed acceptance.

- Shadow truth evaluation is applied to a sampled subset of Stage-1 proxy rejects.
- Shadow truth evaluation is logging-only and does **not** affect chain state, transitions, or acceptance outcomes.
- The objective is to test whether the proxy gate discards proposals that would satisfy the truth threshold.
