"""Mount geometry asset interface."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh

from app.geometry.features import MountFrame
from app.geometry.saddle import SaddleConfig, loft_or_bridge_between_profiles


@dataclass(frozen=True)
class MountAsset:
    """Resolved mount asset mesh and provenance."""

    mesh: trimesh.Trimesh
    type: str
    source: str
    warning: str | None = None


def resolve_mount_asset(
    mount_frame: MountFrame,
    config: SaddleConfig,
    asset_path: Optional[Path] = None,
) -> MountAsset:
    """Resolve a mount mesh asset, falling back to the placeholder mount."""

    if asset_path is None:
        return MountAsset(
            mesh=build_placeholder_mount(mount_frame, config),
            type="placeholder",
            source="generated_oval_plate",
        )
    return MountAsset(
        mesh=build_placeholder_mount(mount_frame, config),
        type="placeholder",
        source=str(asset_path),
        warning="External mount asset import is not implemented yet; used placeholder.",
    )


def build_placeholder_mount(
    mount_frame: MountFrame,
    config: SaddleConfig,
) -> trimesh.Trimesh:
    """Build the current oval mount placeholder."""

    sample_count = max(12, int(config.profile_samples))
    angles = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    half_width = config.footprint_width_mm * 0.5
    half_height = config.footprint_height_mm * 0.5
    bottom_z = config.saddle_height_mm
    top_z = config.saddle_height_mm + max(config.wall_thickness_mm, 0.5)
    bottom = np.column_stack(
        [half_width * np.cos(angles), half_height * np.sin(angles), np.full(sample_count, bottom_z)]
    )
    top = np.column_stack(
        [half_width * np.cos(angles), half_height * np.sin(angles), np.full(sample_count, top_z)]
    )
    mesh, _ = loft_or_bridge_between_profiles(mount_frame, top, bottom)
    return mesh


def transform_mount_asset_to_frame(
    mesh: trimesh.Trimesh,
    mount_frame: MountFrame,
) -> trimesh.Trimesh:
    """Placeholder hook for future real asset transforms."""

    _ = mount_frame
    return mesh.copy()
