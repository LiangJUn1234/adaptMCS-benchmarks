"""Centralized configuration defaults for the AC extension skeleton."""

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass(frozen=True)
class ACConfig:
    """Unified config container for Phase 1 defaults."""

    N: int = 2000
    p0: float = 0.1
    tol: float = 0.8
    sigma0: float = 0.05
    sigma_decay: float = 0.5
    ac_fail_as_violation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Return config values as a plain dictionary."""
        return asdict(self)


DEFAULTS = ACConfig().to_dict()
