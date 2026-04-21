"""Command line interface for the helmet mount bootstrap pipeline."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
import numpy as np

from app.config import (
    DEFAULT_PLACEMENT_CONFIG,
    DEFAULT_SYMMETRY_CONFIG,
    PlacementConfig,
    SymmetrySearchConfig,
)
from app.pipeline import process_scan
from app.geometry.saddle import SaddleConfig

app = typer.Typer(
    help="Process helmet scan meshes for mount placement and saddle generation.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """Helmet mount generation command group."""


@app.command()
def process(
    scan_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the input helmet scan mesh.",
    ),
    mount: str = typer.Option(
        "gopro_low_profile_v1",
        "--mount",
        "-m",
        help="Mount spec identifier to use for processing.",
    ),
    output_root: Optional[Path] = typer.Option(
        None,
        "--output-root",
        help="Directory where run outputs will be created.",
    ),
    max_sample: int = typer.Option(
        DEFAULT_SYMMETRY_CONFIG.max_sample,
        "--max-sample",
        min=1,
        help="Maximum number of mesh vertices sampled for symmetry solving.",
    ),
    angle_range: float = typer.Option(
        DEFAULT_SYMMETRY_CONFIG.angle_range_deg,
        "--angle-range",
        min=0.0,
        help="Angular search range in degrees around the +X normal.",
    ),
    angle_step: float = typer.Option(
        DEFAULT_SYMMETRY_CONFIG.angle_step_deg,
        "--angle-step",
        min=0.1,
        help="Angular search step in degrees.",
    ),
    patch_radius: Optional[float] = typer.Option(
        None,
        "--patch-radius",
        min=0.1,
        help="Radius in millimeters for local mount patch extraction.",
    ),
    mount_center_x: Optional[float] = typer.Option(
        None,
        "--mount-center-x",
        help="Override mount center X coordinate in aligned mesh coordinates.",
    ),
    mount_center_y: Optional[float] = typer.Option(
        None,
        "--mount-center-y",
        help="Override mount center Y coordinate in aligned mesh coordinates.",
    ),
    mount_center_z: Optional[float] = typer.Option(
        None,
        "--mount-center-z",
        help="Override mount center Z coordinate in aligned mesh coordinates.",
    ),
    contact_offset: Optional[float] = typer.Option(
        None,
        "--contact-offset",
        min=0.0,
        help="Offset from sampled helmet patch to saddle contact surface.",
    ),
    footprint_width: Optional[float] = typer.Option(
        None,
        "--footprint-width",
        min=1.0,
        help="Saddle/mount footprint width in millimeters.",
    ),
    footprint_height: Optional[float] = typer.Option(
        None,
        "--footprint-height",
        min=1.0,
        help="Saddle/mount footprint height in millimeters.",
    ),
    saddle_height: Optional[float] = typer.Option(
        None,
        "--saddle-height",
        min=0.1,
        help="Height from contact support to top footprint in millimeters.",
    ),
    review: Optional[Path] = typer.Option(
        None,
        "--review",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to review.json with approval and numeric overrides.",
    ),
    mount_asset: Optional[Path] = typer.Option(
        None,
        "--mount-asset",
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional mount asset STL path; invalid assets fall back to placeholder.",
    ),
    contact_fit_method: str = typer.Option(
        SaddleConfig.contact_fit_method,
        "--contact-fit-method",
        help="Contact surface fit method: weighted_rbf or nearest.",
    ),
    contact_smoothing_passes: int = typer.Option(
        SaddleConfig.smoothing_passes,
        "--contact-smoothing-passes",
        min=0,
        help="Number of circular smoothing passes for contact profile.",
    ),
    mount_asset_origin_mode: str = typer.Option(
        "mount-local",
        "--mount-asset-origin-mode",
        help="Asset coordinate convention. Current supported value: mount-local.",
    ),
) -> None:
    """Run the first-pass helmet scan processing pipeline."""

    symmetry_config = SymmetrySearchConfig(
        max_sample=max_sample,
        angle_range_deg=angle_range,
        angle_step_deg=angle_step,
        offset_ratio=DEFAULT_SYMMETRY_CONFIG.offset_ratio,
        offset_steps=DEFAULT_SYMMETRY_CONFIG.offset_steps,
        trim_ratio=DEFAULT_SYMMETRY_CONFIG.trim_ratio,
    )
    placement_config = PlacementConfig(
        patch_radius_mm=DEFAULT_PLACEMENT_CONFIG.patch_radius_mm,
        center_band_mm=DEFAULT_PLACEMENT_CONFIG.center_band_mm,
        front_percentile=DEFAULT_PLACEMENT_CONFIG.front_percentile,
        lower_percentile=DEFAULT_PLACEMENT_CONFIG.lower_percentile,
    )
    mount_center_override = _parse_mount_center_override(
        mount_center_x,
        mount_center_y,
        mount_center_z,
    )
    result = process_scan(
        scan_path=scan_path,
        mount_id=mount,
        output_root=output_root,
        symmetry_config=symmetry_config,
        placement_config=placement_config,
        mount_center_override=mount_center_override,
        review_path=review,
        patch_radius_override=patch_radius,
        contact_offset_override=contact_offset,
        footprint_width_override=footprint_width,
        footprint_height_override=footprint_height,
        saddle_height_override=saddle_height,
        mount_asset_path=mount_asset,
        contact_fit_method=contact_fit_method,
        contact_smoothing_passes=contact_smoothing_passes,
        mount_asset_origin_mode=mount_asset_origin_mode,
    )

    table = Table(title="Process Result")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Status", result.status)
    table.add_row("Scan", str(result.scan.path))
    table.add_row("Mount", result.mount.mount_id)
    table.add_row("Output", str(result.output_dir))
    table.add_row("Vertices", str(result.mesh.vertex_count))
    table.add_row("Faces", str(result.mesh.face_count))
    table.add_row("Symmetry Score", f"{result.symmetry.score:.6g}")
    table.add_row("Symmetry Normal", str(result.symmetry.plane_normal))
    table.add_row("Mount Center", str(result.mount_frame.origin))
    table.add_row("Mount Center Source", result.mount_center_source)
    table.add_row("Saddle Preview", str(result.saddle.preview_path))
    table.add_row("Final Mount", str(result.saddle.final_mount_path))
    table.add_row("Review Approved", str(result.review.approved))
    table.add_row("Contact Mean Gap", str(result.diagnostics.get("mean_gap_mm")))
    table.add_row("Aligned Mesh", str(result.aligned_mesh_path or "not exported"))
    table.add_row("Result JSON", str(result.result_json_path))
    console.print(table)


def _parse_mount_center_override(
    x: Optional[float],
    y: Optional[float],
    z: Optional[float],
) -> Optional[np.ndarray]:
    """Parse mount center override and require all coordinates together."""

    values = [x, y, z]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise typer.BadParameter(
            "Provide all of --mount-center-x, --mount-center-y, and --mount-center-z.",
        )
    return np.array([x, y, z], dtype=float)


if __name__ == "__main__":
    app()
