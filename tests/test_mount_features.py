"""Tests for mount placement feature extraction."""

import numpy as np
import trimesh

from app.config import PlacementConfig
from app.geometry.features import estimate_local_frame, estimate_mount_center
from app.geometry.symmetry import SymmetryResult


def test_mount_center_prefers_front_lower_chin_region() -> None:
    """Automatic placement should pick the centered front/lower region."""

    mesh = _feature_test_mesh()
    symmetry = _canonical_symmetry()
    config = PlacementConfig(
        patch_radius_mm=6.0,
        center_band_mm=1.0,
        front_percentile=70.0,
        lower_percentile=35.0,
    )

    estimate = estimate_mount_center(mesh, symmetry, config=config)
    center = estimate.center
    source = estimate.source
    chin_region = estimate.chin_region

    assert source == "auto_chin_region"
    assert chin_region.metadata["vertex_count"] >= 3
    assert abs(center[0]) < 1e-10
    assert center[1] >= 8.0
    assert center[2] <= -4.0
    assert estimate.metadata["selection_method"] == "frontier_first_centerline_weighted_top_mean"


def test_local_frame_is_orthonormal() -> None:
    """Estimated mount frame axes should be unit length and perpendicular."""

    mesh = _feature_test_mesh()
    symmetry = _canonical_symmetry()
    center = np.array([0.0, 10.0, -5.0], dtype=float)

    frame, patch = estimate_local_frame(
        mesh=mesh,
        mount_center=center,
        symmetry_result=symmetry,
        patch_radius_mm=6.0,
    )

    axes = [frame.x_axis, frame.y_axis, frame.z_axis]
    assert patch.metadata["vertex_count"] > 0
    for axis in axes:
        assert np.isclose(np.linalg.norm(axis), 1.0, atol=1e-8)
    assert np.isclose(np.dot(frame.x_axis, frame.y_axis), 0.0, atol=1e-8)
    assert np.isclose(np.dot(frame.x_axis, frame.z_axis), 0.0, atol=1e-8)
    assert np.isclose(np.dot(frame.y_axis, frame.z_axis), 0.0, atol=1e-8)
    assert frame.metadata is not None
    assert frame.metadata["handedness"] == "right_handed"
    assert frame.metadata["z_axis_outward_score"] >= 0.0


def _feature_test_mesh() -> trimesh.Trimesh:
    """Build a sparse canonical helmet-like vertex set with a chin cluster."""

    shell_points = [
        [-8.0, -8.0, 2.0],
        [8.0, -8.0, 2.0],
        [-8.0, 0.0, 7.0],
        [8.0, 0.0, 7.0],
        [-7.0, 7.0, 3.0],
        [7.0, 7.0, 3.0],
        [-6.0, 9.0, -1.0],
        [6.0, 9.0, -1.0],
    ]
    chin_points = [
        [-0.5, 9.5, -5.5],
        [0.0, 10.0, -5.0],
        [0.5, 10.5, -4.5],
        [0.0, 11.0, -5.2],
        [0.0, 9.8, -4.8],
    ]
    vertices = np.array(shell_points + chin_points, dtype=float)
    return trimesh.Trimesh(vertices=vertices, faces=np.empty((0, 3), dtype=int), process=False)


def _canonical_symmetry() -> SymmetryResult:
    """Return a canonical x=0 symmetry result for placement tests."""

    return SymmetryResult(
        plane_point=np.array([0.0, 0.0, 0.0], dtype=float),
        plane_normal=np.array([1.0, 0.0, 0.0], dtype=float),
        score=0.0,
        sample_count=0,
        search_config={},
        normal=np.array([1.0, 0.0, 0.0], dtype=float),
        origin=np.array([0.0, 0.0, 0.0], dtype=float),
        status="completed",
        message="canonical",
    )
