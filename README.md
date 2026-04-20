# cene_baglanti

V1 bootstrap for a helmet scan processing pipeline that will grow into:

```text
helmet scan -> symmetry solve -> alignment -> mount placement -> saddle generation
```

The first version provides a working Python CLI, mesh loading, output directory creation, mesh metadata reporting, `result.json` export, and clear geometry stubs for symmetry and alignment.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## CLI

```powershell
python -m app.cli --help
python -m app.cli process scans\helmet_scan.stl --mount gopro_low_profile_v1
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

`app.geometry.symmetry` and `app.geometry.align` intentionally contain deterministic stubs. Their function signatures are stable enough for the next implementation pass.

