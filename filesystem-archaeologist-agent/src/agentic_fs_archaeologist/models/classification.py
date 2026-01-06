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

from agentic_fs_archaeologist.models.base import (
    CleanupRecommendation,
    DeletionConfidence,
    DirectoryType,
    FileType,
)


class Classification(BaseModel):
    """
    Pydantic data model used to represent/contain/contain the classification
    result for a file or directory.
    """
    path: Path
    file_type: Optional[FileType] = None
    directory_type: Optional[DirectoryType] = None
    recommendation: CleanupRecommendation = CleanupRecommendation.KEEP
    confidence: DeletionConfidence
    reasoning: str
    estimated_savings_bytes: int
    is_regenerable: bool = False
    dependencies: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)

    @field_validator("path", mode="before")
    @classmethod
    def convert_path(cls, v):
        """
        Helper function used to convert string paths to Path objects.
        """
        return Path(v) if isinstance(v, str) else v

    @property
    def savings_gb(self) -> float:
        """
        Helper function used to get the estimated savings in gigabytes.
        """
        return self.estimated_savings_bytes / (1024 * 1024 * 1024)


class ReflectionCritique(BaseModel):
    """
    Pydantic data model used to represent/contain the critique from the
    Reflection agent.
    """
    classification_path: Path
    issues_found: List[str]
    suggested_confidence: Optional[DeletionConfidence] = None
    additional_risks: List[str] = Field(default_factory=list)
    should_review: bool = False
    critique_reasoning: str

    @field_validator("classification_path", mode="before")
    @classmethod
    def convert_path(cls, v):
        """
        Helper function used to convert string paths to Path objects.
        """
        return Path(v) if isinstance(v, str) else v
