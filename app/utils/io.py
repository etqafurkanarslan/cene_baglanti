"""Filesystem and serialization helpers."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import trimesh


def create_output_dir(output_root: Path, scan_name: str) -> Path:
    """Create a timestamped output directory for one pipeline run."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_root / f"{scan_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON data with stable indentation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_mesh_as_stl(mesh: trimesh.Trimesh, path: Path) -> Optional[Path]:
    """Export a mesh as STL and return the written path when successful."""

    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)
    return path

