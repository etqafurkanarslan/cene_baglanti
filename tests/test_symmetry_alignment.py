"""Tests for approximate symmetry solving and canonical alignment."""

import numpy as np
import trimesh

from app.config import SymmetrySearchConfig
from app.geometry.align import build_alignment_transform_from_plane
from app.geometry.symmetry import solve_symmetry_plane


def test_symmetry_solver_finds_translated_box_center_plane() -> None:
    """A symmetric translated box should solve to an X-normal center plane."""

    mesh = trimesh.creation.box(extents=(4.0, 8.0, 6.0))
    mesh.apply_translation([3.25, -1.0, 2.0])
    config = SymmetrySearchConfig(
        max_sample=1000,
        angle_range_deg=6.0,
        angle_step_deg=3.0,
        offset_ratio=0.05,
        offset_steps=5,
        trim_ratio=0.0,
    )

    result = solve_symmetry_plane(mesh, config)

    assert result.status == "completed"
    assert result.score < 1e-8
    assert np.allclose(result.plane_normal, [1.0, 0.0, 0.0], atol=1e-8)
    assert abs(result.plane_point[0] - 3.25) < 1e-8


def test_alignment_transform_maps_solved_plane_to_x_zero() -> None:
    """The canonical alignment transform should place the plane at x=0."""

    plane_point = np.array([3.25, -1.0, 2.0], dtype=float)
    plane_normal = np.array([1.0, 0.0, 0.0], dtype=float)

    transform = build_alignment_transform_from_plane(plane_point, plane_normal)

    transformed_point = transform @ np.array([*plane_point, 1.0], dtype=float)
    transformed_normal = transform[:3, :3] @ plane_normal
    assert abs(transformed_point[0]) < 1e-10
    assert np.allclose(transformed_normal, [1.0, 0.0, 0.0], atol=1e-10)
