"""Benchmark runner for comparing auto vs reference placement on helmet scans."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import typer

from app.pipeline import process_scan

app = typer.Typer(help="Run benchmark cases for placement evaluation.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Benchmark command group."""


@dataclass(frozen=True)
class BenchmarkCase:
    """One benchmark case manifest."""

    case_id: str
    input_scan_path: Path
    mount_asset_path: Optional[Path]
    notes: str
    enabled: bool
    case_dir: Path
    reference_review_path: Optional[Path]


@app.command("run")
def run_command(
    cases_root: Path = typer.Option(
        Path("benchmark/cases"),
        "--cases-root",
        help="Directory containing benchmark case folders.",
    ),
    reports_root: Path = typer.Option(
        Path("benchmark/reports"),
        "--reports-root",
        help="Directory where benchmark reports will be written.",
    ),
) -> None:
    """Run all enabled benchmark cases and write summary reports."""

    run_benchmark(cases_root=cases_root, reports_root=reports_root)


def run_benchmark(cases_root: Path, reports_root: Path) -> Path:
    """Execute enabled benchmark cases and write report artifacts."""

    cases = load_benchmark_cases(cases_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = _create_report_dir(reports_root, timestamp)

    records: list[dict[str, Any]] = []
    for case in cases:
        if not case.enabled:
            records.append(_disabled_record(case))
            continue
        if not case.input_scan_path.exists():
            records.append(_missing_record(case, "input_scan_missing"))
            continue

        reference_center = load_reference_center(case.reference_review_path)
        output_root = report_dir / case.case_id
        output_root.mkdir(parents=True, exist_ok=True)

        auto_result = process_scan(
            scan_path=case.input_scan_path,
            mount_id="gopro_low_profile_v1",
            output_root=output_root / "auto",
        )
        records.append(
            build_benchmark_record(
                case=case,
                run_type="auto",
                result_path=auto_result.result_json_path,
                reference_center=reference_center,
            )
        )

        if case.reference_review_path is not None and case.reference_review_path.exists():
            reference_result = process_scan(
                scan_path=case.input_scan_path,
                mount_id="gopro_low_profile_v1",
                output_root=output_root / "reference",
                review_path=case.reference_review_path,
            )
            records.append(
                build_benchmark_record(
                    case=case,
                    run_type="reference",
                    result_path=reference_result.result_json_path,
                    reference_center=reference_center,
                )
            )

        if case.mount_asset_path is not None and case.mount_asset_path.exists():
            asset_result = process_scan(
                scan_path=case.input_scan_path,
                mount_id="gopro_low_profile_v1",
                output_root=output_root / "real_asset",
                mount_asset_path=case.mount_asset_path,
            )
            records.append(
                build_benchmark_record(
                    case=case,
                    run_type="real_asset",
                    result_path=asset_result.result_json_path,
                    reference_center=reference_center,
                )
            )

    summary_json_path = report_dir / "benchmark_summary.json"
    summary_csv_path = report_dir / "benchmark_summary.csv"
    report_md_path = report_dir / "benchmark_report.md"

    summary = {"generated_at": timestamp, "cases_root": str(cases_root), "records": records}
    summary_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_summary_csv(summary_csv_path, records)
    report_md_path.write_text(build_markdown_report(records), encoding="utf-8")
    return report_dir


def load_benchmark_cases(cases_root: Path) -> list[BenchmarkCase]:
    """Load all case manifests from the cases directory."""

    cases: list[BenchmarkCase] = []
    if not cases_root.exists():
        return cases
    for case_json in sorted(cases_root.glob("*/case.json")):
        payload = json.loads(case_json.read_text(encoding="utf-8-sig"))
        case_dir = case_json.parent
        scan_path = resolve_case_path(case_dir, Path(payload["input_scan_path"]))
        mount_asset_path = payload.get("mount_asset_path")
        reference_path = case_dir / "review.reference.json"
        cases.append(
            BenchmarkCase(
                case_id=str(payload["case_id"]),
                input_scan_path=scan_path,
                mount_asset_path=resolve_case_path(case_dir, Path(mount_asset_path))
                if mount_asset_path
                else None,
                notes=str(payload.get("notes", "")),
                enabled=bool(payload.get("enabled", True)),
                case_dir=case_dir,
                reference_review_path=reference_path if reference_path.exists() else None,
            )
        )
    return cases


def resolve_case_path(case_dir: Path, path_value: Path) -> Path:
    """Resolve a benchmark manifest path relative to the case directory or repo root."""

    return path_value if path_value.is_absolute() else (case_dir / path_value).resolve()


def load_reference_center(review_path: Optional[Path]) -> Optional[list[float]]:
    """Load reference mount center from a review file when present."""

    if review_path is None or not review_path.exists():
        return None
    payload = json.loads(review_path.read_text(encoding="utf-8-sig"))
    center = payload.get("mount_center_override")
    if center is None:
        return None
    return [float(center[0]), float(center[1]), float(center[2])]


def build_benchmark_record(
    case: BenchmarkCase,
    run_type: str,
    result_path: Path,
    reference_center: Optional[list[float]],
) -> dict[str, Any]:
    """Build a summary record from one run result."""

    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    mount_center = result["mount_frame"]["origin"]
    diagnostics = result["diagnostics"]
    review = result["review"]
    reference_distance = (
        float(sum((mount_center[i] - reference_center[i]) ** 2 for i in range(3)) ** 0.5)
        if reference_center is not None
        else None
    )
    reference_y_delta = mount_center[1] - reference_center[1] if reference_center is not None else None
    reference_z_delta = mount_center[2] - reference_center[2] if reference_center is not None else None

    mount_center_debug_path = Path(result["output_dir"]) / "mount_center_debug.json"
    debug_payload = (
        json.loads(mount_center_debug_path.read_text(encoding="utf-8-sig"))
        if mount_center_debug_path.exists()
        else {}
    )
    return {
        "case_id": case.case_id,
        "run_type": run_type,
        "status": result["status"],
        "mount_center_x": mount_center[0],
        "mount_center_y": mount_center[1],
        "mount_center_z": mount_center[2],
        "mount_center_source": result["mount_center_source"],
        "reference_center_distance_mm": reference_distance,
        "reference_center_y_delta_mm": reference_y_delta,
        "reference_center_z_delta_mm": reference_z_delta,
        "mean_gap_mm": diagnostics.get("mean_gap_mm"),
        "p90_gap_mm": diagnostics.get("p90_gap_mm"),
        "coverage_ratio": diagnostics.get("coverage_ratio"),
        "shell_count": result["saddle"]["validation"].get("shell_count"),
        "mount_asset_type": result["mount_asset"]["type"],
        "final_export_status": result["saddle"]["final_export_status"],
        "review_approved": review["approved"],
        "candidate_count": debug_payload.get("candidate_count"),
        "frontier_count": debug_payload.get("frontier_candidate_count"),
        "selected_method": debug_payload.get("selection_method"),
        "frontier_percentile": debug_payload.get("frontier_percentile"),
        "centerline_bias_weight": debug_payload.get("centerline_bias_weight"),
        "front_bias_weight": debug_payload.get("front_bias_weight"),
        "low_bias_weight": debug_payload.get("low_bias_weight"),
        "selected_topk_count": debug_payload.get("top_candidate_count"),
        "result_path": str(result_path),
        "notes": case.notes,
    }


def write_summary_csv(path: Path, records: list[dict[str, Any]]) -> None:
    """Write benchmark summary CSV."""

    fieldnames = [
        "case_id",
        "run_type",
        "status",
        "mount_center_x",
        "mount_center_y",
        "mount_center_z",
        "reference_center_distance_mm",
        "mean_gap_mm",
        "p90_gap_mm",
        "coverage_ratio",
        "shell_count",
        "mount_asset_type",
        "final_export_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({key: record.get(key) for key in fieldnames})


def build_markdown_report(records: list[dict[str, Any]]) -> str:
    """Build a lightweight markdown summary report."""

    lines = [
        "# Benchmark Report",
        "",
        "| case_id | run_type | ref_dist_mm | mean_gap_mm | shell_count | asset | export_status |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for record in records:
        mount_asset_type = record.get("mount_asset_type", "")
        lines.append(
            "| {case_id} | {run_type} | {reference_center_distance_mm} | {mean_gap_mm} | {shell_count} | {mount_asset_type} | {final_export_status} |".format(
                **{
                    **record,
                    "reference_center_distance_mm": _fmt(record.get("reference_center_distance_mm")),
                    "mean_gap_mm": _fmt(record.get("mean_gap_mm")),
                    "shell_count": record.get("shell_count", ""),
                    "mount_asset_type": mount_asset_type,
                    "final_export_status": record.get("final_export_status", record.get("status", "")),
                }
            )
        )
    bad_cases = [
        record
        for record in records
        if record.get("reference_center_distance_mm") not in (None, "")
        and float(record["reference_center_distance_mm"]) > 10.0
    ]
    lines.extend(["", "## Review Needed Cases", ""])
    if bad_cases:
        for record in bad_cases:
            lines.append(f"- `{record['case_id']}` `{record['run_type']}` ref distance `{_fmt(record['reference_center_distance_mm'])}` mm")
    else:
        lines.append("- None")

    shell_cases = [record for record in records if (record.get("shell_count") or 0) > 1]
    lines.extend(["", "## Multi-shell Warnings", ""])
    if shell_cases:
        for record in shell_cases:
            lines.append(f"- `{record['case_id']}` `{record['run_type']}` shell_count `{record['shell_count']}`")
    else:
        lines.append("- None")

    fallback_cases = [
        record for record in records if str(record.get("status", "")).startswith("input_scan_") or record.get("status") == "disabled"
    ]
    lines.extend(["", "## Unavailable Or Disabled Cases", ""])
    if fallback_cases:
        for record in fallback_cases:
            lines.append(f"- `{record['case_id']}` `{record['run_type']}` status `{record['status']}`")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _disabled_record(case: BenchmarkCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "run_type": "disabled",
        "status": "disabled",
        "mount_center_x": None,
        "mount_center_y": None,
        "mount_center_z": None,
        "reference_center_distance_mm": None,
        "mean_gap_mm": None,
        "p90_gap_mm": None,
        "coverage_ratio": None,
        "shell_count": None,
        "mount_asset_type": None,
        "final_export_status": "disabled",
        "notes": case.notes,
    }


def _missing_record(case: BenchmarkCase, status: str) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "run_type": "auto",
        "status": status,
        "mount_center_x": None,
        "mount_center_y": None,
        "mount_center_z": None,
        "reference_center_distance_mm": None,
        "mean_gap_mm": None,
        "p90_gap_mm": None,
        "coverage_ratio": None,
        "shell_count": None,
        "mount_asset_type": None,
        "final_export_status": status,
        "notes": case.notes,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _create_report_dir(reports_root: Path, timestamp: str) -> Path:
    """Create a unique benchmark report directory."""

    reports_root.mkdir(parents=True, exist_ok=True)
    for suffix in range(1000):
        candidate = (
            reports_root / f"run_{timestamp}"
            if suffix == 0
            else reports_root / f"run_{timestamp}_{suffix:03d}"
        )
        try:
            candidate.mkdir(parents=False, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError("Could not create a unique benchmark report directory.")


if __name__ == "__main__":
    app()
