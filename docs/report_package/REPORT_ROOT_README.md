# Power-Rare-Events Report Package

当前状态：项目已完成 A1-Guard freeze、A2 simple score tuning closure、DA trace 诊断与 certificate audit，正准备进入 A4。

一段摘要：
A1 将 Level-0 guard 从 ACOPF s_any 排名保护改为 ACOPF failure membership 保护，在不改变 pf_hat 的前提下显著降低 truth calls。A2 离线 score 调优显示 simple scalar family 已接近饱和。DA trace 表明剩余 DA truth calls 主要用于确认 DCOPF-failed proposals。certificate audit 给出高精度但非零错误率，因此 A4 应走 certificate-aware 与 parameterization 双分支路线。

## Read First
1. `report/00_overall/OVERALL_SUMMARY_README.md`
2. `report/00_overall/GUIDE_FOR_MENTOR_REPORT_AND_NEXT_A4.md`
3. `report/06_mentor_update/`
4. `report/01_a1_guard/`
5. `report/03_da_trace/`
6. `report/04_certificate_audit/`
7. `report/05_a4_prep/`

## Directory Map
- `00_overall/`: 总结、manifest、汇报指南
- `01_a1_guard/`: A1 冻结结果
- `02_a2_score_tuning/`: A2 离线调优与比较
- `03_da_trace/`: DA trace 诊断
- `04_certificate_audit/`: 证书审计
- `05_a4_prep/`: A4 准备计划
- `06_mentor_update/`: 导师汇报材料
- `07_cleanup_and_inventory/`: 清理与库存
- `99_raw_copies/`: 可选原始副本

## Warning
源文件仍在 `adaptMCS-benchmarks`；`report/` 包含副本与汇总，不替代源目录。
