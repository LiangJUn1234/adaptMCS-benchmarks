> **Current priority note:**
> For the ML surrogate / ACOPF-DCOPF project branch, read
> `README_ML_SURROGATE_CURRENT_PRIORITY.md` (in the parent directory) first.
> It supersedes older direct-ML-regression instructions in `EXEC_PLAN_ML_SURROGATE.md`.

# ACOPF-Guided DCOPF Screening for Rare-Event Power Grid Failure Simulation

## Repository Context
This repository lives inside the broader `adaptMCS-benchmarks` codebase and currently serves as the working branch for ACOPF-guided DCOPF screening experiments.

# adaptMCS-benchmarks
Welcome to the official repository for the paper titled "Adaptive Monte Carlo methods for estimating rare events in power grids." This repository is a comprehensive resource for storing the code implementation and benchmarks presented in the paper.
## Description
(TBD)
## Software configuration
MATLAB 2022a  
MATPOWER v7.1  
PYTHON 3.8.8, with matlabengine==9.12 (9.12 is the release number for MATLAB2022a. Check the release number [here](https://en.wikipedia.org/wiki/MATLAB) for different MATLAB versions). Other required libraries include numpy, scipy, matplotlib, etc.
## License
Unless otherwise stated, all codes from this repo. is under a [GPL-2.0](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html#SEC1) license. 

## GitHub Overview

### Project Objective
This repository contains a working branch for ACOPF-guided DCOPF screening inside rare-event power-grid failure simulation. The current focus is reducing expensive ACOPF truth evaluations while preserving rare-event estimates.

### Current Result: A1-Guard
Frozen benchmark slice:
- `case118`
- `N=1000`
- `line_outage_prob=0.008`
- `seeds=901,902,903`

For `corrected_da_dcopf`:
- legacy mean `truth_calls = 1320`
- failure-label mean `truth_calls = 577`
- `l0_truth_calls` reduced `1000 -> 250`
- `K_final` reduced `1000 -> 200`
- mean `pf_hat` unchanged at `0.07945`

### Main Finding
The current A1 result comes from controller-objective alignment, not from changing DCOPF physics:
- raw DCOPF remains unchanged
- DA remains unchanged
- ACOPF truth remains unchanged
- only the Level-0 guard objective changes from ACOPF `s_any` rank protection to ACOPF failure-membership protection

### Repository Structure
- `ac_ext/`: Python controller, problem wrappers, MATLAB engine interface, and experiments
- `ac_ext/matlab/`: MATLAB / MATPOWER helper functions
- `docs/`: copied reports and planning documents for GitHub viewing
- `results/final_guard/`: frozen A1-Guard summary artifacts
- `ac_ext/experiments/out/`: local derived outputs, training data, logs, and non-final artifacts

### Reproducibility Notes
The repository preserves source code, controller logic, MATLAB wrappers, reports, and frozen final summaries. Large derived artifacts remain local and are not intended to be Git-tracked.

### Large Data Note
Raw training CSV files and NPZ flow matrices are not tracked in Git. They are derived artifacts and should be regenerated locally or stored externally.

### Next Step: A2 ACOPF-Guided DCOPF Score Parameter Training
The next planned stage is offline training of DCOPF-derived `l0_score` parameters against ACOPF failure labels, using the branch-level DCOPF flow artifact and ACOPF label table. See `ACOPF_GUIDED_DCOPF_SCORE_PARAMETER_TRAINING_PLAN.md`.
