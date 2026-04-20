"""Mesh alignment utilities."""

from dataclasses import dataclass

import numpy as np
import trimesh

from app.geometry.symmetry import SymmetryResult


@dataclass(frozen=True)
class AlignmentResult:
    """Result of aligning a helmet mesh to the project reference frame."""

    mesh: trimesh.Trimesh
    transform: np.ndarray
    status: str
    message: str


def align_to_reference_frame(
    mesh: trimesh.Trimesh,
    symmetry: SymmetryResult,
) -> AlignmentResult:
    """Align the helmet mesh so the symmetry plane becomes x=0."""

    transform = build_alignment_transform_from_plane(
        plane_point=symmetry.plane_point,
        plane_normal=symmetry.plane_normal,
    )
    aligned_mesh = apply_transform_to_mesh(mesh, transform)
    return AlignmentResult(
        mesh=aligned_mesh,
        transform=transform,
        status="completed",
        message="Aligned mesh to canonical frame with symmetry plane at x=0.",
    )


def build_alignment_transform_from_plane(
    plane_point: np.ndarray,
    plane_normal: np.ndarray,
) -> np.ndarray:
    """Build a transform that maps a plane normal to +X and plane to x=0."""

    normal = _unit_vector(plane_normal)
    target = np.array([1.0, 0.0, 0.0], dtype=float)
    rotation = _rotation_between_vectors(normal, target)
    rotated_point = rotation @ np.asarray(plane_point, dtype=float)

    transform = np.eye(4, dtype=float)
    transform[:3, :3] = rotation
    transform[0, 3] = -rotated_point[0]
    return transform


def apply_transform_to_mesh(
    mesh: trimesh.Trimesh,
    transform: np.ndarray,
) -> trimesh.Trimesh:
    """Return a transformed copy of a mesh."""

    aligned = mesh.copy()
    aligned.apply_transform(transform)
    return aligned


def _rotation_between_vectors(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return the shortest rotation matrix mapping source to target."""

    source_unit = _unit_vector(source)
    target_unit = _unit_vector(target)
    cross = np.cross(source_unit, target_unit)
    dot = float(np.clip(np.dot(source_unit, target_unit), -1.0, 1.0))

    if np.linalg.norm(cross) <= 1e-12:
        if dot > 0.0:
            return np.eye(3, dtype=float)
        return np.diag([-1.0, -1.0, 1.0])

    skew = np.array(
        [
            [0.0, -cross[2], cross[1]],
            [cross[2], 0.0, -cross[0]],
            [-cross[1], cross[0], 0.0],
        ],
        dtype=float,
    )
    return np.eye(3, dtype=float) + skew + skew @ skew * (1.0 / (1.0 + dot))


def _unit_vector(vector: np.ndarray) -> np.ndarray:
    """Normalize a vector and reject degenerate input."""

    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("Cannot normalize a zero-length vector.")
    return np.asarray(vector, dtype=float) / norm
