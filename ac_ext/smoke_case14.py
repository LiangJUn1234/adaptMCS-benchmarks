"""Tiny smoke runner for single-sample case14 evaluations."""

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ac_ext.config import DEFAULTS
from ac_ext.problem import eval_single_case


if __name__ == "__main__":
    result = eval_single_case("case14", DEFAULTS)
    print(result)
