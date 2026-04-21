"""File-based review overrides for processing runs."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class ReviewData:
    """Parsed review JSON fields."""

    approved: bool = False
    mount_center_override: list[float] | None = None
    patch_radius_mm: float | None = None
    contact_offset_mm: float | None = None
    footprint_width_mm: float | None = None
    footprint_height_mm: float | None = None
    saddle_height_mm: float | None = None
    notes: str = ""
    source_path: Path | None = None


@dataclass(frozen=True)
class ReviewResolution:
    """Resolved review and override source metadata."""

    data: ReviewData
    override_source: str
    applied_fields: dict[str, str]


def load_review(path: Optional[Path]) -> ReviewData:
    """Load review JSON, returning defaults when no path is provided."""

    if path is None:
        return ReviewData()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return ReviewData(
        approved=bool(payload.get("approved", False)),
        mount_center_override=_coerce_center(payload.get("mount_center_override")),
        patch_radius_mm=_optional_float(payload.get("patch_radius_mm")),
        contact_offset_mm=_optional_float(payload.get("contact_offset_mm")),
        footprint_width_mm=_optional_float(payload.get("footprint_width_mm")),
        footprint_height_mm=_optional_float(payload.get("footprint_height_mm")),
        saddle_height_mm=_optional_float(payload.get("saddle_height_mm")),
        notes=str(payload.get("notes", "")),
        source_path=path.resolve(),
    )


def resolve_review(
    review: ReviewData,
    cli_values: dict[str, Any],
) -> ReviewResolution:
    """Resolve CLI > review.json > defaults precedence for override fields."""

    applied_fields: dict[str, str] = {}
    for field_name in (
        "mount_center_override",
        "patch_radius_mm",
        "contact_offset_mm",
        "footprint_width_mm",
        "footprint_height_mm",
        "saddle_height_mm",
    ):
        if cli_values.get(field_name) is not None:
            applied_fields[field_name] = "cli"
        elif getattr(review, field_name) is not None:
            applied_fields[field_name] = "review"
        else:
            applied_fields[field_name] = "default"

    source_values = set(applied_fields.values())
    if "cli" in source_values:
        override_source = "cli"
    elif "review" in source_values:
        override_source = "review"
    else:
        override_source = "default"

    return ReviewResolution(
        data=review,
        override_source=override_source,
        applied_fields=applied_fields,
    )


def center_to_array(center: list[float] | None) -> Optional[np.ndarray]:
    """Convert a review center list to a numpy vector."""

    if center is None:
        return None
    return np.asarray(center, dtype=float)


def _coerce_center(value: Any) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise ValueError("mount_center_override must be a 3-value array.")
    return [float(value[0]), float(value[1]), float(value[2])]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
