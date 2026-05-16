"""Centralized configuration defaults for the AC extension."""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OSQP_NOISE_PATH = (PROJECT_ROOT / "matpower" / "mp-opt-model" / ".github" / "osqp").resolve()
PGLIB_PATH = (PROJECT_ROOT / "pglib-opf").resolve()


@dataclass(frozen=True)
class ACConfig:
    """Unified config container."""

    N: int = 2000
    p0: float = 0.1
    tol: float = 0.8
    sigma0: float = 0.05
    sigma_decay: float = 0.5
    ac_fail_as_violation: bool = True
    line_outage_prob: float = 0.01
    bus_outage_prob: float = 0.002
    level0_guard_mode: str = "legacy_truth_score"
    da_trace_enabled: bool = False
    da_trace_output_path: str = ""
    da_trace_run_id: str = ""
    benchmark_seed: int = 0
    gen_derate_state_values: tuple[float, ...] = (1.0, 0.8, 0.5, 0.0)
    gen_derate_state_probs: tuple[float, ...] = (0.94, 0.04, 0.015, 0.005)

    def to_dict(self) -> Dict[str, Any]:
        """Return config values as a plain dictionary."""
        return asdict(self)


DEFAULTS = ACConfig().to_dict()
