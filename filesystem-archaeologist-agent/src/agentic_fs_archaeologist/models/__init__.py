"""
Pydantic data models for the Filesystem Archaeologist Agent.

This package contains the Pydantic models organized by domains:

- base (Enumerations and base types)
- filesystem (File and directory metadata)
- classification (Classification and reflection models)
- agent (Agent state, results, and ReAct models)
- workflow (Plan-execute and orchestration models)
- session (Session and user decision models)
- memory (Memory system models)
- safety (Safety and validation models)
"""

# Base enumerations
from agentic_fs_archaeologist.models.base import (
    FileType,
    DirectoryType,
    DeletionConfidence,
    ApprovalStatus,
)

# Filesystem models
from agentic_fs_archaeologist.models.filesystem import (
    FileMetadata,
    DirectoryInfo,
)

# Classification models
from agentic_fs_archaeologist.models.classification import (
    Classification,
    ReflectionCritique,
)

# Agent models
from agentic_fs_archaeologist.models.agent import (
    AgentState,
    AgentResult,
    ReActThought,
    ReActObservation,
    ReActHistory,
)

# Workflow models
from agentic_fs_archaeologist.models.workflow import (
    PlanStep,
    ExecutionPlan,
)

# Session models
from agentic_fs_archaeologist.models.session import (
    UserDecision,
    CleanupSession,
)

# Memory models
from agentic_fs_archaeologist.models.memory import (
    MemoryEntry,
)

# Safety models
from agentic_fs_archaeologist.models.safety import (
    SafetyCheck,
    ValidationResult,
)

__all__ = [
    # Base
    "FileType",
    "DirectoryType",
    "DeletionConfidence",
    "ApprovalStatus",
    # Filesystem
    "FileMetadata",
    "DirectoryInfo",
    # Classification
    "Classification",
    "ReflectionCritique",
    # Agent
    "AgentState",
    "AgentResult",
    "ReActThought",
    "ReActObservation",
    "ReActHistory",
    # Workflow
    "PlanStep",
    "ExecutionPlan",
    # Session
    "UserDecision",
    "CleanupSession",
    # Memory
    "MemoryEntry",
    # Safety
    "SafetyCheck",
    "ValidationResult",
]
