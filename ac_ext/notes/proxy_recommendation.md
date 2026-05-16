\# Proxy Selection Recommendation



\## Current recommendation

\*\*Use FDXB as the default tested Stage-1 proxy candidate.\*\*



\*\*Do not use DCPF as the default Stage-1 proxy for ACOPF-based workflows.\*\*



\## Why this recommendation changed

The initial `case14` diagnostics only supported a weak provisional preference for FDXB over DCPF. Later follow-up runs on `case30` and `pglib\_opf\_case57\_ieee` clarified the situation:



\- FDXB is consistently stronger than DCPF as a ranking-oriented PF-family proxy.

\- DCPF can still detect some extreme failures, but it is too weak and unstable to remain the ACOPF default proxy.

\- The main issue is not implementation failure; it is \*\*truth mismatch\*\* between PF-family proxies and optimization-based ACOPF truth.



\## Evidence summary



\### Under `truth = acopf`

\- DCPF is weak on `case14`.

\- DCPF remains weak on PGLib-57 and even loses strong top-risk overlap there.

\- FDXB is better than DCPF, but still behaves as a \*\*coarse screening proxy\*\*, not a high-fidelity ACOPF surrogate.



\### Under `truth = acpf`

\- FDXB behaves almost perfectly.

\- DCPF improves, especially on extreme-state overlap, but still does not match FDXB.



\## Operational interpretation



\### FDXB

Use FDXB as:

\- the main tested Stage-1 proxy candidate,

\- the default proxy for future delayed-acceptance experiments,

\- a strong proxy when the truth target is ACPF,

\- a coarse screening proxy when the truth target is ACOPF.



\### DCPF

Keep DCPF only as:

\- baseline,

\- debug comparator,

\- occasional extreme-failure detector,

\- sanity-check reference.



Do \*\*not\*\* treat DCPF as the preferred ACOPF-facing screening model.



\## What this means for the next phase

The next controller should be designed under the assumption that:

\- the proxy may be weak against ACOPF,

\- the proxy still has value as a cheap filter,

\- correctness must still come from the truth layer.



In practice this means:

\- build an evaluator-agnostic SuS controller,

\- support truth-only and proxy-only modes first,

\- add delayed-acceptance logic after the controller and discrete MCMC kernel are stable,

\- do not hard-code assumptions that the proxy is strongly rank-consistent with ACOPF.



\## Final recommendation sentence

\*\*FDXB should be treated as the default tested Stage-1 proxy candidate; DCPF should be retained only as baseline/debug support; and future controller design should assume proxy weakness against ACOPF rather than rely on near-surrogate behavior.\*\*



