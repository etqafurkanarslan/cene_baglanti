"""Symmetry estimation stubs."""

from dataclasses import dataclass

import numpy as np
import trimesh


@dataclass(frozen=True)
class SymmetryResult:
    """Estimated symmetry plane for a helmet mesh."""

    origin: np.ndarray
    normal: np.ndarray
    status: str
    message: str


def estimate_symmetry_plane(mesh: trimesh.Trimesh) -> SymmetryResult:
    """Estimate the helmet symmetry plane.

    This bootstrap implementation returns a deterministic center-plane stub.
    A later version should solve this from helmet surface geometry.
    """

    center = np.asarray(mesh.centroid, dtype=float)
    return SymmetryResult(
        origin=center,
        normal=np.array([1.0, 0.0, 0.0], dtype=float),
        status="stub",
        message="Symmetry solver stub used X-axis normal through mesh centroid.",
    )

