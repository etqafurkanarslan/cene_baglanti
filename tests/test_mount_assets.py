"""Tests for mount asset import and frame transform behavior."""

import numpy as np
import trimesh
from pathlib import Path

from app.geometry.features import MountFrame
from app.geometry.mount_assets import resolve_mount_asset
from app.geometry.saddle import SaddleConfig


def test_real_mount_asset_import_and_transform() -> None:
    """A valid asset file should load as a real asset in mount coordinates."""

    work_dir = _work_dir("real_asset")
    asset_path = work_dir / "asset.stl"
    trimesh.creation.box(extents=(2.0, 4.0, 6.0)).export(asset_path)
    frame = _test_frame()

    asset = resolve_mount_asset(frame, SaddleConfig(), asset_path)

    assert asset.type == "real"
    assert asset.loaded_successfully is True
    assert asset.vertex_count > 0
    assert asset.face_count > 0
    transformed_centroid = np.asarray(asset.mesh.centroid, dtype=float)
    assert np.linalg.norm(transformed_centroid - frame.origin) < 1e-6


def test_invalid_mount_asset_falls_back_to_placeholder() -> None:
    """Missing or broken assets should fall back without breaking the run."""

    frame = _test_frame()
    asset = resolve_mount_asset(frame, SaddleConfig(), _work_dir("missing_asset") / "missing.stl")

    assert asset.type == "placeholder"
    assert asset.loaded_successfully is False
    assert asset.warning is not None
    assert asset.vertex_count > 0


def _test_frame() -> MountFrame:
    return MountFrame(
        origin=np.array([10.0, 20.0, 30.0], dtype=float),
        x_axis=np.array([1.0, 0.0, 0.0], dtype=float),
        y_axis=np.array([0.0, 1.0, 0.0], dtype=float),
        z_axis=np.array([0.0, 0.0, 1.0], dtype=float),
        source="test",
        metadata={"determinant": 1.0, "handedness": "right_handed", "z_axis_outward_score": 1.0},
    )


def _work_dir(name: str) -> Path:
    path = Path("outputs") / "test_mount_assets" / name
    path.mkdir(parents=True, exist_ok=True)
    return path
