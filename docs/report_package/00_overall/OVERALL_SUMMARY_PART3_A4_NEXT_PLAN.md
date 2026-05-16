# Overall Project Summary Before A4 — Part 3: A4 Next Plan

## 1. Why A4 is next
- A1 已完成 objective alignment。
- A2 simple score tuning 已出现 ceiling。
- DA trace 说明剩余调用主要集中在 DCOPF-failed proposal confirmation。
- certificate audit 显示高精度但非零 false-certificate 风险。
- 因此下一步应进入 certificate-aware / parameterized DCOPF optimization（A4）。

## 2. A4 branching

### Branch 1: Certificate route
- 目标：设计 regime-gated `certified_dcopf_failure_shortcut` 候选。
- 适用前提：目标 regime 下 false-certificate 风险可控且有 fallback。
- 收益目标：减少 DA confirmation truth calls。
- 安全要求：明确风险报告、禁用默认、可回退。

### Branch 2: Parameterization route
- 目标：通过 grouped coefficient/bias + finite-difference sensitivity，优化 screening loss。
- 工具方向：L-BFGS-B / TNC / quasi-Newton 风格离线优化。
- 约束：优化目标是 screening loss，不是 dispatch loss 复刻。

## 3. Recommended immediate A4 tasks
1. 基于 certificate audit 构建 regime-gating table（seed/lop 风险层级）。
2. 定义 shortcut 安全规则（何时允许、何时强制 truth）。
3. 设计小规模 offline shortcut effect test（仅离线重放，不改线上决策）。
4. 设计 grouped-parameter finite-difference smoke（先验证梯度信号可用性）。
5. 保持 raw DCOPF + failure_label 作为稳定 baseline。

## 4. Decision rules
- 若 certificate route 在 validation regime 可零（或可接受）false-certificate 且显著降 truth calls，可进入在线受控实验。
- 若 target regime 有非可接受风险，不做盲目 shortcut。
- 若 parameter perturbation 对 screening loss 存在稳定梯度，进入 grouped optimizer。
- 若梯度信号弱，再考虑更强 formulation sensitivity 或 graph-aware 扩展。
