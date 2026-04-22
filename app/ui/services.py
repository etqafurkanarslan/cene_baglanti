"""Case discovery and serialization helpers for the local review UI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import DEFAULT_OUTPUT_ROOT
from app.ui.schemas import CaseDetailModel, CaseSummaryModel
from app.ui.selection_store import load_placement, load_selection, load_ui_review


@dataclass(frozen=True)
class ProcessedCase:
    """Resolved processed case on disk."""

    case_id: str
    output_dir: Path
    result_path: Path


def discover_cases(output_root: Path = DEFAULT_OUTPUT_ROOT) -> list[ProcessedCase]:
    """Discover processed cases under the output root."""

    if not output_root.exists():
        return []
    cases: list[ProcessedCase] = []
    for result_path in sorted(output_root.glob("**/result.json"), reverse=True):
        output_dir = result_path.parent
        cases.append(
            ProcessedCase(
                case_id=output_dir.name,
                output_dir=output_dir,
                result_path=result_path,
            )
        )
    unique: dict[str, ProcessedCase] = {}
    for case in cases:
        unique.setdefault(case.case_id, case)
    return list(unique.values())


def get_case(case_id: str, output_root: Path = DEFAULT_OUTPUT_ROOT) -> ProcessedCase:
    """Resolve one processed case by id."""

    for case in discover_cases(output_root):
        if case.case_id == case_id:
            return case
    raise FileNotFoundError(f"Case not found: {case_id}")


def load_result(case: ProcessedCase) -> dict:
    """Load raw result.json for a case."""

    return json.loads(case.result_path.read_text(encoding="utf-8-sig"))


def list_case_summaries(output_root: Path = DEFAULT_OUTPUT_ROOT) -> list[CaseSummaryModel]:
    """Build a compact case listing payload."""

    summaries: list[CaseSummaryModel] = []
    for case in discover_cases(output_root):
        result = load_result(case)
        summaries.append(
            CaseSummaryModel(
                case_id=case.case_id,
                output_dir=case.output_dir,
                scan_name=str(result["scan"]["name"]),
                mount_id=str(result["mount"]["mount_id"]),
                updated_at=str(result["finished_at"]),
                status=str(result["status"]),
                reviewed=bool(result.get("review", {}).get("approved", False)),
            )
        )
    return summaries


def build_case_detail(case: ProcessedCase) -> CaseDetailModel:
    """Build detailed case payload for the UI."""

    result = load_result(case)
    selection = load_selection(case.output_dir)
    placement = load_placement(case.output_dir)
    ui_review = load_ui_review(case.output_dir)
    artifact_urls = {
        "mesh": f"/api/cases/{case.case_id}/mesh",
        "mount_asset_mesh": f"/api/cases/{case.case_id}/mount-asset-mesh",
        "result": f"/api/cases/{case.case_id}/artifacts/result.json",
        "mount_frame": f"/api/cases/{case.case_id}/artifacts/mount_frame.json",
        "chin_patch": f"/api/cases/{case.case_id}/artifacts/chin_patch_points.json",
        "saddle_debug": f"/api/cases/{case.case_id}/artifacts/saddle_debug.json",
        "placement_debug_top": f"/api/cases/{case.case_id}/artifacts/placement_debug_top.png",
        "placement_debug_perspective": f"/api/cases/{case.case_id}/artifacts/placement_debug_perspective.png",
        "placement_anchor_plot": f"/api/cases/{case.case_id}/artifacts/placement_anchor_plot.png",
    }
    return CaseDetailModel(
        case_id=case.case_id,
        output_dir=case.output_dir,
        result=result,
        placement=placement,
        selection=selection,
        ui_review=ui_review,
        artifact_urls=artifact_urls,
    )


def resolve_artifact_path(case: ProcessedCase, artifact_name: str) -> Path:
    """Resolve one case artifact path safely."""

    safe_name = Path(artifact_name).name
    candidate = case.output_dir / safe_name
    if not candidate.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_name}")
    return candidate


def maybe_find_previous_review(case: ProcessedCase) -> Optional[Path]:
    """Return a legacy review.json path when present."""

    candidate = case.output_dir / "review.json"
    return candidate if candidate.exists() else None
