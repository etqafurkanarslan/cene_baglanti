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


@dataclass(frozen=True)
class PlacementConfig:
    """Configuration for mount placement feature extraction."""

    patch_radius_mm: float = 35.0
    center_band_mm: float = 8.0
    front_percentile: float = 75.0
    lower_percentile: float = 35.0


DEFAULT_PLACEMENT_CONFIG = PlacementConfig()
