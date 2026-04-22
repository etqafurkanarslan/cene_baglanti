"""Tests for review overrides, diagnostics, and mount asset fallback."""

import json
from pathlib import Path

import numpy as np
import trimesh

from app.pipeline import process_scan


def test_review_json_overrides_are_applied() -> None:
    """Review JSON should feed placement and saddle config when CLI is quiet."""

    work_dir = _work_dir("review_overrides")
    scan_path = _write_box_scan(work_dir)
    review_path = work_dir / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "approved": True,
                "mount_center_override": [0.0, 1.0, -2.0],
                "patch_radius_mm": 5.0,
                "contact_offset_mm": 1.1,
                "footprint_width_mm": 24.0,
                "footprint_height_mm": 18.0,
                "saddle_height_mm": 4.0,
                "notes": "review accepted",
            }
        ),
        encoding="utf-8",
    )

    result = process_scan(
        scan_path=scan_path,
        mount_id="gopro_low_profile_v1",
        output_root=work_dir / "runs",
        review_path=review_path,
    )

    assert result.review.approved is True
    assert result.review.override_source == "review"
    assert result.review.notes == "review accepted"
    assert result.mount_frame.origin == [0.0, 1.0, -2.0]
    assert result.mount_patch_radius_mm == 5.0
    assert result.saddle.contact_offset_mm == 1.1
    assert result.saddle.footprint_width_mm == 24.0
    assert result.saddle.saddle_height_mm == 4.0


def test_cli_overrides_review_json() -> None:
    """Explicit process arguments should take precedence over review JSON."""

    work_dir = _work_dir("cli_precedence")
    scan_path = _write_box_scan(work_dir)
    review_path = work_dir / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "mount_center_override": [0.0, 1.0, -2.0],
                "footprint_width_mm": 12.0,
                "contact_offset_mm": 0.2,
            }
        ),
        encoding="utf-8",
    )

    result = process_scan(
        scan_path=scan_path,
        mount_id="gopro_low_profile_v1",
        output_root=work_dir / "runs",
        review_path=review_path,
        mount_center_override=np.array([0.0, 3.0, -1.0], dtype=float),
        footprint_width_override=30.0,
    )

    assert result.review.override_source == "cli"
    assert result.review.applied_fields["mount_center_override"] == "cli"
    assert result.review.applied_fields["footprint_width_mm"] == "cli"
    assert result.review.applied_fields["contact_offset_mm"] == "review"
    assert result.mount_frame.origin == [0.0, 3.0, -1.0]
    assert result.saddle.footprint_width_mm == 30.0
    assert result.saddle.contact_offset_mm == 0.2


def test_diagnostics_and_real_mount_asset_are_written() -> None:
    """M5 outputs should include diagnostics and real mount asset metadata."""

    work_dir = _work_dir("diagnostics_asset")
    scan_path = _write_box_scan(work_dir)
    asset_path = work_dir / "future_mount_asset.stl"
    trimesh.creation.box(extents=(1, 1, 1)).export(asset_path)

    result = process_scan(
        scan_path=scan_path,
        mount_id="gopro_low_profile_v1",
        output_root=work_dir / "runs",
        mount_asset_path=asset_path,
    )
    debug = json.loads(result.saddle.debug_path.read_text(encoding="utf-8"))

    assert result.diagnostics["contact_point_count"] > 0
    assert result.diagnostics["mean_gap_mm"] is not None
    assert "p90_gap_mm" in result.diagnostics
    assert result.mount_asset.type == "real"
    assert result.mount_asset.source == str(asset_path)
    assert result.mount_asset.loaded_successfully is True
    assert result.mount_asset.vertex_count > 0
    assert result.mount_asset.face_count > 0
    assert result.mount_asset.warning is None
    assert debug["diagnostics"]["contact_point_count"] == result.diagnostics["contact_point_count"]
    assert debug["mount_asset"]["type"] == "real"
    assert debug["generated_profile_stats"]["contact_fit_method"] == "weighted_rbf"
    for name in (
        "mount_center_debug.json",
        "patch_bounds_debug.json",
        "frame_debug.json",
        "placement_debug_top.png",
        "placement_debug_perspective.png",
    ):
        assert (result.output_dir / name).exists()


def test_missing_mount_asset_falls_back_to_placeholder() -> None:
    """Missing real assets should not break the pipeline."""

    work_dir = _work_dir("missing_asset")
    scan_path = _write_box_scan(work_dir)
    missing_path = work_dir / "missing_asset.stl"

    result = process_scan(
        scan_path=scan_path,
        mount_id="gopro_low_profile_v1",
        output_root=work_dir / "runs",
        mount_asset_path=missing_path,
    )

    assert result.mount_asset.type == "placeholder"
    assert result.mount_asset.loaded_successfully is False
    assert result.mount_asset.warning is not None
    assert result.saddle.validation["shell_count"] >= 1


def _write_box_scan(tmp_path: Path) -> Path:
    scan_path = tmp_path / "sample_box.stl"
    trimesh.creation.box(extents=(10.0, 8.0, 6.0)).export(scan_path)
    return scan_path


def _work_dir(name: str) -> Path:
    path = Path("outputs") / "test_m4" / name
    path.mkdir(parents=True, exist_ok=True)
    return path
