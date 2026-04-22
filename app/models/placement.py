"""Placement override models used by UI-driven regeneration."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class PlacementOverride:
    """User-authored adapter placement override."""

    case_id: str | None
    mount_asset_path: Path | None
    mount_center: np.ndarray
    mount_rotation_euler_deg: np.ndarray
    mount_offset_mm: float
    projection_direction_mode: str = "frame-z-negative"
    footprint_margin_mm: float = 2.0
    contact_offset_mm: float | None = None
    wall_thickness_mm: float | None = None
    notes: str = ""

