"""Regeneration flow for UI-driven overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from app.pipeline import process_scan
from app.ui.schemas import RegenerateResponseModel, UIReviewPayload
from app.ui.selection_store import (
    build_effective_review_payload,
    copy_ui_inputs_to_output,
    load_selection,
    load_ui_review,
    write_effective_review,
)
from app.ui.services import ProcessedCase, load_result


def regenerate_case(case: ProcessedCase) -> RegenerateResponseModel:
    """Run the pipeline again using saved UI inputs."""

    result = load_result(case)
    selection = load_selection(case.output_dir)
    ui_review = load_ui_review(case.output_dir)

    mount_center_override = _resolve_mount_center_override(selection, ui_review)
    effective_review = build_effective_review_payload(
        case.output_dir,
        UIReviewPayload(**ui_review.model_dump(exclude={"source_path"})) if ui_review is not None else None,
        selection_path=(case.output_dir / "surface_selection.json") if selection is not None else None,
    )
    effective_review_path = write_effective_review(case.output_dir, effective_review)

    regenerated = process_scan(
        scan_path=Path(result["scan"]["path"]),
        mount_id=str(result["mount"]["mount_id"]),
        output_root=case.output_dir.parent,
        mount_center_override=mount_center_override,
        review_path=effective_review_path,
        patch_radius_override=_optional_float(effective_review.get("patch_radius_mm")),
        contact_offset_override=_optional_float(effective_review.get("contact_offset_mm")),
        footprint_width_override=_optional_float(effective_review.get("footprint_width_mm")),
        footprint_height_override=_optional_float(effective_review.get("footprint_height_mm")),
        saddle_height_override=_optional_float(effective_review.get("saddle_height_mm")),
        mount_asset_path=Path(result["mount_asset"]["source"])
        if result.get("mount_asset", {}).get("type") == "real"
        else None,
        mount_asset_origin_mode=str(result.get("mount_asset", {}).get("origin_mode", "mount-local")),
    )
    copy_ui_inputs_to_output(case.output_dir, regenerated.output_dir)

    previous_mount_center = result.get("mount_frame", {}).get("origin")
    new_mount_center = regenerated.mount_frame.origin
    return RegenerateResponseModel(
        previous_case_id=case.case_id,
        new_case_id=regenerated.output_dir.name,
        previous_mount_center=previous_mount_center,
        new_mount_center=new_mount_center,
        previous_diagnostics=result.get("diagnostics", {}),
        new_diagnostics=regenerated.diagnostics,
        generated_files={
            "result_json": str(regenerated.result_json_path),
            "saddle_preview": str(regenerated.saddle.preview_path),
            "final_mount": str(regenerated.saddle.final_mount_path),
            "output_dir": str(regenerated.output_dir),
        },
    )


def _resolve_mount_center_override(
    selection,
    ui_review,
) -> Optional[np.ndarray]:
    """Apply precedence: surface selection > manual UI mount center > none."""

    if selection is not None and selection.selection_centroid is not None and selection.selected_point_count > 0:
        return np.asarray(selection.selection_centroid, dtype=float)
    if ui_review is not None and ui_review.mount_center_override is not None:
        return np.asarray(ui_review.mount_center_override, dtype=float)
    return None


def _optional_float(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)
