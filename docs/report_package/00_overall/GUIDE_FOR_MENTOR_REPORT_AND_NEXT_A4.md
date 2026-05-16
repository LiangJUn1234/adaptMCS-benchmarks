# Guide for Mentor Report and Next A4

## 1. 汇报目标
- 不把 A1 夸大为最终 optimized DCOPF。
- 强调 A1/A2/DA/certificate audit 已完成。
- 明确 A4 是下一阶段且为何必要。

## 2. 建议汇报结构（10 sections）
1. Problem and goal
2. Baseline issue
3. A1 guard objective mismatch
4. A1 result table
5. A2 score tuning saturation
6. DA trace result
7. Certificate audit result
8. Literature positioning
9. A4 next plan
10. Questions for mentor

## 3. 每部分建议引用文件
- A1 result:
  - `report/01_a1_guard/final_guard_summary_case118_lop0008_seeds901_903.md`
  - `report/01_a1_guard/final_guard_summary_case118_lop0008_seeds901_903.csv`
- A2 result:
  - `report/02_a2_score_tuning/dcopf_score_training_report_case118_v001.md`
  - `report/02_a2_score_tuning/a2_2_offline_comparison_case118_v001.md`
- DA result:
  - `report/03_da_trace/da_trace_analysis_case118_N1000_seed901_v001.md`
- Certificate:
  - `report/04_certificate_audit/dcopf_failure_certificate_audit_case118_v001.md`
- A4 next:
  - `report/05_a4_prep/A4_ACOPF_GUIDED_DCOPF_FORMULATION_PREP_PLAN.md`
  - `report/00_overall/OVERALL_SUMMARY_PART3_A4_NEXT_PLAN.md`

## 4. 必放表格
- A1 legacy vs failure_label 对比表
- A2 saturation 表（raw vs trained physics）
- DA trace proposal-level summary 表
- certificate audit 关键概率与风险表
- A4 branch decision table

## 5. 哪些话不能说
- 不要说 “DCOPF failure equals ACOPF failure”。
- 不要说 “A4 已完成”。
- 不要把文献指标与本项目指标混为同一指标。
- 不要说 zero risk / zero false certificate。
- 不要说 DA 已优化完成。

## 6. 建议说法
- “A1 corrected an objective mismatch in Level-0 screening.”
- “A2 simple score tuning saturated under the aligned objective.”
- “DA trace shows remaining truth calls are confirmation calls for DCOPF-failed proposals.”
- “Certificate audit shows high precision but nonzero false-certificate risk.”
- “A4 will move toward ACOPF-guided DCOPF parameter optimization with screening loss.”

## 7. A4 制作路线
- A4.0: certificate-aware design
- A4.1: regime gating
- A4.2: shortcut candidate offline test
- A4.3: grouped-parameter finite-difference smoke
- A4.4: online test if safe

## 8. 给导师的问题
1. Should certificate route be pursued before formulation-level parameterization?
2. What false-certificate tolerance is acceptable?
3. Should we test another MATPOWER case before A4?
4. Should we prioritize finite-difference grouped parameters or DA-side shortcut?
5. Is this better framed as contingency screening, rare-event estimation, or DCOPF parameter optimization?
