"""Mount specification model."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.config import DEFAULT_MOUNTS_ROOT


class MountSpec(BaseModel):
    """Describes a mount target used by future placement and saddle stages."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    mount_id: str
    root: Path
    display_name: str
    version: str = "v1"
    description: Optional[str] = None

    @classmethod
    def from_id(cls, mount_id: str) -> "MountSpec":
        """Create a mount spec from a known mount identifier."""

        return cls(
            mount_id=mount_id,
            root=(DEFAULT_MOUNTS_ROOT / mount_id).resolve(),
            display_name=mount_id.replace("_", " ").title(),
            description="Bootstrap mount spec placeholder.",
        )

