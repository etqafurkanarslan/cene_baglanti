"""Tests for V1 saddle mesh generation."""

import numpy as np

from app.geometry.features import LocalPatch, MountFrame
from app.geometry.saddle import SaddleConfig, generate_saddle


def test_saddle_generation_is_valid_and_deterministic() -> None:
    """Same patch/frame/config should produce stable mesh stats."""

    frame = _test_mount_frame()
    patch = _test_patch()
    config = SaddleConfig(
        contact_offset_mm=0.5,
        footprint_width_mm=20.0,
        footprint_height_mm=14.0,
        saddle_height_mm=6.0,
        wall_thickness_mm=2.0,
        profile_samples=24,
        patch_radius_mm=12.0,
    )

    first = generate_saddle(frame, patch, config)
    second = generate_saddle(frame, patch, config)

    assert first.validation["vertex_count"] > 0
    assert first.validation["face_count"] > 0
    assert first.validation["is_watertight"]
    assert first.mesh_stats == second.mesh_stats
    assert first.debug["generated_profile_stats"] == second.debug["generated_profile_stats"]


def test_footprint_override_changes_generated_bounds() -> None:
    """Footprint width override should affect final mesh bounds."""

    frame = _test_mount_frame()
    patch = _test_patch()

    narrow = generate_saddle(
        frame,
        patch,
        SaddleConfig(footprint_width_mm=16.0, footprint_height_mm=14.0, profile_samples=24),
    )
    wide = generate_saddle(
        frame,
        patch,
        SaddleConfig(footprint_width_mm=30.0, footprint_height_mm=14.0, profile_samples=24),
    )

    narrow_width = _bounds_width(narrow.mesh_stats["final"])
    wide_width = _bounds_width(wide.mesh_stats["final"])
    assert wide_width > narrow_width


def _test_mount_frame() -> MountFrame:
    return MountFrame(
        origin=np.array([0.0, 0.0, 0.0], dtype=float),
        x_axis=np.array([1.0, 0.0, 0.0], dtype=float),
        y_axis=np.array([0.0, 1.0, 0.0], dtype=float),
        z_axis=np.array([0.0, 0.0, 1.0], dtype=float),
        source="test",
    )


def _test_patch() -> LocalPatch:
    xs = np.linspace(-12.0, 12.0, 7)
    ys = np.linspace(-10.0, 10.0, 7)
    points = []
    for x in xs:
        for y in ys:
            z = -0.03 * x * x - 0.02 * y * y
            points.append([x, y, z])
    points_array = np.array(points, dtype=float)
    return LocalPatch(
        points=points_array,
        vertex_indices=np.arange(len(points_array)),
        radius_mm=16.0,
        metadata={"vertex_count": len(points_array), "radius_mm": 16.0},
    )


def _bounds_width(stats: dict[str, object]) -> float:
    bounds_min = stats["bounds_min"]
    bounds_max = stats["bounds_max"]
    assert isinstance(bounds_min, list)
    assert isinstance(bounds_max, list)
    return float(bounds_max[0]) - float(bounds_min[0])
