"""Command line interface for the helmet mount bootstrap pipeline."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

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
) -> None:
    """Run the first-pass helmet scan processing pipeline."""

    result = process_scan(scan_path=scan_path, mount_id=mount, output_root=output_root)

    table = Table(title="Process Result")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Status", result.status)
    table.add_row("Scan", str(result.scan.path))
    table.add_row("Mount", result.mount.mount_id)
    table.add_row("Output", str(result.output_dir))
    table.add_row("Vertices", str(result.mesh.vertex_count))
    table.add_row("Faces", str(result.mesh.face_count))
    table.add_row("Aligned Mesh", str(result.aligned_mesh_path or "not exported"))
    table.add_row("Result JSON", str(result.result_json_path))
    console.print(table)


if __name__ == "__main__":
    app()
