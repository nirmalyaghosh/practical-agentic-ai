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

from agentic_fs_archaeologist.models.base import DirectoryType


class FileMetadata(BaseModel):
    """
    Pydantic data model used to represent/contain the metadata about a file
    or directory.
    """
    path: Path
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    is_directory: bool
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    extension: Optional[str] = None

    @property
    def age_days(self) -> int:
        """
        Helper function used to get the age in days since last modification.
        """
        return (datetime.now() - self.modified_at).days

    @field_validator("path", mode="before")
    @classmethod
    def convert_path(cls, v):
        """
        Helper function used to convert string paths to Path objects.
        """
        return Path(v) if isinstance(v, str) else v

    @property
    def size_gb(self) -> float:
        """
        Helper function used to get the size in gigabytes.
        """
        return self.size_bytes / (1024 * 1024 * 1024)

    @property
    def size_mb(self) -> float:
        """
        Helper function used to get the size in megabytes.
        """
        return self.size_bytes / (1024 * 1024)


class DirectoryInfo(BaseModel):
    """
    Pydantic data model used to represent/contain the information
    about a directory and its contents.
    """
    path: Path
    total_size_bytes: int
    file_count: int
    subdirectory_count: int
    directory_type: Optional[DirectoryType] = None
    largest_files: List[FileMetadata] = Field(default_factory=list)

    @field_validator("path", mode="before")
    @classmethod
    def convert_path(cls, v):
        """
        Helper function used to convert string paths to Path objects.
        """
        return Path(v) if isinstance(v, str) else v

    @property
    def size_gb(self) -> float:
        """
        Helper function used to get the total size in gigabytes.
        """
        return self.total_size_bytes / (1024 * 1024 * 1024)
