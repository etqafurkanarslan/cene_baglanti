"""File-based storage for UI selections and reviews."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh

from app.geometry.preprocess import load_mesh
from app.ui.schemas import SavedSelectionModel, UIReviewModel, UIReviewPayload
from app.utils.io import write_json

SELECTION_FILENAME = "surface_selection.json"
UI_REVIEW_FILENAME = "ui_review.json"
EFFECTIVE_REVIEW_FILENAME = "effective_review.json"


def load_selection(case_dir: Path) -> Optional[SavedSelectionModel]:
    """Load a saved selection if present."""

    path = case_dir / SELECTION_FILENAME
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return SavedSelectionModel(**payload)


def save_selection(case_dir: Path, payload: SavedSelectionModel) -> Path:
    """Persist a selection payload."""

    path = case_dir / SELECTION_FILENAME
    write_json(path, payload.model_dump(mode="json"))
    return path


def load_ui_review(case_dir: Path) -> Optional[UIReviewModel]:
    """Load a saved UI review if present."""

    path = case_dir / UI_REVIEW_FILENAME
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload["source_path"] = str(path)
    return UIReviewModel(**payload)


def save_ui_review(case_dir: Path, payload: UIReviewPayload) -> Path:
    """Persist a UI review payload."""

    path = case_dir / UI_REVIEW_FILENAME
    write_json(path, payload.model_dump(mode="json"))
    return path


def build_selection_from_faces(case_dir: Path, included_face_ids: list[int], excluded_face_ids: list[int]) -> SavedSelectionModel:
    """Compute selection geometry from included and excluded faces on the aligned mesh."""

    mesh = load_mesh(case_dir / "aligned_mesh.stl")
    faces = np.asarray(mesh.faces, dtype=int)
    included = sorted({int(face_id) for face_id in included_face_ids if 0 <= int(face_id) < len(faces)})
    excluded = {int(face_id) for face_id in excluded_face_ids if 0 <= int(face_id) < len(faces)}
    active = [face_id for face_id in included if face_id not in excluded]
    if not active:
        return SavedSelectionModel(
            included_face_ids=[],
            excluded_face_ids=sorted(excluded),
            included_vertex_ids=[],
            selection_centroid=None,
            selection_normal=None,
            selected_point_count=0,
        )

    selected_faces = faces[active]
    selected_vertices = np.unique(selected_faces.reshape(-1))
    face_centroids = np.asarray(mesh.triangles_center, dtype=float)[active]
    face_normals = np.asarray(mesh.face_normals, dtype=float)[active]
    centroid = np.mean(face_centroids, axis=0)
    normal = _safe_unit_vector(np.mean(face_normals, axis=0))
    return SavedSelectionModel(
        included_face_ids=active,
        excluded_face_ids=sorted(excluded),
        included_vertex_ids=selected_vertices.astype(int).tolist(),
        selection_centroid=np.round(centroid, 6).tolist(),
        selection_normal=np.round(normal, 6).tolist(),
        selected_point_count=int(len(selected_vertices)),
    )


def build_effective_review_payload(
    case_dir: Path,
    payload: Optional[UIReviewPayload],
    selection_path: Optional[Path],
) -> dict:
    """Merge base review.json with UI review fields for regeneration."""

    base_review_path = case_dir / "review.json"
    base_payload = (
        json.loads(base_review_path.read_text(encoding="utf-8-sig"))
        if base_review_path.exists()
        else {}
    )
    ui_payload = payload.model_dump(mode="json") if payload is not None else {}
    merged = {**base_payload}
    for key, value in ui_payload.items():
        if value is not None:
            merged[key] = value
    if selection_path is not None:
        merged["selection_file"] = str(selection_path)
    return merged


def write_effective_review(case_dir: Path, payload: dict) -> Path:
    """Write the merged review payload used for regeneration."""

    path = case_dir / EFFECTIVE_REVIEW_FILENAME
    write_json(path, payload)
    return path


def copy_ui_inputs_to_output(case_dir: Path, new_output_dir: Path) -> None:
    """Copy UI review artifacts into a regenerated output directory for traceability."""

    for filename in (SELECTION_FILENAME, UI_REVIEW_FILENAME, EFFECTIVE_REVIEW_FILENAME):
        source = case_dir / filename
        if source.exists():
            target = new_output_dir / filename
            target.write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8")


def _safe_unit_vector(vector: np.ndarray) -> np.ndarray:
    """Normalize a vector or fall back to +Z when degenerate."""

    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return np.array([0.0, 0.0, 1.0], dtype=float)
    return np.asarray(vector, dtype=float) / norm

