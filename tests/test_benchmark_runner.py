"""Tests for benchmark manifest parsing and summary report generation."""

import json
from pathlib import Path

import trimesh

from app.benchmark import load_benchmark_cases, run_benchmark


def test_benchmark_manifest_parses() -> None:
    """Benchmark cases should load from manifest directories."""

    root = _build_cases_root("parse")

    cases = load_benchmark_cases(root)

    assert len(cases) == 1
    assert cases[0].case_id == "case_parse"
    assert cases[0].reference_review_path is not None


def test_benchmark_outputs_json_csv_and_markdown() -> None:
    """Benchmark runner should emit summary JSON, CSV, and markdown files."""

    root = _build_cases_root("summary")
    report_dir = run_benchmark(root, Path("outputs") / "test_benchmark" / "reports")

    assert (report_dir / "benchmark_summary.json").exists()
    assert (report_dir / "benchmark_summary.csv").exists()
    assert (report_dir / "benchmark_report.md").exists()

    summary = json.loads((report_dir / "benchmark_summary.json").read_text(encoding="utf-8"))
    run_types = {record["run_type"] for record in summary["records"]}
    assert "auto" in run_types
    assert "reference" in run_types


def test_reference_and_auto_runs_are_distinguished() -> None:
    """Auto and reference runs should carry separate center deltas."""

    root = _build_cases_root("distinguish")
    report_dir = run_benchmark(root, Path("outputs") / "test_benchmark" / "reports")
    summary = json.loads((report_dir / "benchmark_summary.json").read_text(encoding="utf-8"))
    auto_record = next(record for record in summary["records"] if record["run_type"] == "auto")
    reference_record = next(record for record in summary["records"] if record["run_type"] == "reference")

    assert auto_record["run_type"] == "auto"
    assert reference_record["run_type"] == "reference"
    assert reference_record["reference_center_distance_mm"] == 0.0
    assert auto_record["reference_center_distance_mm"] is not None


def _build_cases_root(name: str) -> Path:
    root = Path("outputs") / "test_benchmark" / name / "cases"
    case_dir = root / "case_parse"
    case_dir.mkdir(parents=True, exist_ok=True)
    scan_path = case_dir / "sample_box.stl"
    trimesh.creation.box(extents=(10.0, 8.0, 6.0)).export(scan_path)
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "case_id": "case_parse",
                "input_scan_path": "sample_box.stl",
                "enabled": True,
                "notes": "test case",
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "review.reference.json").write_text(
        json.dumps(
            {
                "approved": True,
                "mount_center_override": [0.0, 1.0, -2.0],
                "notes": "reference",
            }
        ),
        encoding="utf-8",
    )
    return root
