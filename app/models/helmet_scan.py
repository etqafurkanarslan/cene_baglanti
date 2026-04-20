"""Models describing an input helmet scan and mesh metadata."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HelmetScan(BaseModel):
    """Reference to an input helmet scan file."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    name: str
    units: Optional[str] = Field(default=None, description="Source scan unit if known.")


class MeshInfo(BaseModel):
    """Basic mesh statistics captured during preprocessing."""

    vertex_count: int
    face_count: int
    bounds_min: list[float]
    bounds_max: list[float]
    extents: list[float]
    is_watertight: bool
    source_format: Optional[str] = None

