"""Feature extraction for mount placement on canonical helmet meshes."""

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
import trimesh

from app.config import DEFAULT_PLACEMENT_CONFIG, PlacementConfig
from app.geometry.symmetry import SymmetryResult

CenterStrategy = Literal["chin_region"]
FRONTIER_PERCENTILE = 88.0
FRONT_BIAS_WEIGHT = 0.60
LOW_BIAS_WEIGHT = 0.25
CENTERLINE_BIAS_WEIGHT = 0.15
ANCHOR_FRONT_BIAS_WEIGHT = 0.45
ANCHOR_CENTERLINE_WEIGHT = 0.25
ANCHOR_NOT_TOO_LOW_WEIGHT = 0.20
ANCHOR_SUPPORT_DENSITY_WEIGHT = 0.10
ANCHOR_TOPK_LIMIT = 16


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
    metadata: dict[str, float | int | str] | None = None


@dataclass(frozen=True)
class MountCenterEstimate:
    """Estimated mount center plus heuristic diagnostics."""

    center: np.ndarray
    source: str
    chin_region: ChinRegion
    metadata: dict[str, float | int | str | list[float]]
    anchor_point: np.ndarray
    anchor_source: str
    anchor_score: float
    legacy_center: np.ndarray
    centerline_band_points: np.ndarray
    frontier_band_points: np.ndarray
    top_anchor_candidates: np.ndarray


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
) -> MountCenterEstimate:
    """Estimate or override the mount center on a canonical helmet mesh."""

    _ = symmetry_result
    chin_region = extract_chin_region(mesh, config=config)
    legacy_center, legacy_metadata = _compute_legacy_mount_center(chin_region.points, config.center_band_mm)
    anchor = _compute_chin_anchor(chin_region.points, config.center_band_mm)
    if override is not None:
        center = np.asarray(override, dtype=float)
        return MountCenterEstimate(
            center=center,
            source="override",
            chin_region=chin_region,
            metadata={
                "candidate_count": int(len(chin_region.points)),
                "centerline_band_count": int(len(anchor["centerline_band_points"])),
                "frontier_candidate_count": int(len(anchor["frontier_points"])),
                "top_candidate_count": int(len(anchor["top_candidates"])),
                "selected_mount_center_world": np.round(center, 6).tolist(),
                "selected_mount_center_local": [0.0, 0.0, 0.0],
                "selection_method": "manual_override",
                "legacy_mount_center": np.round(legacy_center, 6).tolist(),
                "chin_anchor_point": np.round(anchor["anchor_point"], 6).tolist(),
                "chin_anchor_score": float(anchor["anchor_score"]),
                "chin_anchor_source": "auto_chin_anchor",
                "anchor_delta_mm": float(np.linalg.norm(anchor["anchor_point"] - legacy_center)),
                "frontier_percentile": FRONTIER_PERCENTILE,
                "front_bias_weight": ANCHOR_FRONT_BIAS_WEIGHT,
                "low_bias_weight": ANCHOR_NOT_TOO_LOW_WEIGHT,
                "centerline_bias_weight": ANCHOR_CENTERLINE_WEIGHT,
                "support_density_weight": ANCHOR_SUPPORT_DENSITY_WEIGHT,
                "legacy_selection_method": legacy_metadata["selection_method"],
            },
            anchor_point=center,
            anchor_source="manual_override",
            anchor_score=float(anchor["anchor_score"]),
            legacy_center=legacy_center,
            centerline_band_points=anchor["centerline_band_points"],
            frontier_band_points=anchor["frontier_points"],
            top_anchor_candidates=anchor["top_candidates"],
        )
    if strategy != "chin_region":
        raise ValueError(f"Unsupported mount center strategy: {strategy}")

    center = np.asarray(anchor["anchor_point"], dtype=float)
    return MountCenterEstimate(
        center=center,
        source="auto_chin_anchor",
        chin_region=chin_region,
        metadata={
            "candidate_count": int(len(chin_region.points)),
            "centerline_band_count": int(len(anchor["centerline_band_points"])),
            "frontier_candidate_count": int(len(anchor["frontier_points"])),
            "top_candidate_count": int(len(anchor["top_candidates"])),
            "selected_mount_center_world": np.round(center, 6).tolist(),
            "selected_mount_center_local": [0.0, 0.0, 0.0],
            "selection_method": "chin_anchor_frontier_centerline_density_top_mean",
            "legacy_selection_method": legacy_metadata["selection_method"],
            "legacy_mount_center": np.round(legacy_center, 6).tolist(),
            "chin_anchor_point": np.round(anchor["anchor_point"], 6).tolist(),
            "chin_anchor_score": float(anchor["anchor_score"]),
            "chin_anchor_source": "auto_chin_anchor",
            "anchor_delta_mm": float(np.linalg.norm(anchor["anchor_point"] - legacy_center)),
            "frontier_percentile": FRONTIER_PERCENTILE,
            "frontier_y_threshold": float(anchor["frontier_threshold"]),
            "front_bias_weight": ANCHOR_FRONT_BIAS_WEIGHT,
            "low_bias_weight": ANCHOR_NOT_TOO_LOW_WEIGHT,
            "centerline_bias_weight": ANCHOR_CENTERLINE_WEIGHT,
            "support_density_weight": ANCHOR_SUPPORT_DENSITY_WEIGHT,
            "score_min": float(anchor["score_min"]),
            "score_max": float(anchor["score_max"]),
            "score_mean": float(anchor["score_mean"]),
            "top_candidates_centroid": np.round(np.mean(anchor["top_candidates"], axis=0), 6).tolist(),
            "top_candidates": np.round(anchor["top_candidates"], 6).tolist(),
        },
        anchor_point=np.asarray(anchor["anchor_point"], dtype=float),
        anchor_source="auto_chin_anchor",
        anchor_score=float(anchor["anchor_score"]),
        legacy_center=legacy_center,
        centerline_band_points=anchor["centerline_band_points"],
        frontier_band_points=anchor["frontier_points"],
        top_anchor_candidates=anchor["top_candidates"],
    )


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

    z_axis, z_axis_outward_score = _estimate_patch_normal(mesh, patch, mount_center)
    x_axis = x_raw - np.dot(x_raw, z_axis) * z_axis
    if np.linalg.norm(x_axis) <= 1e-9:
        x_axis = _fallback_perpendicular_axis(z_axis)
    x_axis = _unit_vector(x_axis)
    y_axis = _unit_vector(np.cross(z_axis, x_axis))
    x_axis = _unit_vector(np.cross(y_axis, z_axis))
    determinant = float(np.linalg.det(np.column_stack([x_axis, y_axis, z_axis])))

    return (
        MountFrame(
            origin=np.asarray(mount_center, dtype=float),
            x_axis=x_axis,
            y_axis=y_axis,
            z_axis=z_axis,
            source="estimated_local_patch",
            metadata={
                "determinant": determinant,
                "handedness": "right_handed" if determinant > 0 else "left_handed",
                "z_axis_outward_score": float(z_axis_outward_score),
            },
        ),
        patch,
    )


def estimate_mount_frame_from_placement(
    mesh: trimesh.Trimesh,
    contact_center: np.ndarray,
    symmetry_result: SymmetryResult,
    patch_radius_mm: float,
    rotation_euler_deg: np.ndarray | None = None,
    mount_offset_mm: float = 0.0,
) -> tuple[MountFrame, LocalPatch]:
    """Estimate a mount frame from a user-placed contact center and local rotations."""

    base_frame, patch = estimate_local_frame(
        mesh=mesh,
        mount_center=np.asarray(contact_center, dtype=float),
        symmetry_result=symmetry_result,
        patch_radius_mm=patch_radius_mm,
    )
    euler = np.asarray(rotation_euler_deg if rotation_euler_deg is not None else [0.0, 0.0, 0.0], dtype=float)
    basis = np.column_stack([base_frame.x_axis, base_frame.y_axis, base_frame.z_axis])
    rotation_matrix = Rotation.from_euler("xyz", euler, degrees=True).as_matrix()
    rotated_basis = basis @ rotation_matrix
    x_axis = _unit_vector(rotated_basis[:, 0])
    y_axis = _unit_vector(rotated_basis[:, 1])
    z_axis = _unit_vector(rotated_basis[:, 2])
    origin = np.asarray(contact_center, dtype=float) + z_axis * float(mount_offset_mm)
    determinant = float(np.linalg.det(np.column_stack([x_axis, y_axis, z_axis])))
    return (
        MountFrame(
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
            z_axis=z_axis,
            source="ui_placement",
            metadata={
                "determinant": determinant,
                "handedness": "right_handed" if determinant > 0 else "left_handed",
                "z_axis_outward_score": float(base_frame.metadata.get("z_axis_outward_score", 0.0))
                if base_frame.metadata
                else 0.0,
                "contact_center": np.round(np.asarray(contact_center, dtype=float), 6).tolist(),
                "mount_rotation_euler_deg": np.round(euler, 6).tolist(),
                "mount_offset_mm": float(mount_offset_mm),
            },
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
) -> tuple[np.ndarray, float]:
    """Estimate and outward-orient a local patch normal."""

    normal = _normal_from_vertex_normals(mesh, patch)
    if normal is None:
        normal = _normal_from_pca(patch.points)
    if normal is None:
        normal = np.asarray(mount_center, dtype=float) - _mesh_center(mesh)

    normal = _unit_vector(normal)
    outward = np.asarray(mount_center, dtype=float) - _mesh_center(mesh)
    outward[0] = 0.0
    outward_score = float(np.dot(normal, outward))
    if np.linalg.norm(outward) > 1e-9 and outward_score < 0.0:
        normal = -normal
        outward_score = -outward_score
    return normal, outward_score


def _score_mount_center_candidates(points: np.ndarray, center_band_mm: float) -> np.ndarray:
    """Score candidate chin points with front, low, and centered bias."""

    x = np.abs(points[:, 0])
    y = points[:, 1]
    z = points[:, 2]
    x_score = 1.0 - _normalize_vector(x)
    y_score = _normalize_vector(y)
    z_score = 1.0 - _normalize_vector(z)
    center_bias = np.exp(-np.square(x / max(center_band_mm, 1.0)))
    return (
        FRONT_BIAS_WEIGHT * y_score
        + LOW_BIAS_WEIGHT * z_score
        + CENTERLINE_BIAS_WEIGHT * np.maximum(x_score, center_bias)
    )


def _compute_legacy_mount_center(
    points: np.ndarray,
    center_band_mm: float,
) -> tuple[np.ndarray, dict[str, float | int | str]]:
    """Preserve the previous center heuristic for comparison/debugging."""

    frontier_threshold = float(np.percentile(points[:, 1], FRONTIER_PERCENTILE))
    frontier_mask = points[:, 1] >= frontier_threshold
    frontier_points = points[frontier_mask]
    if len(frontier_points) == 0:
        frontier_points = points
    candidate_scores = _score_mount_center_candidates(frontier_points, center_band_mm)
    top_count = max(1, min(24, int(np.ceil(len(frontier_points) * 0.05))))
    ranked_indices = np.argsort(candidate_scores)[::-1]
    top_points = frontier_points[ranked_indices[:top_count]]
    center = np.mean(top_points, axis=0)
    center[0] = 0.0
    return center, {
        "selection_method": "frontier_first_centerline_weighted_top_mean",
        "frontier_candidate_count": int(len(frontier_points)),
        "top_candidate_count": int(top_count),
        "frontier_y_threshold": frontier_threshold,
        "score_min": float(np.min(candidate_scores)),
        "score_max": float(np.max(candidate_scores)),
        "score_mean": float(np.mean(candidate_scores)),
    }


def _compute_chin_anchor(points: np.ndarray, center_band_mm: float) -> dict[str, np.ndarray | float]:
    """Select a chin anchor at the front-center supportable region."""

    centerline_mask = np.abs(points[:, 0]) <= center_band_mm
    centerline_points = points[centerline_mask]
    if len(centerline_points) == 0:
        relaxed_band = max(center_band_mm * 1.5, center_band_mm + 1.0)
        centerline_mask = np.abs(points[:, 0]) <= relaxed_band
        centerline_points = points[centerline_mask]
    if len(centerline_points) == 0:
        centerline_points = points

    frontier_threshold = float(np.percentile(centerline_points[:, 1], FRONTIER_PERCENTILE))
    frontier_mask = centerline_points[:, 1] >= frontier_threshold
    frontier_points = centerline_points[frontier_mask]
    if len(frontier_points) == 0:
        frontier_points = centerline_points

    scores = _score_anchor_candidates(frontier_points, center_band_mm)
    top_count = max(1, min(ANCHOR_TOPK_LIMIT, int(np.ceil(len(frontier_points) * 0.08))))
    ranked_indices = np.argsort(scores)[::-1]
    top_points = frontier_points[ranked_indices[:top_count]]
    anchor_point = np.mean(top_points, axis=0)
    anchor_point[0] = 0.0
    return {
        "anchor_point": anchor_point,
        "anchor_score": float(np.mean(scores[ranked_indices[:top_count]])),
        "centerline_band_points": centerline_points,
        "frontier_points": frontier_points,
        "top_candidates": top_points,
        "frontier_threshold": frontier_threshold,
        "score_min": float(np.min(scores)),
        "score_max": float(np.max(scores)),
        "score_mean": float(np.mean(scores)),
    }


def _score_anchor_candidates(points: np.ndarray, center_band_mm: float) -> np.ndarray:
    """Score anchor candidates with front, centerline, height, and support density bias."""

    x = np.abs(points[:, 0])
    y = points[:, 1]
    z = points[:, 2]
    centerline_bias = np.exp(-np.square(x / max(center_band_mm, 1.0)))
    front_score = _normalize_vector(y)
    not_too_low_score = _normalize_vector(z)
    density_score = _local_density_score(points)
    return (
        ANCHOR_FRONT_BIAS_WEIGHT * front_score
        + ANCHOR_CENTERLINE_WEIGHT * centerline_bias
        + ANCHOR_NOT_TOO_LOW_WEIGHT * not_too_low_score
        + ANCHOR_SUPPORT_DENSITY_WEIGHT * density_score
    )


def _local_density_score(points: np.ndarray) -> np.ndarray:
    """Estimate local support suitability from neighborhood density."""

    if len(points) <= 1:
        return np.ones(len(points), dtype=float)
    radius = max(4.0, min(8.0, float(np.ptp(points[:, 1]) * 0.15)))
    tree = cKDTree(points)
    counts = np.array([len(tree.query_ball_point(point, radius)) for point in points], dtype=float)
    return _normalize_vector(counts)


def _normalize_vector(values: np.ndarray) -> np.ndarray:
    """Normalize vector into [0, 1] with constant-array handling."""

    min_value = float(np.min(values))
    max_value = float(np.max(values))
    if max_value - min_value <= 1e-12:
        return np.ones_like(values, dtype=float)
    return (values - min_value) / (max_value - min_value)


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
