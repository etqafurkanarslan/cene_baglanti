"""Project configuration constants."""

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs"
DEFAULT_MOUNTS_ROOT = PROJECT_ROOT / "mounts"
DEFAULT_SCANS_ROOT = PROJECT_ROOT / "scans"


@dataclass(frozen=True)
class SymmetrySearchConfig:
    """Configuration for approximate symmetry plane search."""

    max_sample: int = 5000
    angle_range_deg: float = 12.0
    angle_step_deg: float = 3.0
    offset_ratio: float = 0.08
    offset_steps: int = 7
    trim_ratio: float = 0.1


DEFAULT_SYMMETRY_CONFIG = SymmetrySearchConfig()
