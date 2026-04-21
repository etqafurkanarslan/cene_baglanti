"""Feature extraction for mount placement on canonical helmet meshes."""

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import trimesh

from app.config import DEFAULT_PLACEMENT_CONFIG, PlacementConfig
from app.geometry.symmetry import SymmetryResult

CenterStrategy = Literal["chin_region"]


@dataclass(frozen=True)
class ChinRegion:
    """Vertex subset used as the chin placement candidate region."""

    points: np.ndarray
    vertex_indices: np.ndarray
    metadata: dict[str, float | int | str]


@dataclass(frozen=True)
class LocalPatch:
    """Radius-based local patch around a mount center."""

    points: np.ndarray
    vertex_indices: np.ndarray
    radius_mm: float
    metadata: dict[str, float | int]


@dataclass(frozen=True)
class MountFrame:
    """Local mount frame estimated from a canonical helmet mesh."""

    origin: np.ndarray
    x_axis: np.ndarray
    y_axis: np.ndarray
    z_axis: np.ndarray
    source: str


def extract_chin_region(
    mesh: trimesh.Trimesh,
    z_percentile: Optional[float] = None,
    y_percentile: Optional[float] = None,
    center_band_mm: Optional[float] = None,
    config: PlacementConfig = DEFAULT_PLACEMENT_CONFIG,
) -> ChinRegion:
    """Extract vertices near the symmetry plane, front side, and lower region."""

    vertices = _vertices(mesh)
    z_cut_percentile = z_percentile if z_percentile is not None else config.lower_percentile
    y_cut_percentile = y_percentile if y_percentile is not None else config.front_percentile
    x_band = center_band_mm if center_band_mm is not None else config.center_band_mm

    z_cut = float(np.percentile(vertices[:, 2], z_cut_percentile))
    y_cut = float(np.percentile(vertices[:, 1], y_cut_percentile))
    mask = (
        (np.abs(vertices[:, 0]) <= x_band)
        & (vertices[:, 1] >= y_cut)
        & (vertices[:, 2] <= z_cut)
    )
    source = "center_front_lower"

    if not np.any(mask):
        mask = (vertices[:, 1] >= y_cut) & (vertices[:, 2] <= z_cut)
        source = "front_lower_relaxed_center_band"
    if not np.any(mask):
        distances = _normalized_rank(vertices[:, 1], high=True) + _normalized_rank(
            vertices[:, 2],
            high=False,
        )
        keep_count = max(1, int(np.ceil(len(vertices) * 0.05)))
        keep_indices = np.argsort(distances)[-keep_count:]
        mask = np.zeros(len(vertices), dtype=bool)
        mask[keep_indices] = True
        source = "front_lower_rank_fallback"

    indices = np.flatnonzero(mask)
    metadata: dict[str, float | int | str] = {
        "source": source,
        "vertex_count": int(len(indices)),
        "center_band_mm": float(x_band),
        "front_percentile": float(y_cut_percentile),
        "lower_percentile": float(z_cut_percentile),
        "front_y_cut": y_cut,
        "lower_z_cut": z_cut,
    }
    return ChinRegion(points=vertices[indices], vertex_indices=indices, metadata=metadata)


def estimate_mount_center(
    mesh: trimesh.Trimesh,
    symmetry_result: SymmetryResult,
    strategy: CenterStrategy = "chin_region",
    config: PlacementConfig = DEFAULT_PLACEMENT_CONFIG,
    override: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, str, ChinRegion]:
    """Estimate or override the mount center on a canonical helmet mesh."""

    _ = symmetry_result
    chin_region = extract_chin_region(mesh, config=config)
    if override is not None:
        return np.asarray(override, dtype=float), "override", chin_region
    if strategy != "chin_region":
        raise ValueError(f"Unsupported mount center strategy: {strategy}")
    center = np.median(chin_region.points, axis=0)
    center[0] = 0.0
    return center, "auto_chin_region", chin_region


def estimate_local_frame(
    mesh: trimesh.Trimesh,
    mount_center: np.ndarray,
    symmetry_result: SymmetryResult,
    patch_radius_mm: float,
) -> tuple[MountFrame, LocalPatch]:
    """Estimate a local mount frame from patch geometry around the center."""

    patch = extract_local_patch(mesh, mount_center, patch_radius_mm)
    x_raw = _unit_vector(np.asarray(symmetry_result.plane_normal, dtype=float))
    if x_raw[0] < 0.0:
        x_raw = -x_raw

    z_axis = _estimate_patch_normal(mesh, patch, mount_center)
    x_axis = x_raw - np.dot(x_raw, z_axis) * z_axis
    if np.linalg.norm(x_axis) <= 1e-9:
        x_axis = _fallback_perpendicular_axis(z_axis)
    x_axis = _unit_vector(x_axis)
    y_axis = _unit_vector(np.cross(z_axis, x_axis))
    x_axis = _unit_vector(np.cross(y_axis, z_axis))

    return (
        MountFrame(
            origin=np.asarray(mount_center, dtype=float),
            x_axis=x_axis,
            y_axis=y_axis,
            z_axis=z_axis,
            source="estimated_local_patch",
        ),
        patch,
    )


def extract_local_patch(
    mesh: trimesh.Trimesh,
    mount_center: np.ndarray,
    patch_radius_mm: float,
) -> LocalPatch:
    """Return vertices within a radius of the mount center."""

    vertices = _vertices(mesh)
    center = np.asarray(mount_center, dtype=float)
    distances = np.linalg.norm(vertices - center, axis=1)
    mask = distances <= patch_radius_mm
    if not np.any(mask):
        keep_count = min(max(8, int(np.ceil(len(vertices) * 0.02))), len(vertices))
        indices = np.argsort(distances)[:keep_count]
    else:
        indices = np.flatnonzero(mask)

    patch_distances = distances[indices]
    metadata = {
        "vertex_count": int(len(indices)),
        "radius_mm": float(patch_radius_mm),
        "max_distance_mm": float(np.max(patch_distances)) if len(indices) else 0.0,
        "mean_distance_mm": float(np.mean(patch_distances)) if len(indices) else 0.0,
    }
    return LocalPatch(
        points=vertices[indices],
        vertex_indices=indices,
        radius_mm=float(patch_radius_mm),
        metadata=metadata,
    )


def _estimate_patch_normal(
    mesh: trimesh.Trimesh,
    patch: LocalPatch,
    mount_center: np.ndarray,
) -> np.ndarray:
    """Estimate and outward-orient a local patch normal."""

    normal = _normal_from_vertex_normals(mesh, patch)
    if normal is None:
        normal = _normal_from_pca(patch.points)
    if normal is None:
        normal = np.asarray(mount_center, dtype=float) - _mesh_center(mesh)

    normal = _unit_vector(normal)
    outward = np.asarray(mount_center, dtype=float) - _mesh_center(mesh)
    outward[0] = 0.0
    if np.linalg.norm(outward) > 1e-9 and np.dot(normal, outward) < 0.0:
        normal = -normal
    return normal


def _normal_from_vertex_normals(
    mesh: trimesh.Trimesh,
    patch: LocalPatch,
) -> Optional[np.ndarray]:
    """Average mesh vertex normals on a patch when available."""

    if len(getattr(mesh, "faces", [])) == 0 or len(patch.vertex_indices) == 0:
        return None
    normals = np.asarray(mesh.vertex_normals, dtype=float)
    if len(normals) == 0:
        return None
    averaged = normals[patch.vertex_indices].mean(axis=0)
    if np.linalg.norm(averaged) <= 1e-9:
        return None
    return averaged


def _normal_from_pca(points: np.ndarray) -> Optional[np.ndarray]:
    """Estimate normal as the least-variance principal direction."""

    if len(points) < 3:
        return None
    centered = points - points.mean(axis=0)
    covariance = centered.T @ centered / max(1, len(points) - 1)
    values, vectors = np.linalg.eigh(covariance)
    normal = vectors[:, int(np.argmin(values))]
    if np.linalg.norm(normal) <= 1e-9:
        return None
    return normal


def _vertices(mesh: trimesh.Trimesh) -> np.ndarray:
    """Return validated mesh vertices as a float array."""

    vertices = np.asarray(mesh.vertices, dtype=float)
    if len(vertices) == 0:
        raise ValueError("Mesh has no vertices for feature extraction.")
    return vertices


def _mesh_center(mesh: trimesh.Trimesh) -> np.ndarray:
    """Return a robust mesh center from vertices."""

    return _vertices(mesh).mean(axis=0)


def _normalized_rank(values: np.ndarray, high: bool) -> np.ndarray:
    """Return normalized rank scores where larger is better."""

    order = np.argsort(values)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.linspace(0.0, 1.0, len(values))
    return ranks if high else 1.0 - ranks


def _fallback_perpendicular_axis(axis: np.ndarray) -> np.ndarray:
    """Choose a stable axis perpendicular to the provided vector."""

    candidates = [
        np.array([1.0, 0.0, 0.0], dtype=float),
        np.array([0.0, 1.0, 0.0], dtype=float),
        np.array([0.0, 0.0, 1.0], dtype=float),
    ]
    best = min(candidates, key=lambda candidate: abs(float(np.dot(candidate, axis))))
    return best - np.dot(best, axis) * axis


def _unit_vector(vector: np.ndarray) -> np.ndarray:
    """Normalize a vector and reject degenerate input."""

    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("Cannot normalize a zero-length vector.")
    return np.asarray(vector, dtype=float) / norm
