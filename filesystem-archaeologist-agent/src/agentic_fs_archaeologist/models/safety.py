from pathlib import Path
from typing import List

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class SafetyCheck(BaseModel):
    """
    Pydantic data model used for the results of safety checks.
    """
    check_name: str
    passed: bool
    reason: str
    severity: str = "info"  # info, warning, critical


class ValidationResult(BaseModel):
    """
    Pydantic data model used for the comprehensive validation result.
    """
    path: Path
    is_safe: bool
    checks: List[SafetyCheck]
    blocking_issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @field_validator('path', mode='before')
    @classmethod
    def convert_path(cls, v):
        """
        Helper function used to convert string paths to Path objects.
        """
        return Path(v) if isinstance(v, str) else v
