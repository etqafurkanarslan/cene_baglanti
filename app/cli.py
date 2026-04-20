"""Command line interface for the helmet mount bootstrap pipeline."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.config import DEFAULT_SYMMETRY_CONFIG, SymmetrySearchConfig
from app.pipeline import process_scan

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
    result = process_scan(
        scan_path=scan_path,
        mount_id=mount,
        output_root=output_root,
        symmetry_config=symmetry_config,
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
    table.add_row("Aligned Mesh", str(result.aligned_mesh_path or "not exported"))
    table.add_row("Result JSON", str(result.result_json_path))
    console.print(table)


if __name__ == "__main__":
    app()
