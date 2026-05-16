# \# Phase 5 Proxy Diagnostics Results

# 

# \## Purpose

# This document records the final Phase 5 proxy-diagnostics findings after the initial `case14` pass and the follow-up verification on `case30` and `pglib\_opf\_case57\_ieee`.

# 

# The Phase 5 goal was not to assume that one proxy must win in advance, but to determine whether tested proxy candidates carry enough information to justify later multifidelity use.

# 

# \## Tested truth/proxy combinations

# 

# \### Truth solvers

# \- `acopf`

# \- `acpf`

# 

# \### Proxy candidates

# \- `dcpf`

# \- `fdxb`

# 

# \### Damage regimes used in follow-up diagnostics

# \- Light damage on `case14`

# \- Heavier line-outage regime on `case30`

# \- Moderate line-outage regime on `pglib\_opf\_case57\_ieee`

# 

# ---

# 

# \## Round 1: `case14`, `truth = acopf`, light damage

# 

# \### DCPF

# Artifacts:

# \- `ac\_ext/experiments/out/diag\_dcpf/proxy\_diagnostics.csv`

# \- `ac\_ext/experiments/out/diag\_dcpf/truth\_vs\_proxy\_scatter.png`

# \- `ac\_ext/experiments/out/diag\_dcpf/proxy\_quantile\_truth\_mean.png`

# 

# Summary:

# \- finite\_pair\_count: `194 / 200`

# \- Pearson(s\_any): `1.3129918688133189e-17`

# \- Spearman(s\_any): `null`

# \- top-10% Jaccard: `0.21212121212121213`

# \- overlap: `7 / 20`

# \- overlap\_rate: `0.35`

# 

# Interpretation:

# \- DCPF was technically integrated and diagnostics-complete.

# \- Under this setup, DCPF scores collapsed to an almost constant value for most finite samples.

# \- This removed almost all usable ranking signal.

# \- Shared `+Inf` failures still produced some overlap on the most extreme states.

# 

# \### FDXB

# Artifacts:

# \- `ac\_ext/experiments/out/diag\_fdxb/proxy\_diagnostics.csv`

# \- `ac\_ext/experiments/out/diag\_fdxb/truth\_vs\_proxy\_scatter.png`

# \- `ac\_ext/experiments/out/diag\_fdxb/proxy\_quantile\_truth\_mean.png`

# 

# Summary:

# \- finite\_pair\_count: `194 / 200`

# \- Pearson(s\_any): `0.10055052057097247`

# \- Spearman(s\_any): `0.12086706276182277`

# \- top-10% Jaccard: `0.21212121212121213`

# \- overlap: `7 / 20`

# \- overlap\_rate: `0.35`

# 

# Interpretation:

# \- FDXB was also technically integrated and diagnostics-complete.

# \- Under `case14 + acopf`, FDXB was still weak, but it preserved more score variation than DCPF.

# \- This justified treating FDXB as the provisional default candidate after the initial pass, but not as a strong proxy.

# 

# Interim conclusion from `case14`:

# \- `FDXB > DCPF`, but both were weak under this small-system light-damage setup.

# \- A more realistic system and a stronger damage regime were required before making a durable proxy decision.

# 

# ---

# 

# \## Round 2: `case30`, heavier damage, `truth = acopf`

# 

# \### DCPF vs ACOPF

# Summary:

# \- finite\_pair\_count: `92 / 200`

# \- Pearson(s\_any): `-0.010753197587093297`

# \- Spearman(s\_any): `-0.17587606581570125`

# \- top-10% Jaccard: `0.5384615384615384`

# \- overlap: `14 / 20`

# \- overlap\_rate: `0.7`

# 

# Interpretation:

# \- DCPF became useful as a coarse detector of the most extreme failures.

# \- However, continuous ranking on finite samples remained poor.

# \- The result suggested that DCPF may help catch some top-risk states, but does not behave like a reliable smooth ranking proxy for ACOPF severity.

# 

# \### FDXB vs ACOPF

# Summary:

# \- finite\_pair\_count: `92 / 200`

# \- Pearson(s\_any): `0.05787419031509335`

# \- Spearman(s\_any): `0.27836863064995704`

# \- top-10% Jaccard: `0.5384615384615384`

# \- overlap: `14 / 20`

# \- overlap\_rate: `0.7`

# 

# Interpretation:

# \- FDXB again outperformed DCPF on ranking signal.

# \- Like DCPF, it still relied partly on shared extreme failures, but it preserved more usable ordering information within the finite region.

# \- This strengthened the case that FDXB should be preferred over DCPF for ACOPF-facing screening.

# 

# Interim conclusion from `case30 + acopf`:

# \- Both proxies can help identify very dangerous states under heavier damage.

# \- FDXB is clearly better than DCPF as a ranking-oriented Stage-1 candidate.

# \- Neither behaves like a high-fidelity surrogate for ACOPF.

# 

# ---

# 

# \## Round 3: truth-mismatch control on `case30`

# 

# \### DCPF vs ACPF

# Summary:

# \- finite\_pair\_count: `129 / 200`

# \- Pearson(s\_any): `0.45047258349502817`

# \- Spearman(s\_any): `0.05642982710257793`

# \- top-10% Jaccard: `1.0`

# \- overlap: `20 / 20`

# \- overlap\_rate: `1.0`

# 

# Interpretation:

# \- DCPF aligns much better with ACPF than with ACOPF on extreme states.

# \- It still lacks strong smooth ranking power, but it no longer appears fundamentally disconnected from the truth target.

# 

# \### FDXB vs ACPF

# Summary:

# \- finite\_pair\_count: `129 / 200`

# \- Pearson(s\_any): `0.9999999999999988`

# \- Spearman(s\_any): `1.0`

# \- top-10% Jaccard: `1.0`

# \- overlap: `20 / 20`

# \- overlap\_rate: `1.0`

# 

# Interpretation:

# \- FDXB is effectively a perfect proxy for ACPF under this diagnostic setup.

# \- This is the strongest evidence collected in Phase 5.

# 

# Major finding from the ACPF control:

# \- The main limitation is \*\*not\*\* that PF-family proxies are intrinsically useless.

# \- The main limitation is \*\*truth mismatch\*\*: PF-family proxies track ACPF very well, but degrade when asked to rank ACOPF outcomes that include redispatch and optimization logic.

# 

# ---

# 

# \## Round 4: `pglib\_opf\_case57\_ieee`, `truth = acopf`, DCPF

# 

# \### DCPF vs ACOPF on PGLib-57

# Artifacts:

# \- `ac\_ext/experiments/out/diag\_pglib57\_v3/proxy\_diagnostics.csv`

# \- `ac\_ext/experiments/out/diag\_pglib57\_v3/truth\_vs\_proxy\_scatter.png`

# \- `ac\_ext/experiments/out/diag\_pglib57\_v3/proxy\_quantile\_truth\_mean.png`

# 

# Summary:

# \- finite\_pair\_count: `41 / 200`

# \- Pearson(s\_any): `0.1659629710936674`

# \- Spearman(s\_any): `0.17414507056543663`

# \- top-10% Jaccard: `0.1111111111111111`

# \- overlap: `4 / 20`

# \- overlap\_rate: `0.2`

# 

# Interpretation:

# \- On a more realistic PGLib-style case, DCPF remained weak against ACOPF.

# \- The top-risk overlap dropped sharply relative to the `case30` heavy-damage result.

# \- This substantially weakens any claim that DCPF should remain a serious ACOPF default Stage-1 candidate.

# 

# ---

# 

# \## Final Phase 5 conclusions

# 

# \### 1. DCPF is not the right default proxy for ACOPF-facing workflows

# DCPF is still useful as:

# \- a baseline comparison,

# \- a debugging tool,

# \- an extreme-failure detector in some settings.

# 

# But the full Phase 5 evidence does \*\*not\*\* support DCPF as the default Stage-1 proxy for ACOPF-based rare-event estimation.

# 

# \### 2. FDXB is the strongest tested PF-family proxy

# FDXB is:

# \- a near-perfect proxy for ACPF under the tested setup,

# \- clearly better than DCPF for ACOPF-facing screening,

# \- still only a \*\*coarse screening proxy\*\* for ACOPF rather than a high-fidelity surrogate.

# 

# \### 3. The key Phase 5 research finding is truth mismatch

# The central result of Phase 5 is:

# \- PF-family proxies are not generically bad;

# \- they become weak when the truth target is upgraded from power-flow evaluation to optimization-aware ACOPF.

# 

# This finding is important because it explains why later controller design must be \*\*proxy-tolerant\*\* rather than dependent on a near-perfect surrogate.

# 

# ---

# 

# \## Recommended next action

# \- Use `FDXB` as the default tested Stage-1 proxy candidate for the next development round.

# \- Keep `DCPF` as baseline/debug only.

# \- Build the next controller layer so that it is evaluator-agnostic and robust to weak proxies.

# \- Treat delayed-acceptance logic as the place where a coarse proxy is useful, rather than expecting strong one-stage ranking fidelity from the proxy alone.

# 

