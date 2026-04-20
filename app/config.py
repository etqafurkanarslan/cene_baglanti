"""Project configuration constants."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs"
DEFAULT_MOUNTS_ROOT = PROJECT_ROOT / "mounts"
DEFAULT_SCANS_ROOT = PROJECT_ROOT / "scans"

