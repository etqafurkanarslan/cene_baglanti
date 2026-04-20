"""Models for pipeline outputs and persisted result metadata."""

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.models.helmet_scan import HelmetScan, MeshInfo
from app.models.mount_spec import MountSpec

StageStatus = Literal["completed", "skipped", "stub", "failed"]


class PipelineStage(BaseModel):
    """Status entry for one pipeline stage."""

    name: str
    status: StageStatus
    message: str


class PipelineResult(BaseModel):
    """Complete metadata for one processing run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: Literal["completed", "failed"]
    started_at: datetime
    finished_at: datetime
    scan: HelmetScan
    mount: MountSpec
    mesh: MeshInfo
    output_dir: Path
    aligned_mesh_path: Optional[Path]
    result_json_path: Path
    stages: list[PipelineStage]

