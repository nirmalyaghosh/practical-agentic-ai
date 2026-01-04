from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    Field,
)

from agentic_fs_archaeologist.models.base import (
    ApprovalStatus,
    DeletionConfidence,
    DirectoryType,
    FileType,
)


class MemoryEntry(BaseModel):
    """
    Pydantic data model used for an entry in the agent's memory system.
    """
    path_pattern: str
    file_type: Optional[FileType] = None
    directory_type: Optional[DirectoryType] = None
    user_decision: ApprovalStatus
    confidence: DeletionConfidence
    approval_count: int = 0
    rejection_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @property
    def approval_rate(self) -> float:
        """
        Helper function used to calculate approval rate.
        """
        total = self.approval_count + self.rejection_count
        if total == 0:
            return 0.0
        return self.approval_count / total
