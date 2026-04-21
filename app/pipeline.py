"""Pipeline orchestration for helmet scan processing."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from rich.console import Console

from app.config import (
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_PLACEMENT_CONFIG,
    DEFAULT_SYMMETRY_CONFIG,
    PlacementConfig,
    SymmetrySearchConfig,
)
from app.geometry.align import align_to_reference_frame
from app.geometry.features import estimate_local_frame, estimate_mount_center
from app.geometry.preprocess import load_mesh, summarize_mesh
from app.geometry.symmetry import SymmetryResult, estimate_symmetry_plane
from app.models.helmet_scan import HelmetScan
from app.models.mount_spec import MountSpec
from app.models.result import (
    AlignmentModel,
    MountFrameModel,
    PipelineResult,
    PipelineStage,
    SymmetryPlaneModel,
)
from app.utils.io import create_output_dir, export_mesh_as_stl, write_json

console = Console()


def process_scan(
    scan_path: Path,
    mount_id: str,
    output_root: Optional[Path] = None,
    symmetry_config: SymmetrySearchConfig = DEFAULT_SYMMETRY_CONFIG,
    placement_config: PlacementConfig = DEFAULT_PLACEMENT_CONFIG,
    mount_center_override: Optional[np.ndarray] = None,
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

    symmetry = estimate_symmetry_plane(mesh, symmetry_config)
    console.log(
        f"Symmetry score: {symmetry.score:.6g} "
        f"(samples={symmetry.sample_count}, normal={_format_vector(symmetry.plane_normal)})"
    )
    alignment = align_to_reference_frame(mesh, symmetry)
    canonical_symmetry = _canonical_symmetry_result(symmetry, alignment.transform)

    mount_center, mount_center_source, chin_region = estimate_mount_center(
        mesh=alignment.mesh,
        symmetry_result=canonical_symmetry,
        config=placement_config,
        override=mount_center_override,
    )
    mount_frame, local_patch = estimate_local_frame(
        mesh=alignment.mesh,
        mount_center=mount_center,
        symmetry_result=canonical_symmetry,
        patch_radius_mm=placement_config.patch_radius_mm,
    )
    console.log(
        f"Mount center: {_format_vector(mount_center)} "
        f"(source={mount_center_source}, patch_vertices={len(local_patch.vertex_indices)})"
    )

    aligned_mesh_path = output_dir / "aligned_mesh.stl"
    exported_path = export_mesh_as_stl(alignment.mesh, aligned_mesh_path)
    mount_frame_path = output_dir / "mount_frame.json"
    chin_patch_points_path = output_dir / "chin_patch_points.json"
    mount_frame_payload = {
        "origin": _rounded_vector(mount_frame.origin),
        "x_axis": _rounded_vector(mount_frame.x_axis),
        "y_axis": _rounded_vector(mount_frame.y_axis),
        "z_axis": _rounded_vector(mount_frame.z_axis),
        "source": mount_frame.source,
        "mount_center_source": mount_center_source,
        "patch_radius_mm": placement_config.patch_radius_mm,
        "local_patch": local_patch.metadata,
        "chin_region": chin_region.metadata,
    }
    write_json(mount_frame_path, mount_frame_payload)
    write_json(
        chin_patch_points_path,
        {
            "points": np.round(local_patch.points, 6).tolist(),
            "vertex_indices": local_patch.vertex_indices.astype(int).tolist(),
            "metadata": local_patch.metadata,
        },
    )

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
        PipelineStage(
            name="mount_placement",
            status="completed",
            message="Estimated mount center, local frame, and debug patch.",
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
        input_mesh=mesh_info,
        symmetry=SymmetryPlaneModel(
            plane_point=np.round(symmetry.plane_point, 6).tolist(),
            plane_normal=np.round(symmetry.plane_normal, 8).tolist(),
            score=symmetry.score,
            sample_count=symmetry.sample_count,
            search_config=symmetry.search_config,
        ),
        alignment=AlignmentModel(
            transform_matrix=np.round(alignment.transform, 10).tolist(),
        ),
        mount_frame=MountFrameModel(
            origin=_rounded_vector(mount_frame.origin),
            x_axis=_rounded_vector(mount_frame.x_axis),
            y_axis=_rounded_vector(mount_frame.y_axis),
            z_axis=_rounded_vector(mount_frame.z_axis),
            source=mount_frame.source,
        ),
        mount_center_source=mount_center_source,
        mount_patch_radius_mm=placement_config.patch_radius_mm,
        chin_patch={
            "region": chin_region.metadata,
            "local_patch": local_patch.metadata,
        },
        output_dir=output_dir,
        aligned_mesh_path=exported_path,
        mount_frame_path=mount_frame_path,
        chin_patch_points_path=chin_patch_points_path,
        result_json_path=result_json_path,
        stages=stages,
    )
    write_json(result_json_path, result.model_dump(mode="json"))
    console.log(f"Wrote result JSON: {result_json_path}")

    return result


def _format_vector(vector: np.ndarray) -> str:
    """Format a small numeric vector for readable logs."""

    values = [f"{value:.4f}" for value in vector]
    return f"[{', '.join(values)}]"


def _rounded_vector(vector: np.ndarray) -> list[float]:
    """Round a vector for stable JSON output."""

    return np.round(np.asarray(vector, dtype=float), 6).tolist()


def _canonical_symmetry_result(
    symmetry: SymmetryResult,
    transform: np.ndarray,
) -> SymmetryResult:
    """Transform a solved symmetry plane into aligned mesh coordinates."""

    point_h = np.append(symmetry.plane_point, 1.0)
    canonical_point = (transform @ point_h)[:3]
    canonical_point[0] = 0.0
    canonical_normal = transform[:3, :3] @ symmetry.plane_normal
    if canonical_normal[0] < 0.0:
        canonical_normal = -canonical_normal
    return SymmetryResult(
        plane_point=canonical_point,
        plane_normal=canonical_normal / np.linalg.norm(canonical_normal),
        score=symmetry.score,
        sample_count=symmetry.sample_count,
        search_config=symmetry.search_config,
        normal=canonical_normal / np.linalg.norm(canonical_normal),
        origin=canonical_point,
        status=symmetry.status,
        message=symmetry.message,
    )
