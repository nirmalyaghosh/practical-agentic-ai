from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pydantic import BaseModel

from agentic_fs_archaeologist.models.base import DeletionConfidence


class ReflectionOutcome(BaseModel):
    """
    Pydantic data model used to record each reflection decision
    and its accuracy
    """
    path: Path
    decision: str  # e.g. "downgraded_to_likely_safe"
    reasoning: str  # LLM reasoning
    accuracy_confirmed: Optional[bool]
    confidence_before: DeletionConfidence
    confidence_after: DeletionConfidence
    context: Dict[str, Any]  # Size, type, similar cases
    timestamp: datetime


class ReflectionMetrics(BaseModel):
    """
    Pydantic data model used to aggregate for learning and improvement
    """
    total_reflections: int
    accuracy_rate: float
    common_error_patterns: List[str]
    improvement_suggestions: List[str]
