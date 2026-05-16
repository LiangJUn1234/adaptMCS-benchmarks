# Overall Project Summary Before A4 — Part 2: Results and Evidence

## A1-Guard freeze result（case118, N=1000, lop=0.008, seeds=901/902/903）

### legacy_truth_score
- mean truth_calls = 1320
- mean l0_truth_calls = 1000
- mean K_final = 1000
- mean pf_hat = 0.07945

### failure_label
- mean truth_calls = 577
- mean l0_truth_calls = 250
- mean K_final = 200
- mean pf_hat = 0.07945

### Interpretation
- 第一瓶颈是 guard objective mismatch，而非仅 DCOPF proxy 弱。
- failure-label guard 对齐 rare-event failure screening 目标后，truth calls 显著下降且 pf_hat 保持不变。

## A2 result（A2.1 + A2.2）
- `raw_success_fail` = best_overall。
- best_trained_physics = `base_margin_m1.2_e10`。
- pseudo-limit / base-margin / hybrid 未超越 raw baseline。
- `K_initial < 200` 对 all-lop 不安全（无法稳定 pass_all_lops）。
- `tail_audit` 可从 50 降到 25（在离线调优中显示可行余量）。
- simple failed-state severity tie-breaker 未优于 raw。
- 结论：simple scalar score tuning 已饱和，不建议继续仅扩 margin/q/epsilon 网格。

## DA trace result（representative run）
- run: corrected_da_dcopf + failure_label, seed901, N=1000, lop=0.008
- total DA proposals = 850
- stage1_accept = 282
- truth_evaluated = 282
- final_accept = 192
- reverse_proxy_reject = 25
- truth_evaluated & ACOPF failed = 282
- truth_evaluated & ACOPF safe = 0

### Interpretation
- A1 后剩余 DA-stage truth calls 主要是“确认 DCOPF-failed 提案”的调用，而不是大量检查 safe proposals 的浪费调用。

## Certificate audit result（case118 dataset）
- `P(ACOPF failure | DCOPF failure) = 0.998143`
- `dcopf_failed_count = 3770`
- `false_certificate_count = 7`
- `false_certificate_rate = 0.001857`
- `missed_failure_rate = 0.007124`
- problematic seed/lop regimes:
  - seed 7: lop 0.005, 0.008, 0.011, 0.014
  - seed 200: lop 0.014, 0.020

### Interpretation
- DCOPF failure 是高精度 empirical certificate，但不是 zero-error certificate。
- 不能无条件跳过 ACOPF truth，必须有 regime gating / safety rule / fallback 设计。

## Literature positioning
- Taheri & Molzahn 支持 AC/ACOPF-guided DC/DCPF/DCOPF 参数优化（offline train, online deploy）。
- 其主指标偏 dispatch/flow accuracy；本项目主指标是 failure screening / truth-call reduction。
- contingency screening 方向支持“failure-preserving screening”，但 DCOPF-not-AC-feasible 文献也提示不能过度等价化。
