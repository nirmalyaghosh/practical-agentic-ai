from enum import Enum


class ApprovalStatus(str, Enum):
    """
    Represents the status of user approval for deletion.
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class DeletionConfidence(str, Enum):
    """
    Represents the confidence levels for deletion safety.
    """
    SAFE = "safe"  # High confidence, safe to delete
    LIKELY_SAFE = "likely_safe"  # Medium confidence
    UNCERTAIN = "uncertain"  # Low confidence, needs human review
    UNSAFE = "unsafe"  # Do not delete


class DirectoryType(str, Enum):
    """
    Represents the types of directories that can be classified by the
    Filesystem Archaeologist Agent.
    """
    NODE_MODULES = "node_modules"
    VENV = "venv"
    CACHE_DIR = "cache_dir"
    BUILD_DIR = "build_dir"
    TEMP_DIR = "temp_dir"
    GIT_DIR = "git_dir"
    OTHER = "other"


class FileType(str, Enum):
    """
    Represents the types of files that can be classified by the Filesystem
    Archaeologist Agent.
    """
    CACHE = "cache"
    BUILD_ARTIFACT = "build_artifact"
    TEMP_FILE = "temp_file"
    DUPLICATE = "duplicate"
    OLD_DOWNLOAD = "old_download"
    UNUSED_DEPENDENCY = "unused_dependency"
    LOG_FILE = "log_file"
    BACKUP = "backup"
    OTHER = "other"
