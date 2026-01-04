from datetime import datetime
from pathlib import Path
from typing import (
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from agentic_fs_archaeologist.models.base import ApprovalStatus
from agentic_fs_archaeologist.models.classification import Classification


class UserDecision(BaseModel):
    """
    Pydantic data model used for user decisions about file deletions.
    """
    path: Path
    classification: Classification
    status: ApprovalStatus
    user_feedback: Optional[str] = None
    decided_at: datetime = Field(default_factory=datetime.now)

    @field_validator("path", mode="before")
    @classmethod
    def convert_path(cls, v):
        """
        Helper function used to convert string paths to Path objects.
        """
        return Path(v) if isinstance(v, str) else v


class CleanupSession(BaseModel):
    """
    Pydantic data model used for cleanup session with all decisions.
    """
    session_id: str
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    target_path: Path
    decisions: List[UserDecision] = Field(default_factory=list)
    total_space_freed_bytes: int = 0

    @field_validator("target_path", mode="before")
    @classmethod
    def convert_path(cls, v):
        """
        Helper function used to convert string paths to Path objects.
        """
        return Path(v) if isinstance(v, str) else v

    @property
    def approval_rate(self) -> float:
        """
        Helper function used to calculate the approval rate.
        """
        if not self.decisions:
            return 0.0
        approved = sum(1 for d in self.decisions
                       if d.status == ApprovalStatus.APPROVED)
        return approved / len(self.decisions)

    @property
    def space_freed_gb(self) -> float:
        """
        Helper function used to calculate the space freed in gigabytes.
        """
        return self.total_space_freed_bytes / (1024 * 1024 * 1024)
