"""Saddle mesh generation between a mount frame and local helmet patch."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.spatial import cKDTree
import trimesh

from app.geometry.features import LocalPatch, MountFrame


@dataclass(frozen=True)
class SaddleConfig:
    """Configuration for deterministic saddle generation."""

    contact_offset_mm: float = 0.6
    footprint_width_mm: float = 42.0
    footprint_height_mm: float = 32.0
    saddle_height_mm: float = 8.0
    wall_thickness_mm: float = 3.0
    profile_samples: int = 48
    patch_decimation_limit: int | None = 2000
    smoothing_passes: int = 0
    approved: bool = False
    mount_center_override: list[float] | None = None
    patch_radius_mm: float | None = None
    notes: str = ""


@dataclass(frozen=True)
class SaddleResult:
    """Generated saddle artifacts and metadata."""

    saddle_mesh: trimesh.Trimesh
    final_mesh: trimesh.Trimesh
    debug: dict[str, Any]
    validation: dict[str, Any]
    mesh_stats: dict[str, Any]
    warnings: list[str]


def generate_saddle(
    mount_frame: MountFrame,
    local_patch: LocalPatch,
    config: SaddleConfig,
) -> SaddleResult:
    """Generate a saddle and merged final mount mesh."""

    warnings: list[str] = []
    patch_surface = build_patch_support_surface(mount_frame, local_patch, config, warnings)
    footprint = build_mount_footprint(config)
    saddle_mesh, profile_stats = loft_or_bridge_between_profiles(
        mount_frame=mount_frame,
        top_profile_local=footprint["profile"],
        bottom_profile_local=patch_surface["profile"],
    )
    final_mesh = merge_mount_and_saddle(saddle_mesh, mount_frame, config)
    validation = validate_generated_mesh(final_mesh)
    if not validation["valid"]:
        warnings.extend(validation["warnings"])

    mesh_stats = {
        "saddle": _mesh_stats(saddle_mesh),
        "final": _mesh_stats(final_mesh),
    }
    debug = {
        "config": asdict(config),
        "input_patch_stats": {
            **local_patch.metadata,
            "decimated_point_count": int(len(patch_surface["patch_points_local"])),
        },
        "chosen_mount_frame": _frame_summary(mount_frame),
        "generated_profile_stats": {
            **footprint["metadata"],
            **patch_surface["metadata"],
            **profile_stats,
        },
        "mesh_stats": mesh_stats,
        "validation": validation,
        "warnings": warnings,
        "review": {
            "approved": config.approved,
            "mount_center_override": config.mount_center_override,
            "patch_radius_mm": config.patch_radius_mm,
            "contact_offset_mm": config.contact_offset_mm,
            "footprint_width_mm": config.footprint_width_mm,
            "footprint_height_mm": config.footprint_height_mm,
            "saddle_height_mm": config.saddle_height_mm,
            "notes": config.notes,
        },
    }
    return SaddleResult(
        saddle_mesh=saddle_mesh,
        final_mesh=final_mesh,
        debug=debug,
        validation=validation,
        mesh_stats=mesh_stats,
        warnings=warnings,
    )


def build_mount_footprint(config: SaddleConfig) -> dict[str, Any]:
    """Build a deterministic oval top footprint in mount-frame local space."""

    sample_count = _validated_sample_count(config.profile_samples)
    angles = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    half_width = config.footprint_width_mm * 0.5
    half_height = config.footprint_height_mm * 0.5
    profile = np.column_stack(
        [
            half_width * np.cos(angles),
            half_height * np.sin(angles),
            np.full(sample_count, config.saddle_height_mm, dtype=float),
        ]
    )
    return {
        "profile": profile,
        "metadata": {
            "top_profile_samples": int(sample_count),
            "top_profile_width_mm": float(config.footprint_width_mm),
            "top_profile_height_mm": float(config.footprint_height_mm),
        },
    }


def build_patch_support_surface(
    mount_frame: MountFrame,
    local_patch: LocalPatch,
    config: SaddleConfig,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build bottom support profile by sampling nearest patch heights."""

    patch_points = _decimate_points(local_patch.points, config.patch_decimation_limit)
    if len(patch_points) == 0:
        raise ValueError("Cannot build saddle support surface from an empty patch.")

    patch_local = _world_to_local(patch_points, mount_frame)
    tree = cKDTree(patch_local[:, :2])
    top_profile = build_mount_footprint(config)["profile"]

    # Slightly larger contact boundary gives the saddle a stable lower lip.
    bottom_xy = top_profile[:, :2] * 1.08
    distances, indices = tree.query(bottom_xy, k=1)
    nearest_z = patch_local[indices, 2]
    bottom_z = nearest_z + config.contact_offset_mm
    bottom_profile = np.column_stack([bottom_xy, bottom_z])

    if warnings is not None and len(patch_points) < 8:
        warnings.append("Patch has fewer than 8 points; support profile may be coarse.")

    return {
        "profile": bottom_profile,
        "patch_points_local": patch_local,
        "metadata": {
            "bottom_profile_samples": int(len(bottom_profile)),
            "bottom_profile_min_z_mm": float(np.min(bottom_profile[:, 2])),
            "bottom_profile_max_z_mm": float(np.max(bottom_profile[:, 2])),
            "bottom_profile_mean_nearest_xy_distance_mm": float(np.mean(distances)),
        },
    }


def loft_or_bridge_between_profiles(
    mount_frame: MountFrame,
    top_profile_local: np.ndarray,
    bottom_profile_local: np.ndarray,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Create a capped loft mesh between matching top and bottom profiles."""

    if len(top_profile_local) != len(bottom_profile_local):
        raise ValueError("Top and bottom profiles must have the same sample count.")
    sample_count = len(top_profile_local)
    top_world = _local_to_world(top_profile_local, mount_frame)
    bottom_world = _local_to_world(bottom_profile_local, mount_frame)
    top_center = top_world.mean(axis=0)
    bottom_center = bottom_world.mean(axis=0)

    vertices = np.vstack([bottom_world, top_world, bottom_center, top_center])
    bottom_center_index = sample_count * 2
    top_center_index = sample_count * 2 + 1
    faces: list[list[int]] = []
    for index in range(sample_count):
        next_index = (index + 1) % sample_count
        bottom_a = index
        bottom_b = next_index
        top_a = sample_count + index
        top_b = sample_count + next_index
        faces.append([bottom_a, bottom_b, top_b])
        faces.append([bottom_a, top_b, top_a])
        faces.append([bottom_center_index, bottom_b, bottom_a])
        faces.append([top_center_index, top_a, top_b])

    mesh = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
    mesh.remove_unreferenced_vertices()
    return mesh, {
        "bridge_profile_samples": int(sample_count),
        "saddle_vertex_count": int(len(mesh.vertices)),
        "saddle_face_count": int(len(mesh.faces)),
    }


def merge_mount_and_saddle(
    saddle_mesh: trimesh.Trimesh,
    mount_frame: MountFrame,
    config: SaddleConfig,
) -> trimesh.Trimesh:
    """Merge saddle with a simple top mount plate for V1 final export."""

    plate = _build_mount_plate(mount_frame, config)
    merged = trimesh.util.concatenate([saddle_mesh, plate])
    merged.remove_unreferenced_vertices()
    return merged


def validate_generated_mesh(mesh: trimesh.Trimesh) -> dict[str, Any]:
    """Run basic validation checks for generated saddle/final meshes."""

    warnings: list[str] = []
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if len(vertices) == 0:
        warnings.append("Mesh has no vertices.")
    if len(faces) == 0:
        warnings.append("Mesh has no faces.")
    if len(vertices) > 0 and not np.isfinite(vertices).all():
        warnings.append("Mesh contains NaN or infinite vertex coordinates.")

    is_watertight = bool(mesh.is_watertight) if len(faces) > 0 else False
    if not is_watertight:
        warnings.append("Mesh is not watertight.")
    winding_consistent = bool(mesh.is_winding_consistent) if len(faces) > 0 else False
    if not winding_consistent:
        warnings.append("Mesh winding is not fully consistent.")

    return {
        "valid": len(warnings) == 0,
        "vertex_count": int(len(vertices)),
        "face_count": int(len(faces)),
        "is_watertight": is_watertight,
        "is_winding_consistent": winding_consistent,
        "warnings": warnings,
    }


def _build_mount_plate(
    mount_frame: MountFrame,
    config: SaddleConfig,
) -> trimesh.Trimesh:
    """Build a simple oval top plate representing standard mount geometry."""

    sample_count = _validated_sample_count(config.profile_samples)
    angles = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    half_width = config.footprint_width_mm * 0.5
    half_height = config.footprint_height_mm * 0.5
    bottom_z = config.saddle_height_mm
    top_z = config.saddle_height_mm + max(config.wall_thickness_mm, 0.5)
    bottom = np.column_stack(
        [half_width * np.cos(angles), half_height * np.sin(angles), np.full(sample_count, bottom_z)]
    )
    top = np.column_stack(
        [half_width * np.cos(angles), half_height * np.sin(angles), np.full(sample_count, top_z)]
    )
    mesh, _ = loft_or_bridge_between_profiles(mount_frame, top, bottom)
    return mesh


def _world_to_local(points: np.ndarray, mount_frame: MountFrame) -> np.ndarray:
    """Project world points into mount-frame local coordinates."""

    basis = np.vstack([mount_frame.x_axis, mount_frame.y_axis, mount_frame.z_axis])
    return (np.asarray(points, dtype=float) - mount_frame.origin) @ basis.T


def _local_to_world(points: np.ndarray, mount_frame: MountFrame) -> np.ndarray:
    """Map local mount-frame coordinates back into world coordinates."""

    local = np.asarray(points, dtype=float)
    return (
        mount_frame.origin
        + local[:, 0, np.newaxis] * mount_frame.x_axis
        + local[:, 1, np.newaxis] * mount_frame.y_axis
        + local[:, 2, np.newaxis] * mount_frame.z_axis
    )


def _decimate_points(points: np.ndarray, limit: int | None) -> np.ndarray:
    """Deterministically decimate patch points to a maximum count."""

    points_array = np.asarray(points, dtype=float)
    if limit is None or limit <= 0 or len(points_array) <= limit:
        return points_array
    indices = np.linspace(0, len(points_array) - 1, limit, dtype=int)
    return points_array[indices]


def _validated_sample_count(profile_samples: int) -> int:
    """Clamp profile sample count to a practical minimum."""

    return max(12, int(profile_samples))


def _mesh_stats(mesh: trimesh.Trimesh) -> dict[str, Any]:
    """Return compact mesh statistics."""

    return {
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "is_watertight": bool(mesh.is_watertight) if len(mesh.faces) else False,
        "bounds_min": np.round(mesh.bounds[0], 6).tolist() if len(mesh.vertices) else [],
        "bounds_max": np.round(mesh.bounds[1], 6).tolist() if len(mesh.vertices) else [],
    }


def _frame_summary(mount_frame: MountFrame) -> dict[str, Any]:
    """Return mount frame vectors for debug JSON."""

    return {
        "origin": np.round(mount_frame.origin, 6).tolist(),
        "x_axis": np.round(mount_frame.x_axis, 6).tolist(),
        "y_axis": np.round(mount_frame.y_axis, 6).tolist(),
        "z_axis": np.round(mount_frame.z_axis, 6).tolist(),
        "source": mount_frame.source,
    }
