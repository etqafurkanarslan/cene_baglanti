"""Schemas for the local review UI API."""

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SelectionPayload(BaseModel):
    """Incoming surface selection payload."""

    included_face_ids: list[int] = Field(default_factory=list)
    excluded_face_ids: list[int] = Field(default_factory=list)


class SavedSelectionModel(BaseModel):
    """Persisted surface selection summary."""

    included_face_ids: list[int] = Field(default_factory=list)
    excluded_face_ids: list[int] = Field(default_factory=list)
    included_vertex_ids: list[int] = Field(default_factory=list)
    selection_centroid: Optional[list[float]] = None
    selection_normal: Optional[list[float]] = None
    selected_point_count: int = 0


class UIReviewPayload(BaseModel):
    """Incoming human review payload from the UI."""

    approved: bool = False
    mount_center_override: Optional[list[float]] = None
    selection_file: Optional[str] = None
    patch_radius_mm: Optional[float] = None
    contact_offset_mm: Optional[float] = None
    footprint_width_mm: Optional[float] = None
    footprint_height_mm: Optional[float] = None
    saddle_height_mm: Optional[float] = None
    notes: str = ""


class UIReviewModel(UIReviewPayload):
    """Persisted UI review payload."""

    source_path: Optional[Path] = None


class CaseSummaryModel(BaseModel):
    """Top-level case list entry."""

    case_id: str
    output_dir: Path
    scan_name: str
    mount_id: str
    updated_at: str
    status: str
    reviewed: bool


class CaseDetailModel(BaseModel):
    """Detailed case payload for the review UI."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    case_id: str
    output_dir: Path
    result: dict[str, Any]
    selection: Optional[SavedSelectionModel]
    ui_review: Optional[UIReviewModel]
    artifact_urls: dict[str, str]


class RegenerateResponseModel(BaseModel):
    """Summary of one regeneration action."""

    previous_case_id: str
    new_case_id: str
    previous_mount_center: Optional[list[float]]
    new_mount_center: Optional[list[float]]
    previous_diagnostics: dict[str, Any]
    new_diagnostics: dict[str, Any]
    generated_files: dict[str, str]

