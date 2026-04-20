"""Mesh loading and preprocessing helpers."""

from pathlib import Path

import numpy as np
import trimesh

from app.models.helmet_scan import MeshInfo


def load_mesh(scan_path: Path) -> trimesh.Trimesh:
    """Load a mesh file and normalize scene inputs into a single mesh."""

    loaded = trimesh.load(scan_path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        mesh = trimesh.util.concatenate(
            [geometry for geometry in loaded.geometry.values()]
        )
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise ValueError(f"Unsupported mesh type loaded from {scan_path}: {type(loaded)!r}")

    if mesh.vertices.size == 0:
        raise ValueError(f"Mesh has no vertices: {scan_path}")

    return mesh


def summarize_mesh(mesh: trimesh.Trimesh) -> MeshInfo:
    """Return basic mesh statistics for logging and result serialization."""

    bounds = np.asarray(mesh.bounds, dtype=float)
    extents = np.asarray(mesh.extents, dtype=float)
    return MeshInfo(
        vertex_count=int(len(mesh.vertices)),
        face_count=int(len(mesh.faces)),
        bounds_min=bounds[0].round(6).tolist(),
        bounds_max=bounds[1].round(6).tolist(),
        extents=extents.round(6).tolist(),
        is_watertight=bool(mesh.is_watertight),
        source_format=getattr(mesh, "metadata", {}).get("file_type"),
    )

