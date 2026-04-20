"""Pipeline orchestration for helmet scan processing."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from app.config import DEFAULT_OUTPUT_ROOT
from app.geometry.align import AlignmentResult, align_to_reference_frame
from app.geometry.preprocess import load_mesh, summarize_mesh
from app.geometry.symmetry import SymmetryResult, estimate_symmetry_plane
from app.models.helmet_scan import HelmetScan
from app.models.mount_spec import MountSpec
from app.models.result import PipelineResult, PipelineStage
from app.utils.io import create_output_dir, export_mesh_as_stl, write_json

console = Console()


def process_scan(
    scan_path: Path,
    mount_id: str,
    output_root: Optional[Path] = None,
) -> PipelineResult:
    """Process a helmet scan mesh and persist first-pass run artifacts."""

    started_at = datetime.now(timezone.utc)
    output_base = output_root or DEFAULT_OUTPUT_ROOT

    console.log(f"Loading mesh: {scan_path}")
    mesh = load_mesh(scan_path)
    mesh_info = summarize_mesh(mesh)

    output_dir = create_output_dir(output_base, scan_path.stem)
    console.log(f"Created output directory: {output_dir}")

    scan = HelmetScan(path=scan_path.resolve(), name=scan_path.stem)
    mount = MountSpec.from_id(mount_id)

    symmetry = estimate_symmetry_plane(mesh)
    alignment = align_to_reference_frame(mesh, symmetry)

    aligned_mesh_path = output_dir / "aligned_mesh.stl"
    exported_path = export_mesh_as_stl(alignment.mesh, aligned_mesh_path)

    stages = [
        PipelineStage(name="load_mesh", status="completed", message="Input mesh loaded."),
        PipelineStage(
            name="symmetry",
            status=symmetry.status,
            message=symmetry.message,
        ),
        PipelineStage(
            name="alignment",
            status=alignment.status,
            message=alignment.message,
        ),
        PipelineStage(
            name="export_aligned_mesh",
            status="completed" if exported_path else "skipped",
            message="Aligned mesh exported." if exported_path else "Mesh export skipped.",
        ),
    ]

    result_json_path = output_dir / "result.json"
    result = PipelineResult(
        status="completed",
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        scan=scan,
        mount=mount,
        mesh=mesh_info,
        output_dir=output_dir,
        aligned_mesh_path=exported_path,
        result_json_path=result_json_path,
        stages=stages,
    )
    write_json(result_json_path, result.model_dump(mode="json"))
    console.log(f"Wrote result JSON: {result_json_path}")

    return result

