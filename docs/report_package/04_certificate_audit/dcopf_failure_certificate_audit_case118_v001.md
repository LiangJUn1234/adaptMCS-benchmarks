# DCOPF Failure Certificate Audit (case118 v001)

## 1. Purpose

Audit whether `DCOPF failed` empirically implies `ACOPF failed` on existing case118 data.

## 2. Data Sources

- CSV: `ac_ext/experiments/out/ml_training_data_with_dcopf_case118.csv`
- NPZ: `ac_ext/experiments/out/dcopf_flow_features_case118.npz`
- rows: `30000`

## 3. Overall Certificate Result

- `dcopf_failed_count`: `3770`
- `acopf_failed_count`: `3790`
- `true_certificate_count`: `3763`
- `false_certificate_count`: `7`
- `P(ACOPF fail | DCOPF fail)`: `0.998143`
- Wilson 95% CI: `[0.996172, 0.999100]`
- `false_certificate_rate`: `0.001857`
- `missed_failure_rate`: `0.007124`

## 4. By-lop Table

| lop | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | false_rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.005000 | 5000 | 245 | 246 | 1 | 0.995918 | 0.004082 |
| 0.008000 | 5000 | 393 | 395 | 1 | 0.997455 | 0.002545 |
| 0.011000 | 5000 | 548 | 550 | 1 | 0.998175 | 0.001825 |
| 0.014000 | 5000 | 714 | 717 | 2 | 0.997199 | 0.002801 |
| 0.017000 | 5000 | 865 | 872 | 0 | 1.000000 | 0.000000 |
| 0.020000 | 5000 | 1005 | 1010 | 2 | 0.998010 | 0.001990 |

## 5. By-seed Table

| seed | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | false_rate |
|---:|---:|---:|---:|---:|---:|---:|
| 7 | 6000 | 782 | 794 | 4 | 0.994885 | 0.005115 |
| 42 | 6000 | 807 | 807 | 0 | 1.000000 | 0.000000 |
| 100 | 6000 | 719 | 728 | 0 | 1.000000 | 0.000000 |
| 200 | 6000 | 735 | 734 | 3 | 0.995918 | 0.004082 |
| 300 | 6000 | 727 | 727 | 0 | 1.000000 | 0.000000 |

## 6. By seed x lop Table

| seed,lop | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | false_rate |
|---|---:|---:|---:|---:|---:|---:|
| seed=7,lop=0.005000 | 1000 | 53 | 53 | 1 | 0.981132 | 0.018868 |
| seed=7,lop=0.008000 | 1000 | 82 | 83 | 1 | 0.987805 | 0.012195 |
| seed=7,lop=0.011000 | 1000 | 117 | 118 | 1 | 0.991453 | 0.008547 |
| seed=7,lop=0.014000 | 1000 | 154 | 156 | 1 | 0.993506 | 0.006494 |
| seed=7,lop=0.017000 | 1000 | 175 | 179 | 0 | 1.000000 | 0.000000 |
| seed=7,lop=0.020000 | 1000 | 201 | 205 | 0 | 1.000000 | 0.000000 |
| seed=42,lop=0.005000 | 1000 | 53 | 53 | 0 | 1.000000 | 0.000000 |
| seed=42,lop=0.008000 | 1000 | 83 | 83 | 0 | 1.000000 | 0.000000 |
| seed=42,lop=0.011000 | 1000 | 113 | 113 | 0 | 1.000000 | 0.000000 |
| seed=42,lop=0.014000 | 1000 | 152 | 152 | 0 | 1.000000 | 0.000000 |
| seed=42,lop=0.017000 | 1000 | 189 | 189 | 0 | 1.000000 | 0.000000 |
| seed=42,lop=0.020000 | 1000 | 217 | 217 | 0 | 1.000000 | 0.000000 |
| seed=100,lop=0.005000 | 1000 | 45 | 46 | 0 | 1.000000 | 0.000000 |
| seed=100,lop=0.008000 | 1000 | 75 | 76 | 0 | 1.000000 | 0.000000 |
| seed=100,lop=0.011000 | 1000 | 100 | 101 | 0 | 1.000000 | 0.000000 |
| seed=100,lop=0.014000 | 1000 | 136 | 138 | 0 | 1.000000 | 0.000000 |
| seed=100,lop=0.017000 | 1000 | 169 | 171 | 0 | 1.000000 | 0.000000 |
| seed=100,lop=0.020000 | 1000 | 194 | 196 | 0 | 1.000000 | 0.000000 |
| seed=200,lop=0.005000 | 1000 | 42 | 42 | 0 | 1.000000 | 0.000000 |
| seed=200,lop=0.008000 | 1000 | 69 | 69 | 0 | 1.000000 | 0.000000 |
| seed=200,lop=0.011000 | 1000 | 102 | 102 | 0 | 1.000000 | 0.000000 |
| seed=200,lop=0.014000 | 1000 | 139 | 138 | 1 | 0.992806 | 0.007194 |
| seed=200,lop=0.017000 | 1000 | 174 | 175 | 0 | 1.000000 | 0.000000 |
| seed=200,lop=0.020000 | 1000 | 209 | 208 | 2 | 0.990431 | 0.009569 |
| seed=300,lop=0.005000 | 1000 | 52 | 52 | 0 | 1.000000 | 0.000000 |
| seed=300,lop=0.008000 | 1000 | 84 | 84 | 0 | 1.000000 | 0.000000 |
| seed=300,lop=0.011000 | 1000 | 116 | 116 | 0 | 1.000000 | 0.000000 |
| seed=300,lop=0.014000 | 1000 | 133 | 133 | 0 | 1.000000 | 0.000000 |
| seed=300,lop=0.017000 | 1000 | 158 | 158 | 0 | 1.000000 | 0.000000 |
| seed=300,lop=0.020000 | 1000 | 184 | 184 | 0 | 1.000000 | 0.000000 |

## 6b. By split Table

| split | n_total | dc_fail | ac_fail | false_cert | P(ac_fail|dc_fail) | availability |
|---|---:|---:|---:|---:|---:|---|
| train | 24000 | 3043 | 3063 | 7 | 0.997700 | available |
| validation | 6000 | 727 | 727 | 0 | 1.000000 | available |
| unseen | 0 | 0 | 0 | 0 | N/A | not_available |
| other | 0 | 0 | 0 | 0 | N/A | not_available |

## 7. False Certificate Cases

- False certificate total: `7`.
- Regimes with nonzero false certificate count:
- seed=7 lop=0.005: false=1 / dc_fail=53 (0.018868)
- seed=7 lop=0.008: false=1 / dc_fail=82 (0.012195)
- seed=7 lop=0.011: false=1 / dc_fail=117 (0.008547)
- seed=7 lop=0.014: false=1 / dc_fail=154 (0.006494)
- seed=200 lop=0.014: false=1 / dc_fail=139 (0.007194)
- seed=200 lop=0.02: false=2 / dc_fail=209 (0.009569)

## 8. Interpretation

- DCOPF failure is not universally safe as a certificate in this dataset; the nonzero false-certificate regimes above must be excluded or further modeled.

## 9. Implication for DA

- A4 parameterization should focus on separating high-confidence DCOPF failures from uncertain failures before any shortcut attempt.