#!/usr/bin/env bash
set -euo pipefail
PY=/home/lhftr/venv310/bin/python

cd "$(dirname "$0")/.."

echo "[$(date '+%F %T')] Step 1 start: collect data"
"$PY" ac_ext/experiments/collect_ml_training_data.py \
  --case case118 \
  --seeds 7 42 100 200 300 \
  --n-per-seed 1000 \
  --line-outage-probs 0.005 0.008 0.011 0.014 0.017 0.02

echo "[$(date '+%F %T')] Step 2 start: train model"
"$PY" ac_ext/experiments/train_ml_surrogate.py

echo "[$(date '+%F %T')] Step 4 start: benchmark"
"$PY" ac_ext/experiments/run_ml_surrogate_benchmark.py \
  --case case118 \
  --N 1000 \
  --seeds 400 500 600 \
  --sus-p0 0.15 \
  --line-outage-prob 0.008

echo "[$(date '+%F %T')] Pipeline completed"
