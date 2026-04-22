"""Tests for mount placement feature extraction."""

import numpy as np
import trimesh

from app.config import PlacementConfig
from app.geometry.features import estimate_local_frame, estimate_mount_center
from app.geometry.symmetry import SymmetryResult


def test_mount_center_prefers_front_lower_chin_region() -> None:
    """Automatic placement should pick a centered front anchor region."""

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

    assert source == "auto_chin_anchor"
    assert chin_region.metadata["vertex_count"] >= 3
    assert abs(center[0]) < 1e-10
    assert center[1] >= 8.0
    assert center[2] >= -5.5
    assert estimate.metadata["selection_method"] == "chin_anchor_frontier_centerline_density_top_mean"
    assert abs(estimate.anchor_point[0]) < 1e-10
    assert estimate.anchor_score > 0.0
    assert len(estimate.centerline_band_points) > 0
    assert len(estimate.frontier_band_points) > 0


def test_chin_anchor_can_shift_final_center_from_legacy_center() -> None:
    """Anchor-based placement should be able to move away from the legacy center."""

    mesh = _anchor_shift_test_mesh()
    symmetry = _canonical_symmetry()

    estimate = estimate_mount_center(
        mesh,
        symmetry,
        config=PlacementConfig(
            patch_radius_mm=6.0,
            center_band_mm=1.5,
            front_percentile=65.0,
            lower_percentile=45.0,
        ),
    )

    assert np.linalg.norm(estimate.center - estimate.legacy_center) > 0.1
    assert np.isclose(estimate.center[0], 0.0)
    assert abs(estimate.center[0]) <= abs(estimate.legacy_center[0])
    assert estimate.center[2] > estimate.legacy_center[2]


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


def _anchor_shift_test_mesh() -> trimesh.Trimesh:
    """Build a sparse mesh where the anchor should move above the legacy center."""

    vertices = np.array(
        [
            [-7.0, -5.0, 4.0],
            [7.0, -5.0, 4.0],
            [-6.0, 3.0, 2.0],
            [6.0, 3.0, 2.0],
            [-0.2, 10.7, -6.1],
            [0.2, 10.7, -6.0],
            [-0.4, 10.8, -5.8],
            [0.4, 10.8, -5.7],
            [-0.6, 10.9, -4.4],
            [-0.3, 10.9, -4.3],
            [0.0, 10.9, -4.2],
            [0.3, 10.9, -4.2],
            [0.6, 10.9, -4.3],
            [-0.2, 11.0, -4.1],
            [0.0, 11.0, -4.0],
            [0.2, 11.0, -4.1],
        ],
        dtype=float,
    )
    return trimesh.Trimesh(vertices=vertices, faces=np.empty((0, 3), dtype=int), process=False)
