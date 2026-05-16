# Overall Project Summary Before A4 — Part 1: Project Status

## 1. 当前阶段判断
- A1 completed: Level-0 guard objective alignment 已完成并冻结。
- A2 completed and closed: simple score tuning（base-margin / percentile / hybrid / failed-severity tie-break）已完成，进入“饱和”结论。
- DA trace completed: proposal-level trace 与代表性分析已完成（seed901, N=1000, lop=0.008）。
- Certificate audit completed: DCOPF failure 作为 ACOPF failure empirical certificate 的精度已审计。
- Next stage: A4 formulation-prep / certificate-aware branching。

## 2. 项目目标（进入 A4 前保持不变）
- 降低昂贵 ACOPF truth calls。
- 保持 rare-event ACOPF failure screening 的安全性。
- 保持 pf_hat 稳定。
- 以 DCOPF 作为 fast physics proxy，逐步走向 ACOPF-guided parameter optimization。

## 3. 阶段定义（当前语义）
- A1: Level-0 objective alignment（从 ACOPF s_any 排名保护切换到 ACOPF failure membership 保护）。
- A2: score-level DCOPF tuning（离线）并确认 simple scalar family 的性能边界。
- DA trace: proposal-level DA 行为透明化，定位剩余 truth calls 来源。
- Certificate audit: 量化 `P(ACOPF failure | DCOPF failure)` 与 false-certificate 风险。
- A4: certificate-aware / parameterized DCOPF optimization（下一阶段）。

## 4. 当前不能过度声明
- 还不是 formulation-level DCOPF optimization 完成态。
- 不能声称 DCOPF 与 ACOPF 等价。
- 不能声称 shortcut 已可无条件上线。
- A4 仍是下一阶段工作，不是已完成结果。
