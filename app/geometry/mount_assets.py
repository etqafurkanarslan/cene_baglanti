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
    loaded_successfully: bool
    vertex_count: int
    face_count: int
    warning: str | None = None
    origin_mode: str = "mount_local_origin"


def resolve_mount_asset(
    mount_frame: MountFrame,
    config: SaddleConfig,
    asset_path: Optional[Path] = None,
    origin_mode: str = "mount-local",
) -> MountAsset:
    """Resolve a mount mesh asset, falling back to the placeholder mount."""

    if asset_path is None:
        mesh = build_placeholder_mount(mount_frame, config)
        return MountAsset(
            mesh=mesh,
            type="placeholder",
            source="generated_oval_plate",
            loaded_successfully=False,
            vertex_count=int(len(mesh.vertices)),
            face_count=int(len(mesh.faces)),
            origin_mode=origin_mode,
        )
    try:
        loaded = _load_mount_mesh(asset_path)
        transformed = transform_mount_asset_to_frame(loaded, mount_frame)
        return MountAsset(
            mesh=transformed,
            type="real",
            source=str(asset_path),
            loaded_successfully=True,
            vertex_count=int(len(transformed.vertices)),
            face_count=int(len(transformed.faces)),
            origin_mode=origin_mode,
        )
    except Exception as exc:
        mesh = build_placeholder_mount(mount_frame, config)
        return MountAsset(
            mesh=mesh,
            type="placeholder",
            source=str(asset_path),
            loaded_successfully=False,
            vertex_count=int(len(mesh.vertices)),
            face_count=int(len(mesh.faces)),
            warning=f"Mount asset import failed; used placeholder. Reason: {exc}",
            origin_mode=origin_mode,
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
    """Transform mount-local asset coordinates into the mount frame.

    Convention: asset local origin is the mount center; local +X/+Y/+Z map to
    mount_frame x_axis/y_axis/z_axis respectively, in millimeters.
    """

    transformed = mesh.copy()
    local = np.asarray(transformed.vertices, dtype=float)
    world = (
        mount_frame.origin
        + local[:, 0, np.newaxis] * mount_frame.x_axis
        + local[:, 1, np.newaxis] * mount_frame.y_axis
        + local[:, 2, np.newaxis] * mount_frame.z_axis
    )
    transformed.vertices = world
    return transformed


def _load_mount_mesh(asset_path: Path) -> trimesh.Trimesh:
    """Load and validate a real mount asset mesh."""

    if not asset_path.exists():
        raise FileNotFoundError(asset_path)
    loaded = trimesh.load(asset_path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(list(loaded.geometry.values()))
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"Unsupported asset type: {type(loaded)!r}")
    if len(loaded.vertices) == 0 or len(loaded.faces) == 0:
        raise ValueError("Asset mesh is empty.")
    vertices = np.asarray(loaded.vertices, dtype=float)
    if not np.isfinite(vertices).all():
        raise ValueError("Asset mesh contains non-finite coordinates.")
    return loaded
