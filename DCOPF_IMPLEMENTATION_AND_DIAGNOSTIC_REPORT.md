# DCOPF Implementation and Diagnostic Report

## 0. Executive Summary
- 当前可执行的 DCOPF 代理实现位于 `ac_ext/matlab/mp_run_dcopf_minimal.m`，Python 边界在 `ac_ext/matlab_engine.py::run_dcopf()`。
- 实际求解调用是 `runopf(mpc, mpopt)` 且 `mpopt.model='DC'`，不是 `rundcopf(...)`。
- damaged case 由 `mp_apply_damage_state_minimal.m` 构造：`line_out` 拉闸、`bus_out` 隔离母线并切断关联支路/机组、`gen_scale` 直接缩放 `PMAX`；`gen_derate_state` 不直接参与 MATPOWER 修改。
- score 定义是 `s_any = max(s_line, s_volt)`；solver fail 在默认 `ac_fail_as_violation=True` 下映射为 `success=False` 且 `s_line=s_volt=s_any=+inf`。
- 现有 case118 benchmark 中，`corrected_da_dcopf` 的 truth 调用节省主要来自 DA 上层 stage-1 过滤，而不是 Level-0 prescreen。
- Level-0 guard 对 DCOPF 排序仍不稳：N=500 时 `K_final=500`（实质全量 truth），N=1000 时 guard 失败并 fallback 全量 truth（`l0_truth_calls=N`）。
- 主要问题类型是 `D (Level-0 guard/expansion)` + `C (DC 物理近似)`，并伴随 `A/E`（score 用途耦合：同一 score 同时承担 L0 排序与 DA gate）。
- 下一步建议先做最小离线诊断脚本，抽取 `dcopf_s_line/s_volt/s_any/success` 与 AC truth 对齐分析，再做可校准的 A1 optimized DCOPF baseline。

## 1. DCOPF Call Path
主 benchmark 路径：
- `ac_ext/experiments/run_ml_surrogate_benchmark.py`
- `SuSController(case_name, config).run(...)`
- Level-0 或 DA 阶段内部调用 `eval_proxy(..., proxy_mode='dcopf')`
- `ac_ext/problem.py::eval_proxy()`
- `apply_state(case_name, state)` 生成 `DamagedCaseSpec` token
- `ac_ext/matlab_engine.py::run_dcopf(DamagedCaseSpec)`
- `run_dcopf_damaged(case_data, state)`
- MATLAB: `mp_apply_damage_state_minimal(case_data, state_json)`
- MATLAB: `mp_run_dcopf_minimal(mpc_damaged, ...)`
- MATLAB: `runopf(mpc, mpoption(...,'model','DC'))`
- MATLAB: `local_compute_scores -> s_line/s_volt/s_any`
- Python: `validate_scalar_payload()` 校验 `s_any=max(s_line,s_volt)`
- SuS Level-0 ranking / DA stage-1 gate / reverse proxy gate 使用 `s_any`。

补充：
- `ac_ext/matlab/mp_eval_damaged_case_minimal.m` 的 `mode` 仅含 `acpf/acopf/dcpf/fdxb`，`dcopf` 走独立 `run_dcopf_damaged()` 分支。

## 2. Damaged Case Construction
实现文件：`ac_ext/matlab/mp_apply_damage_state_minimal.m`。

状态字段到 MATPOWER case 的映射：
- `line_out`：`branch(line_out>0.5, BR_STATUS)=0`。
- `gen_scale`：逐机组处理。
- `gen_scale<=0`：`GEN_STATUS=0` 且 `PMAX=0`。
- `gen_scale>0`：`PMAX := PMAX * gen_scale`（下限截断到 0）。
- `bus_out`：保守规则。
- 将母线 `BUS_TYPE=4`（isolated）。
- 该母线 incident branches 全部 `BR_STATUS=0`。
- 该母线机组 `GEN_STATUS=0`、`PMAX=0`。
- `gen_derate_state`：仅在 Python 侧用于状态完整性校验/采样记录，不直接进入 MATLAB 变更逻辑。

在当前 SuS benchmark 的实际运行中：
- `SuSController._initial_states()` 强制 `bus_outage_prob=0.0`、`gen_derate_state_values=(1.0,)`、`gen_derate_state_probs=(1.0,)`。
- `_normalize_line_only_state()` 再次把 `bus_out` 置 0、`gen_scale` 置 1.0、`gen_derate_state` 置 0。
- 因此当前路径本质是 line-only damage，bus/gen 退化在该 benchmark 中未生效。

## 3. DCOPF Score Definition
DCOPF solver 与成功判定：
- `mp_run_dcopf_minimal.m` 调用 `runopf(..., model='DC')`。
- `success = logical(result.success)`。

分数定义：
- `s_line`：在线且 `RATE_A>0` 支路上，`max(loading - RATE_A)`。
- loading 优先用 `hypot(P,Q)`（若无 Q 列则退化为 `abs(P)`）。
- `s_volt`：`max(vmin-vm, vm-vmax)`（直接由结果 bus 矩阵 VM/VMAX/VMIN 计算）。
- `s_any = max(s_line, s_volt)`（同时被 Python `validate_scalar_payload` 强制校验）。

失败映射：
- 若 solver 返回 `success=false`：
- `ac_fail_as_violation=True` -> `s_line=s_volt=s_any=+inf`。
- `ac_fail_as_violation=False` -> `-inf`。
- 若 MATLAB 执行异常（wrapper crash/exception），Python 和 MATLAB wrapper 都回退到 `success=false, s_*=+inf` 失败载荷。

关于 DC 模型与电压项：
- DCOPF 没有 AC 电压/无功物理；`s_volt` 仍按 bus VM 边界公式计算，但该信号在 DC 模型下通常信息量有限，更多是“字段兼容”而非 AC 电压真实性能指标。

## 4. Current Benchmark Evidence
数据源：
- `ac_ext/experiments/out/hybrid_smoke_case118_N500_seed901.json`
- `ac_ext/experiments/out/hybrid_case118_N1000_seed901.json`

### N = 500
| arm | pf_hat | truth_calls | proxy_calls | acceptance_rate | l0_guard_passed | l0_truth_calls | l0_K_initial | l0_K_final | l0_rank_inversion_hits | reverse_proxy_rejects |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| truth_only | 0.0558 | 925 | 0 | 0.4000 | True | 500 | - | - | 0 | 0 |
| corrected_da_fdxb | 0.0609 | 675 | 1068 | 0.2329 | True | 500 | 200 | 500 | 42 | 9 |
| corrected_da_dcopf | 0.0588 | 619 | 1044 | 0.1929 | True | 500 | 200 | 500 | 29 | 7 |
| corrected_da_hybrid_ml_failure_l0_dcopf_da | 0.0588 | 619 | 1044 | 0.1929 | True | 500 | 200 | 500 | 23 | 7 |

### N = 1000
| arm | pf_hat | truth_calls | proxy_calls | acceptance_rate | l0_guard_passed | l0_truth_calls | l0_K_initial | l0_K_final | l0_rank_inversion_hits | reverse_proxy_rejects |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| truth_only | 0.06915 | 1850 | 0 | 0.4106 | True | 1000 | - | - | 0 | 0 |
| corrected_da_fdxb | 0.0678 | 1391 | 2190 | 0.2600 | False | 1000 | 200 | 1000 | 114 | 20 |
| corrected_da_dcopf | 0.06825 | 1269 | 2118 | 0.2247 | False | 1000 | 200 | 1000 | 85 | 10 |
| corrected_da_hybrid_ml_failure_l0_dcopf_da | 0.06825 | 1269 | 2118 | 0.2247 | False | 1000 | 200 | 1000 | 84 | 10 |

## 5. Interpretation: Where DCOPF Helps and Where It Fails
upper-level DA savings：
- 明显存在。相对 `truth_only`，`corrected_da_dcopf` 的 truth 调用从 925->619（N=500）和 1850->1269（N=1000）下降。
- 在当前配置下，节省来源是 DA stage-1 proxy gate 拦截 proposal，而不是 L0 预筛。

Level-0 prescreen failure：
- `corrected_da_dcopf` 两个规模都 `l0_truth_calls = N`。
- N=500: `K_final=500`（等于 N），即便 `l0_guard_passed=True` 也没有产生 truth 节省。
- N=1000: `l0_guard_passed=False` 且 `fallback_reason=rank_inversion_guard_exceeded`，直接全量 truth。

rank inversion issue：
- DCOPF 比 FDXB 好一些（29<42，85<114），但 inversion 仍高，guard 触发扩容/回退。

score-scale compatibility：
- 同一个 `s_any` 同时用于 L0 排序与 DA gate。
- 从结果看它对 DA gate 有用（truth_calls 降），但对 L0 top-K 排序稳定性不足（K 扩到 N 或 fallback）。

## 6. Candidate Optimization Directions
优先级排序（仅方案，不改代码）：

Option A: score recalibration
- 形式：`score = alpha*s_line + beta*s_volt + gamma*fail_indicator`。
- 用固定样本做 grid search / logistic calibration / isotonic calibration，分别优化 L0 排序质量和 DA gate 通过-拒绝区分。

Option B: DCOPF diagnostic feature export
- 导出并落盘：`dcopf_s_line, dcopf_s_volt, dcopf_s_any, dcopf_success`，再与 AC truth 联合分析。
- 为后续 C 路线（ML-calibrated DCOPF）提供最小可用训练/校准特征。

Option D: guard sensitivity
- 系统扫描 `K, tail_audit, allowed_inversions(可新增), expand_factor, max_expand_rounds, failure_recall_threshold`。
- 目标是避免 “K 快速扩到 N” 的退化行为。

Option C: optimized DC power-flow / DCOPF parameters
- 研究 line-flow scaling、bias correction、constraint margin、solver fail penalty 等工程参数。
- 先在离线数据上验证再进入在线 SuS。

Option E: compare ACPF as intermediate proxy
- 若可用，评估 ACPF 连续违约分数在 L0 排序上的稳定性，作为 DCOPF 的对照中间层。

## 7. Recommended Next Step
推荐先做：`analyze_dcopf_vs_acopf.py`（最小离线诊断脚本）。

理由：
- 不需要跑长 benchmark，直接复用已有样本/结果文件。
- 一次性回答 A/C/E 的关键问题：
- `dcopf_s_any` 与 AC truth 的排序一致性（top-K overlap、rank inversion curve、AUC）。
- `s_line/s_volt/success` 各自对 AC failure 的贡献。
- 为 A1（optimized DCOPF baseline）提供可执行的校准目标与 guard 参数建议。

建议脚本输出：
- 每个候选 score 定义在固定 K 下的 `top-K recall@truth-fail`、`rank inversion hits`、`expected l0_truth_calls`。
- DA 相关的阈值敏感性摘要，区分“适合 L0”与“适合 DA”的 score 配方。

## 8. Missing Information Before DCOPF Training
当前报告已明确实现链路、score 语义与 benchmark 症状，但仍不足以直接进入 optimized DCOPF 训练。正式训练前还缺：

1. DCOPF feature dataset
- 需要原因：当前结果文件主要是 arm-level聚合指标，缺少逐样本 `dcopf_s_line/s_volt/s_any/success` 与 ACOPF label 的对齐数据。
- 缺失风险：无法做可重复的离线优化与误差归因，只能凭 benchmark 末端指标盲调。

2. Explicit optimization target
- 需要原因：文献常用 dispatch-error，但本课题目标是 ACOPF-failure ranking 与 rare-event screening。
- 缺失风险：优化方向与最终目标不一致，可能提升 OPF 数值拟合却恶化 L0/DA 节省。

3. Parameterization plan
- 需要原因：需要先定义 A1.1/A1.2/A1.3 各自可调参数边界，避免训练对象漂移。
- 缺失风险：实验不可比、版本不可追踪，且容易误触 MATPOWER 核心修改。

4. Train/validation/test split
- 需要原因：必须隔离调参与最终证据，避免 seed 泄漏。
- 缺失风险：结论乐观偏置，无法支撑 A1 路线有效性主张。

5. Guard-aware validation protocol
- 需要原因：已知瓶颈是 guard 扩展到 `K=N`，只看 AUC 类指标不够。
- 缺失风险：离线指标好看但线上仍 fallback 全量 truth，truth-call saving 不提升。

## 9. Required DCOPF Feature Dataset
目标表：
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`

基线来源：
- `ac_ext/experiments/out/ml_training_data_case118.csv`

该扩展表必需字段：

Original damage state:
- `sample_id`
- `seed`
- `line_outage_prob`
- `line_out_json`
- `bus_out_json`
- `gen_derate_state_json`
- `gen_scale_json`

ACOPF label fields:
- `acopf_success`
- `acopf_s_line`
- `acopf_s_volt`
- `acopf_s_any`
- `acopf_fail_label`

DCOPF diagnostic fields:
- `dcopf_success`
- `dcopf_s_line`
- `dcopf_s_volt`
- `dcopf_s_any`
- `dcopf_fail_indicator`

Optional future fields:
- `fdxb_success`
- `fdxb_s_line`
- `fdxb_s_volt`
- `fdxb_s_any`
- `acpf_success`
- `acpf_s_line`
- `acpf_s_volt`
- `acpf_s_any`

说明：
- 该表是 A1 optimized DCOPF、C ML-calibrated DCOPF、以及未来 FDXB/ACPF calibration 的共同基础数据层。
- 该步骤不需要重跑 ACOPF；应复用已有 damage states + ACOPF labels，仅补跑 DCOPF proxy 字段。
- 若 DCOPF 字段计算依赖 MATLAB，仅先设计脚本与接口；本阶段不执行 MATLAB-heavy 任务。

## 10. Candidate Optimization Targets
### 10.1 Ranking / classification metrics
- AUROC for ACOPF failure
- AUPRC for ACOPF failure
- Top-K ACOPF-failure recall
- Top-K precision
- missed-failure count
- rank inversion hits

### 10.2 Guard-aware metrics
- `l0_K_final`
- `l0_truth_calls`
- guard pass/fail
- `rank_inversion_guard_exceeded` rate
- expected fallback probability

### 10.3 Final benchmark metrics
- `truth_calls`
- truth-call saving vs `truth_only`
- truth-call saving vs raw `dcopf`
- `pf_hat` relative error vs `truth_only`
- wall-clock time
- `reverse_proxy_rejects`
- `acceptance_rate`

目标转译原则：
- 不直接照搬文献中的 generator dispatch error loss。
- 采用 ACOPF-guided DCOPF optimization 思想，但把目标函数转译为 ACOPF-failure ranking / rare-event screening 损失与 truth-call 节省。

## 11. DCOPF Optimization Levels
### A1.1 Score-level optimized DCOPF
不改 MATPOWER，不改 damaged case，只做 score 后处理：

`score_opt = alpha * normalized(dcopf_s_line) + beta * normalized(dcopf_s_volt) + gamma * I(dcopf_fail) + delta`

或：

`score_opt = calibrated P(ACOPF failure | dcopf_s_line, dcopf_s_volt, dcopf_s_any, dcopf_success)`

说明：
- 实现最快，适合作为 MVP。
- 主要用于验证“raw DCOPF 输出是否可经后处理显著改善 L0 ranking”。

### A1.2 Wrapper-level optimized DCOPF
不改 MATPOWER 原包，在项目 wrapper 暴露可调参数：
- branch limit margin
- RATE_A safety factor
- line-flow scaling
- solver-failure penalty
- `s_line / s_volt` weighting
- optional branch-specific or global scaling factors

说明：
- 新增 `proxy_mode=\"dcopf_optimized\"`。
- 保留 raw `proxy_mode=\"dcopf\"` 作为对照。
- 这是当前阶段最合适的 PhD-level engineering 主线。

### A1.3 Formulation-level optimized DCOPF
更接近文献路线：
- coefficient scaling
- injection bias
- flow bias
- DC approximation parameter tuning
- possible `Bbus / Bf / PTDF`-like correction（若可访问）

说明：
- 方法学最接近 ACOPF-guided DCOPF optimization 文献。
- 工程复杂度最高。
- 不应直接修改外部 `matpower/` 包；应在 project-local wrapper / custom MATLAB function 内实现。

## 12. Data Split and Leakage Control
建议数据划分：

Training:
- seeds `7, 42, 100, 200`

Validation:
- seed `300`

Unseen benchmark:
- seeds `901, 902, 903`

约束：
- 现有 30,000 ACOPF training data 可用于 train/validation。
- unseen seeds 不参与参数优化与模型选择。
- 若使用 seed 901 做 smoke，只能标记为 smoke，不得作为最终证据。
- 禁止“用 901 调参后再用 901 证明提升”。

## 13. Guard-aware Validation Protocol
当前已观测到的退化模式：
- `K_initial = 200`
- `tail_audit = 50`
- `expand_factor = 1.5`
- `max_expand_rounds = 3`
- `K_final = N`
- `l0_truth_calls = N`

因此候选 score 不能只看 AUPRC/AUROC，必须进行离线 guard simulation。

每个候选 score 的 simulation 输入：
- candidate score
- ACOPF fail label or ACOPF truth score
- `K_initial`
- `tail_audit`
- `expand_factor`
- `max_expand_rounds`
- optional `allowed_inversions`
- optional `failure_recall_threshold`

simulation 输出：
- simulated `K_final`
- simulated `l0_truth_calls`
- inversion hits
- failure recall inside final K
- whether fallback would trigger

用途：
- 过滤掉“分类指标好看但 guard 仍扩到 `N`”的无效 score。

## 14. Minimal Script Roadmap
本节仅定义最小脚本，不在本轮实现。

### 14.1 collect_dcopf_feature_data.py
目的：
- 读取 `ml_training_data_case118.csv`，重建 damage state，运行 `eval_proxy(..., proxy_mode=\"dcopf\")`，输出 `ml_training_data_with_dcopf_case118.csv`。

要求：
- preserve ACOPF labels
- add `dcopf_s_line/s_volt/s_any/success`
- no ACOPF re-evaluation
- support resume / skip existing rows
- flush regularly

### 14.2 analyze_dcopf_vs_acopf.py
目的：
- 比较 raw DCOPF score 与 ACOPF failure label。

输出：
- AUROC / AUPRC
- Top-K recall / precision
- rank inversion hits
- per-`line_outage_prob` cohort breakdown
- `s_line` vs `s_volt` vs `s_any` contribution
- guard simulation summary

### 14.3 optimize_dcopf_score.py
目的：
- 实现 A1.1 score-level optimized DCOPF。

候选方法：
- grid search over `alpha/beta/gamma`
- logistic regression
- isotonic calibration
- simple XGBoost/LightGBM on DCOPF-only features as diagnostic (not final ML-calibrated model)

输出：
- best score formula
- validation metrics
- comparison: `raw_dcopf` vs `optimized_dcopf_score`

### 14.4 plan_dcopf_optimized_proxy_mode.md
目的：
- 设计 `proxy_mode=\"dcopf_optimized\"` 的 wrapper-level 实现方案。

## 15. Decision Rules Before Implementation
1. 若 optimized score 显著降低 rank inversion 且 guard simulation 显示 `K_final < N`：
- 进入 `proxy_mode=\"dcopf_optimized\"` 实现。

2. 若 optimized score 仅提升 AUPRC，但 guard 仍 `K=N`：
- 优先修 guard 策略（如 `allowed_inversions` / `failure_recall_threshold` 等）后再推进。

3. 若 DCOPF features 对 ACOPF failure 几乎无预测力：
- 暂停 DCOPF optimization，转向 ACPF 或 FDXB calibration。

4. 若 raw DCOPF score 已接近最优但 benchmark 仍差：
- 判定主问题在 guard，而非 DCOPF score 本体。

5. 若 A1 optimized DCOPF 确认有效：
- 再进入 C（ML-calibrated DCOPF）阶段。

## 16. Current Recommended Next Step
当前最优先步骤不是直接实现 `dcopf_optimized`，而是完成从 diagnostic 到 training framework 的桥梁：

1. create `collect_dcopf_feature_data.py`
2. create `analyze_dcopf_vs_acopf.py`
3. use outputs to define A1.1 score-level optimized DCOPF
4. only then design `proxy_mode=\"dcopf_optimized\"`

理由：
- 先把逐样本证据和 guard-aware 离线评价体系建起来，才能避免在 benchmark 末端盲调参数。

## 17. Second-Opinion Audit: RATE_A=0 and DCOPF Score Degeneration
### 17.1 Confirmed facts
- `matpower/data/case118.m` 的 `mpc.branch` 中 `rateA` 列（第 6 列）在 186 条支路上全为 0。
- `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`（30000 行）中：
- `dcopf_s_line` 有限值数为 0，`inf` 为 30000。
- `dcopf_s_volt` 有限值数为 26230，且有限值唯一（`-0.06000000000000005`）；`inf` 为 3770。
- `dcopf_s_any` 与 `dcopf_s_volt` 同分布（有限值唯一 + 失败时 `inf`）。
- 该分布与 `dcopf_success`/`dcopf_fail_indicator` 高度一致，连续排序信息几乎退化。

### 17.2 Source-code evidence
- `mp_run_dcopf_minimal.m` 中：
- `eligible = (status == 1) & isfinite(rate) & (rate > 0)`。
- 若 `any(eligible)` 为假，则 `s_line = -inf`。
- `s_any = max(s_line, s_volt)`。
- 因此在 `RATE_A` 全 0 条件下，successful case 的 `s_line=-inf` 是预期行为，不是异常。
- Python 侧 `events.validate_scalar_payload()` 只要求字段存在且 `s_any==max(s_line,s_volt)`，当前 payload 完全满足一致性约束。
- `problem.eval_proxy(..., proxy_mode='dcopf')` 对该 payload 直接通过校验并返回，无内部矛盾。
- `collect_dcopf_feature_data.py` 将 `eval_proxy(..., 'dcopf')` 的返回值原样写入 `dcopf_s_line/s_volt/s_any/success`，字段映射逻辑正确。
- `ac_fail_as_violation=True` 时，solver fail 映射 `s_*=+inf`（MATLAB wrapper 与 Python fallback 一致），当前 CSV 与该语义一致。

### 17.3 Why current dcopf_s_line is not usable for continuous ranking
- 当前 `s_line` 是“相对 `RATE_A` 的超限裕度”。
- `RATE_A` 全 0 导致所有支路都不进入 `eligible` 集合。
- 结果是 successful 样本统一 `s_line=-inf`，failed 样本统一 `s_line=+inf`。
- 这不是数值噪声问题，而是 score 定义在该 case 数据语义下失去连续量纲。

### 17.4 Why current dcopf_s_any behaves like a solver-success classifier
- 当 successful 时：`s_line=-inf`，`s_any=max(-inf,s_volt)=s_volt`。
- 而当前 `s_volt` 在 successful 样本上几乎常数 `-0.06`。
- 当 failed 时：`s_any=+inf`。
- 因此 `s_any` 在 case118 上近似二值化：`-0.06`（成功）/`+inf`（失败），本质更像“solver success classifier”，不是可细粒度排序分数。

### 17.5 Required next data artifact: branch-level DCOPF PF matrix
- 若目标是 A1 optimized DCOPF 的连续排序优化，当前 `dcopf_s_*` 字段信息不足。
- 需要新增逐样本流量特征层，至少包含每条支路的 `PF/PT`（可选 `QF/QT`）或其压缩统计（如 `abs(PF)` 分位数、top-k、max、加权和）。
- 推荐产物为“样本级元数据 CSV + 支路流矩阵 NPZ/Parquet”双文件结构，以避免 CSV 存储膨胀。
- 该产物可直接支持：
- A1.1 score-level calibration（构造 pseudo-limit score）。
- A1.2 wrapper-level 参数扫描（flow scaling / margin / penalty）。
- C 路线（ML-calibrated DCOPF）中的轻量特征建模。

对已生成 `dcopf_flow_features_case118.npz` 的后续审计还确认了一个关键约束：
- `dcopf_success=False` 的 3770 个样本中，存储的 `PF/PT` 全部为 0。
- 这说明失败样本没有可用的连续 DC 流量解，或者 wrapper 在失败路径上将流量字段置 0。
- 无论具体来源是什么，这些 0 都不能被解释为“低风险”或“低应力”。

因此任何后续 flow-based score 都必须先看 solver 成败，再决定是否读取 `PF/PT`：

```python
if dcopf_success == False:
    flow_score = float("inf")
    fail_proxy = 1.0
else:
    flow_score = max(abs(PF_active) / pseudo_limit - 1.0)
```

否则会把最危险的一类样本错误排到排序末端，直接破坏 L0 排序和 guard simulation。

更具体地说，离线分析脚本应强制遵守以下结构：

```python
success = d["dcopf_success"].astype(bool)
PF = d["PF"]
PT = d["PT"]
branch_status = d["branch_status"].astype(bool)

score = np.full(PF.shape[0], np.inf, dtype=float)

# only compute continuous flow score for successful DCOPF solves
abs_flow = np.maximum(np.abs(PF), np.abs(PT))

# outaged branches should not contribute
abs_flow = np.where(branch_status, abs_flow, np.nan)

ratio = abs_flow / pseudo_limit[None, :]
flow_score_success = np.nanmax(ratio - 1.0, axis=1)

score[success] = flow_score_success[success]

# failed samples remain +inf
assert np.all(np.isinf(score[~success]))
```

同样，若 pseudo-limit 用 training percentile 构造，则必须只用：
- `train split only`
- `dcopf_success == True`
- `branch_status == 1`

例如：

```python
train_success = train_mask & success
flows_train = abs_flow[train_success]
limit = np.nanpercentile(flows_train, q, axis=0)
```

原因是 failed 样本的零流量若混入 percentile 估计，会把 pseudo-limit 人为拉低，制造假 signal。

还需要区分 ranking 用法和 ML feature 用法：
- ranking / guard simulation：`failed -> +inf`
- ML feature table：不要直接喂 `+inf` 给 XGBoost / LightGBM

推荐的 ML-side 转换：

```python
cap = np.nanpercentile(
    flow_score_success[np.isfinite(flow_score_success)],
    99.5,
)
model_feature_score = np.where(success, flow_score_success, cap + 1.0)
model_feature_failed = (~success).astype(int)
```

即：
- ranking 阶段保留“failed = maximal risk”语义；
- ML 特征阶段把它转成“高但有限的分数 + 明确失败标志”。

### 17.6 Candidate pseudo-limit strategies
1. Base-case PF margin
- 定义：`limit_i = max(abs(PF_base_i) * margin, epsilon)`。
- 泄漏风险：低（只依赖基准网络，不用标签）。
- split 兼容：高（train/val/test 共用同一 deterministic limit）。
- online 兼容：高（`proxy_mode=\"dcopf_optimized\"` 可直接内置）。
- 文献贴近度：中（属于 DC 参数校准但未显式 AC 引导）。

2. Training-set percentile
- 定义：`limit_i = percentile_train(abs(PF_i), q)`。
- 泄漏风险：中（若误用全数据会泄漏；必须只用 train seeds）。
- split 兼容：中到高（流程可控时可用）。
- online 兼容：高（离线固化后在线只读参数）。
- 文献贴近度：中（数据驱动校准，弱 AC 引导）。

3. Hybrid (recommended)
- 定义：`limit_i = max(abs(PF_base_i)*margin, percentile_train(abs(PF_i), q), epsilon)`。
- 泄漏风险：中（与 2 相同，需严格 train-only 估计）。
- split 兼容：高（参数冻结后可跨 seed 验证）。
- online 兼容：高。
- 文献贴近度：中到高（兼具物理基准与数据校准）。

4. Branch-independent global limit
- 定义：全支路共享一个 `limit_global`。
- 泄漏风险：低。
- split 兼容：高。
- online 兼容：高。
- 文献贴近度：低（过度简化，支路异质性丢失）。

5. ACOPF-guided branchwise calibration
- 定义：用 train seeds 的 AC failure 目标，直接优化每支路缩放系数或分组缩放系数。
- 泄漏风险：中到高（必须严格 train-only，且需正则化）。
- split 兼容：中（参数维度大时易过拟合）。
- online 兼容：中到高（参数冻结后可用）。
- 文献贴近度：高（最接近 ACOPF-guided DCOPF optimization）。

### 17.7 Recommended next step
- 审计结论：`RATE_A=0` 诊断成立；当前 `dcopf_s_any` 在 case118 上基本退化为成功/失败二值信号。
- 新增结论：flow-level artifact 虽然已足够支持离线 score 设计，但失败样本的 `PF/PT=0` 进一步说明连续 score 不能脱离 `dcopf_success` 单独使用。
- 下一最小可执行工件应是“流量特征数据采集”，优先级排序：
- B > C > A > D > E
- B: `collect_dcopf_flow_feature_data.py`（导出 branch PF/PT 矩阵与样本索引）。
- C: `analyze_dcopf_flow_scores.py`（在离线上评估 pseudo-limit score、Top-K recall、guard simulation）。
- A: 扩展 `mp_run_dcopf_minimal.m` 输出少量 raw flow 统计（可做，但灵活性不如独立采集脚本）。
- D: 直接改当前 score 为 pseudo RATE_A（应在 B/C 证据后做，不宜先改）。
- E: 继续只用现有 `ml_training_data_with_dcopf_case118.csv`（不建议，信息不足以做连续 ranking 优化）。
- guard 关系：当前 L0 guard 扩展到 `K=N` 与“分数缺少连续排序能力”高度一致。建议先构建连续 flow-based score，再做 guard 灵敏度调参与规则修正。

## 18. Independent Audit: Score/Guard Objective Mismatch
### 18.1 Current legacy guard behavior
- 当前 Level-0 guard 实现在 `SuSController._evaluate_states_level0_prescreen()`。
- proxy 排序使用 `eval_proxy(...).get("s_any")`，truth audit 使用 `eval_truth(...).get("s_any")`。
- truth payload 通过 `_timed_truth_payload()` 返回给 controller；controller 在 guard 中缓存 `truth_payloads[idx]`，并把 `truth_scores[idx] = float(payload["s_any"])`。
- guard 的核心判定是：
- 在当前 top-K truth 中按 `s_any` 降序取第 `n_seed` 个样本，得到 `gamma_candidate`。
- 在 tail audit 中统计 `truth s_any >= gamma_candidate` 的样本数，记为 `rank_inversion_hits`。
- 若该计数非 0，则扩 K；超过最大扩展轮数则 fallback 到 full truth。
- 这说明当前 guard 明确保护的是 “ACOPF `s_any` 排序阈值”，不是 “ACOPF failure membership”。
- 当前 controller 在 guard 逻辑中会顺手统计 `tail_audit_truth_fail_count` / `tail_audit_hit_fail_count`，但这些只是诊断计数，不参与 pass/fail 决策。

### 18.2 Evidence from lop=0.008 validation
- 离线脚本 `analyze_dcopf_flow_scores.py` 在 `seed=300, line_outage_prob=0.008, N=1000, sus_p0=0.15, K_initial=200, tail_audit=50` 上给出：
- raw DCOPF success/fail score：`n_fail=84, AUROC=1.0, AUPRC=1.0, top100_recall=1.0, top200_recall=1.0`。
- 同一 slice 上，legacy guard：`rank_inversion_hits=62, K_final=1000, l0_truth_calls=1000, fallback=True`。
- 同一 slice 上，failure-label guard：`rank_inversion_hits=0, K_final=200, l0_truth_calls=250, fallback=False, failure_recall_inside_final_k=1.0`。
- `hybrid_case118_N1000_seed901.json` 的真实 benchmark 结果也与此一致：`corrected_da_dcopf` 的 `l0_rank_inversion_hits=85, l0_prescreen_K_final=1000, l0_guard_passed=False`。
- 对比 `all_lop` 结果可见，raw success/fail 在 `line_outage_prob=0.02` 时 legacy guard 已可自然通过（`legacy_rank_inversion_hits=0, K_final=200`），说明问题具有 slice dependence，而不是 “raw DCOPF 在所有 slice 上都完全无效”。

### 18.3 Why raw DCOPF success/fail is sufficient for ACOPF failure membership on this slice
- 在 `lop=0.008` 验证 slice 上，raw DCOPF 的 `success=False -> s_any=+inf` 已经把全部 ACOPF failure 提前到排序顶部。
- 证据是 `top100_recall=1.0` 且 `top200_recall=1.0`；failure-label guard 也显示 `failure_recall_inside_final_k=1.0` 且无需扩 K。
- 这说明在该 slice 上，raw DCOPF 的主要有效信息并不是连续 stress ranking，而是 hard fail indicator。
- 因此，若 Level-0 的任务目标是 “把所有 ACOPF failure 保留在 top-K 内”，则 raw success/fail 已经足够满足该目标。

### 18.4 Why legacy guard still expands K to N
- 当前 legacy guard 审计的是 ACOPF `s_any` 排序，而不是 ACOPF failure membership。
- `events.combine_scores()` 锁定了 `s_any = max(s_line, s_volt)`；因此 controller 会把所有 finite `s_any` 差异都当成有序阈值上的“真值差异”。
- 在当前 case118 / ACOPF 语义下，很多 solved 样本的 finite `s_any` 只是接近 0 的微小数值差异，这些差异并不等价于 rare-event failure severity。
- 结果是：即使所有真正 failure 都已经在 top-K 中，只要 tail audit 里存在 `truth s_any >= gamma_candidate` 的 solved 样本，legacy guard 仍会记作 rank inversion 并扩 K。
- 因而我同意以下解释：
- raw DCOPF fail indicator 在该验证 slice 上已经是强 ACOPF failure detector。
- 当前 `K=N` 的直接原因是 legacy guard 保护 ACOPF `s_any` 排名，而不是保护 ACOPF failure 集合。
- 仅继续优化 pseudo-limit flow score，不足以保证 legacy `K=N` 问题消失；除非同时改变 guard 目标，否则 legacy guard 仍可能对近零 finite truth score 的噪声排序过度敏感。

### 18.5 Failure-label guard proposal
- 最小可行方案是新增 `level0_guard_mode`：
- `legacy_truth_score`：保持当前行为，默认值，用于复现。
- `failure_label`：仅在 tail audit 中审计 “是否漏掉了 ACOPF failure”。
- 推荐的 failure label 定义：

```python
truth_failed = (not bool(payload.get("success", False))) or math.isinf(float(payload.get("s_any", float("-inf"))))
```

- 推荐的新 tail audit 规则：

```python
hits_this_round = sum(1 for idx in audit_indices if truth_failed[idx])
```

- 也就是说，`failure_label` guard 不再构造 `gamma_candidate`，而是只问：
- top-K 外的 tail audit 中是否仍有 ACOPF failure？
- 若有，则扩 K。
- 若没有，则 guard 通过。
- 这与离线脚本中的 `guard_simulation_failure_label()` 一致，也与 rare-event failure-screening 任务目标一致。

### 18.6 Risks and controls
- 风险 1：failure-label guard 只保护 failure membership，不保护 near-failure severity 排序。
- 影响：可能放过一些 “非 fail 但接近 fail” 的样本，导致 top-K 的连续真值代表性下降。
- 控制：先将其限定在 Level-0 prescreen，不改变 DA；并额外记录 `failure_recall_inside_final_k`、`tail_audit_truth_fail_count`、`tail_audit_hit_fail_count`。
- 风险 2：failure-label guard 若直接替代 legacy guard，可能改变 Subset Simulation 对连续 truth threshold 的近似方式。
- 影响：若 naively 用于所有 truth/proxy 组合，可能影响 `pf_hat` 稳定性与理论解释。
- 控制：将该模式设计为 opt-in，仅用于 A1 / DCOPF prescreen 诊断；benchmark 中始终与 legacy mode 并列比较 `pf_hat`、truth_calls、K_final。
- 风险 3：binary failure 目标可能对 ACOPF numerical noise 过于鲁棒，但也可能忽略真正有用的 continuous severity signal。
- 控制：可后续增加 secondary buffer，例如：
- `truth_failed or truth_s_any > -epsilon`
- 或在 failure guard 通过后，再附加一个轻量 severity audit。
- 风险 4：若后续 proxy 改成 `l0_score` / `da_score` 分离，controller 仍需确保 Level-0 使用的是适合 failure screening 的 score，而 DA 保持更保守的 gate。

### 18.7 Recommended minimal implementation and benchmark
- 最小 controller 变更建议：
- 在 config / controller 中新增 `level0_guard_mode`，默认 `"legacy_truth_score"`。
- 在 `SuSController._default_l0_meta()`、`self.stats`、`run_ml_surrogate_benchmark.py` 输出行中新增：
- `l0_guard_mode`
- `l0_failure_recall_inside_final_k`
- 可选新增：
- `l0_tail_audit_truth_fail_count`
- `l0_tail_audit_hit_fail_count`
- 在 `_evaluate_states_level0_prescreen()` 中保留当前 legacy 分支不变；仅新增一个 `if level0_guard_mode == "failure_label":` 的 tail audit 分支。
- 不修改 DA stage。
- 不修改 raw `proxy_mode="dcopf"`。
- 不修改 ACOPF / MATPOWER payload。

- 最小 benchmark 建议：
1. `N=500` smoke：
- `truth_only`
- `corrected_da_dcopf` + `legacy_truth_score`
- `corrected_da_dcopf` + `failure_label`
2. `N=1000, seed=901`：
- 相同三组。

- 必看指标：
- `pf_hat`
- `truth_calls`
- `l0_truth_calls`
- `l0_prescreen_K_final`
- `l0_failure_recall_inside_final_k`
- `l0_rank_inversion_hits`
- `l0_fallback_reason`
- `acceptance_rate`
- `reverse_proxy_rejects`

- 优先级建议：
- A. 先实现 `failure_label` guard 并 benchmark raw DCOPF
- B. 再继续优化 pseudo-limit continuous score
- C. 不建议在 guard 语义未分离前把主要精力放在继续调 score

- 具体排序：
1. `A`
2. `C`
3. `B`
4. `D`（其他）

- 理由：
- 你们已经有明确证据表明在关键 slice 上 raw success/fail 已足够抓住 ACOPF failure，而 legacy guard 目标本身与 rare-event failure-screening 任务不一致。
- 在这个前提下，先验证 failure-label guard 能否在真实 benchmark 中把 `K` 从 `N` 拉回到接近 `200`，是当前最小、最有信息量的实验。
- 之后再看 pseudo-limit continuous score 是否能在 failure 已覆盖的前提下进一步改善 `pf_hat` 稳定性、near-failure 覆盖或更高难度 slice 的表现。

## 19. Implementation: Failure-label Level-0 Guard
- 已实现的最小设计应保持以下边界：
- `legacy_truth_score` 仍为默认值，保证现有 benchmark 在不显式传参时保持旧逻辑。
- `failure_label` 为 opt-in，只改变 Level-0 tail audit 判定。
- raw `proxy_mode="dcopf"` 不变。
- DA stage 不变。
- MATLAB / truth solver / proxy payload 不变。

### 19.1 Guard modes
- `legacy_truth_score`
- tail audit 命中条件：`truth_s_any >= gamma_candidate`
- 保护对象：ACOPF scalar truth ranking

- `failure_label`
- tail audit 命中条件：`truth_failed == True`
- 推荐定义：

```python
truth_failed = (not bool(truth_payload.get("success", False))) or math.isinf(
    float(truth_payload.get("s_any", float("-inf")))
)
```

- 保护对象：ACOPF failure membership

### 19.2 Metadata requirements
- benchmark 输出应稳定包含（CSV/JSON 不因 arm 不同而缺列）：
- `l0_guard_active`
- `l0_guard_mode`
- `l0_tail_audit_count`
- `l0_tail_audit_failure_hits`
- `l0_failure_recall_inside_final_k`
- `l0_failure_recall_inside_final_k_observed`
- `l0_failure_label_rank_inversion_hits`
- `l0_failure_label_guard_passed`
- `l0_failure_label_fallback_reason`

- 语义约定：
- 当 `l0_prescreen_enabled=False`（例如 `truth_only`）时：
- `l0_guard_mode = "not_applicable"`
- `l0_guard_active = False`
- `l0_fallback_reason = "not_applicable"`
- `l0_failure_*` 字段统一为 `"not_applicable"`（或统一空值，但必须一致）

- recall 字段区分：
- `l0_failure_recall_inside_final_k`：仅当 controller 在 L0 阶段已得到全量 truth failure 标签时才输出全局 recall，否则输出 `not_available`。
- `l0_failure_recall_inside_final_k_observed`：基于“已评估 truth 子集”的 observed recall，可在非全量 truth 情况下稳定输出。

- 兼容性要求：
- 旧字段 `l0_guard_passed` / `l0_fallback_reason` / `l0_rank_inversion_hits` 继续保留，并代表当前 active guard mode 的结果。

### 19.3 Experimental intent
- 该实现的第一目标不是修改 physics proxy，而是验证：
- 在 raw DCOPF 已能覆盖 ACOPF failure membership 的 slice 上，单独更换 guard objective 是否就足以把 `K_final` 从 `N` 拉回到接近 `K_initial`。

- 如果答案是肯定的，则说明：
- 当前瓶颈首先是 score/guard objective mismatch；
- continuous pseudo-limit score 的下一阶段优化应围绕更难 slice、near-failure 排序和 `pf_hat` 稳定性展开，而不是继续为 legacy guard 的近零 truth ranking 噪声买单。

## 20. Guard Freeze Benchmark Plan
- clean arms:
- `truth_only`
- `corrected_da_dcopf`

- guard modes:
- `legacy_truth_score`
- `failure_label`

- fixed benchmark slice:
- `case118`
- `N=1000`
- `line_outage_prob=0.008`
- `seeds=901, 902, 903`
- `sus_p0=0.15`

- purpose:
- 在进入 trained DCOPF score / parameter optimization 之前，先把 A1-Guard 的 controller-side收益做成干净、可复现、最小化 arms 的 freeze benchmark。
- 这个 freeze 只比较 guard objective，不重新讨论 FDXB、ML surrogate、hybrid arm，也不引入 pseudo-limit score。

- interpretation boundary:
- `failure_label` guard 的作用是 evaluation-objective alignment：它把 Level-0 的保护目标从 “ACOPF scalar truth ranking” 改成 “ACOPF failure membership”。
- 这不是最终的 DCOPF parameter training，也不是 `dcopf_optimized` 的终态设计。

- required outputs:
- `final_guard_legacy_case118_N1000_lop0008_seeds901_903.csv/.json`
- `final_guard_failure_label_case118_N1000_lop0008_seeds901_903.csv/.json`
- 对应 `nohup` 日志各一份

- after freeze:
- 若 freeze 结果确认 `failure_label` 在多 seed 上稳定降低 `truth_calls` 且保持 `pf_hat`，下一步转向 ACOPF-guided DCOPF score-parameter training。
- 该训练阶段应把重点放在连续 `l0_score` / `flow_score` 设计，而不是继续混合 score/guard 两类问题。

## 21. A1-Guard Freeze Result
- clean arms:
- `truth_only`
- `corrected_da_dcopf`

- benchmark slice:
- `case118`
- `N=1000`
- `line_outage_prob=0.008`
- `seeds=901, 902, 903`

- corrected `corrected_da_dcopf` summary:
- `legacy_truth_score` mean `pf_hat = 0.07945`
- `failure_label` mean `pf_hat = 0.07945`
- per-seed `pf_hat` values are unchanged between the two guard modes: `[0.06825, 0.08085, 0.08925]`

- truth-call effect:
- mean `truth_calls` drops from `1320` to `577`
- absolute mean saving = `743`
- relative mean saving vs legacy = `56.29%`

- Level-0 prescreen effect:
- mean `l0_truth_calls` drops from `1000` to `250`
- mean `K_final` drops from `1000` to `200`
- mean `l0_tail_audit_failure_hits` remains `0`

- interpretation:
- the result is a controller-objective alignment win, not a DCOPF physics-model change
- only the Level-0 guard objective changed
- raw DCOPF proxy stayed fixed
- DA stayed fixed
- ACOPF truth stayed fixed

- practical conclusion:
- A1-Guard successfully removes the forced `K=N` behavior on this benchmark slice without changing the final rare-event estimate for `corrected_da_dcopf`
- this freeze establishes a clean baseline for A2 score-parameter training

## 22. How A1-Guard Was Modified

Before:
- legacy guard protected the ACOPF `s_any` rank threshold
- tail audit hit condition:

```text
truth_s_any >= gamma_candidate
```

- consequence:
- finite ACOPF `s_any` ranking noise could trigger expansion even when all ACOPF failures were already inside top-K

After:
- failure-label guard protects ACOPF failure membership
- tail audit hit condition:

```text
truth_failed = (not success) or isinf(s_any)
```

- consequence:
- the guard expands only when the audited tail still contains ACOPF failure cases that were missed by the current top-K

Scope boundaries:
- raw `dcopf` unchanged
- DA unchanged
- ACOPF truth unchanged
- legacy guard remains the default
- `failure_label` is opt-in
- configuration field: `level0_guard_mode`
- supported modes:
- `legacy_truth_score`
- `failure_label`
- `truth_only` runs use `l0_guard_mode = not_applicable`

Net effect:
- A1 changed controller semantics, not solver semantics
- that separation is important because A2 should now focus on DCOPF-derived score training rather than continuing to patch controller-objective mismatch
