# cene_baglanti

V1 bootstrap for a helmet scan processing pipeline that will grow into:

```text
helmet scan -> symmetry solve -> alignment -> mount placement -> saddle generation
```

The first version provides a working Python CLI, mesh loading, output directory creation, mesh metadata reporting, `result.json` export, and clear geometry stubs for symmetry and alignment.

## Setup

Python 3.10-3.13 is recommended. Python 3.14 may not have a compatible `open3d` wheel yet.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## CLI

```powershell
python -m app.cli --help
python -m app.cli process scans\helmet_scan.stl --mount gopro_low_profile_v1
python -m app.benchmark run
```

Each `process` run creates a timestamped directory under `outputs/` containing:

- `result.json`
- `aligned_mesh.stl`

## Project Structure

```text
app/
  geometry/
  models/
  utils/
  exporters/
  workers/
mounts/gopro_low_profile_v1/
scans/
outputs/
tests/
```

## Current Geometry Status

`app.geometry.symmetry` solves an approximate YZ-like symmetry plane with sampled vertices, mirrored nearest-neighbor scoring, and trimmed mean error. `app.geometry.align` maps that plane to canonical `x=0` with the normal facing `+X`.

## Benchmark

Benchmark cases live under `benchmark/cases/<case_id>/`.

Each case may contain:

- `case.json`
- `review.reference.json`

Minimal `case.json` fields:

```json
{
  "case_id": "helmet_a",
  "input_scan_path": "C:/local/path/to/Mesh.ply",
  "mount_asset_path": "C:/local/path/to/mount.stl",
  "enabled": true,
  "notes": "optional note"
}
```

Run the benchmark:

```powershell
python -m app.benchmark run
```

Outputs are written under `benchmark/reports/<timestamp>/`:

- `benchmark_summary.json`
- `benchmark_summary.csv`
- `benchmark_report.md`

Per-case run folders keep the normal debug artifacts:

- `mount_center_debug.json`
- `patch_bounds_debug.json`
- `frame_debug.json`
- `placement_debug_top.png`
- `placement_debug_perspective.png`
- `saddle_debug.json`
- `result.json`

Interpretation guidance:

- lower `reference_center_distance_mm` is better
- lower `p90_gap_mm` is better
- higher `coverage_ratio` is better
- `shell_count > 1` means the export is not a single solid
- `final_export_status = reviewed` means the run used an approved reference review

Known benchmark limit:

- cases that point to unavailable local scan files are skipped or marked unavailable; the repository keeps only manifests and reference reviews, not the real scan meshes
