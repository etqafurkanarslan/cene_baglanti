"""Mesh alignment stubs."""

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
    """Align the helmet mesh to a canonical reference frame.

    This bootstrap implementation keeps the mesh unchanged and returns the
    identity transform. Future versions should use the solved symmetry plane.
    """

    _ = symmetry
    return AlignmentResult(
        mesh=mesh.copy(),
        transform=np.eye(4, dtype=float),
        status="stub",
        message="Alignment stub returned input mesh with identity transform.",
    )

