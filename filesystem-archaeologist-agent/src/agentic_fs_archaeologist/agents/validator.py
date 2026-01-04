import os

from pathlib import Path

from agentic_fs_archaeologist.agents.base import BaseAgent
from agentic_fs_archaeologist.models import (
    AgentResult,
    AgentState,
    Classification,
    DeletionConfidence,
    SafetyCheck,
    ValidationResult,
)


class ValidatorAgent(BaseAgent):
    """
    Rule-based validator for safety checks (NOT agentic).
    """

    SYSTEM_PATHS = [
        "/System",
        "/Library",
        "/usr",
        "/etc",
        "/bin",
        "/sbin",
        "/var",
        "/private",
        "/Applications",
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
    ]

    PROTECTED_PATTERNS = [
        ".git",
        ".ssh",
        "Desktop",
        "Documents",
        "Downloads",
        "Photos",
        "Pictures",
    ]

    async def execute(self, state: AgentState) -> AgentResult:
        """
        Helper function used to validate classifications using safety rules.
        """
        classifications = state.classifications
        validations = []

        for classification in classifications:
            validation = self._validate_classification(classification)
            validations.append(validation)

            # Update classification if not safe
            if not validation.is_safe:
                classification.confidence = DeletionConfidence("unsafe")
                classification.risks.extend(validation.blocking_issues)

        safe_count = sum(1 for v in validations if v.is_safe)
        unsafe_count = len(validations) - safe_count

        return AgentResult(
            success=True,
            data={"validations": validations},
            reasoning=[
                f"Validated {len(validations)} items",
                f"Safe: {safe_count}, Unsafe: {unsafe_count}",
            ],
            metadata={"safe_count": safe_count, "unsafe_count": unsafe_count}
        )

    def _is_protected_pattern(self, path: Path) -> tuple:
        """
        Helper function used to check if path matches protected patterns.
        """
        path_str = str(path)
        for pattern in self.PROTECTED_PATTERNS:
            if pattern in path_str:
                return True, f"Protected pattern: {pattern}"
        return False, "Not a protected pattern"

    def _is_system_path(self, path: Path) -> tuple:
        """
        Helper function used to check if path is a system path.
        """
        path_str = str(path)
        for sys_path in self.SYSTEM_PATHS:
            if path_str.startswith(sys_path):
                return True, f"System path: {sys_path}"
        return False, "Not a system path"

    def _validate_classification(
            self,
            classification: Classification) -> ValidationResult:
        """
        Helper function used to validate a single classification.
        """
        checks = []
        blocking_issues = []
        warnings = []

        # Check 1: System path
        is_system, reason = self._is_system_path(classification.path)
        checks.append(SafetyCheck(
            check_name="system_path",
            passed=not is_system,
            reason=reason,
            severity="critical" if is_system else "info"
        ))
        if is_system:
            blocking_issues.append(reason)

        # Check 2: Protected pattern
        is_protected, reason = self._is_protected_pattern(classification.path)
        checks.append(SafetyCheck(
            check_name="protected_pattern",
            passed=not is_protected,
            reason=reason,
            severity="warning" if is_protected else "info"
        ))
        if is_protected:
            warnings.append(reason)

        # Check 3: Path exists
        exists = classification.path.exists()
        checks.append(SafetyCheck(
            check_name="path_exists",
            passed=exists,
            reason="Path exists" if exists else "Path does not exist",
            severity="critical" if not exists else "info"
        ))
        if not exists:
            blocking_issues.append("Path does not exist")

        # Check 4: Has write permission
        if exists:
            has_permission = os.access(classification.path, os.W_OK)
            reason_str = "Has write permission" if has_permission \
                else "No write permission",
            checks.append(SafetyCheck(
                check_name="write_permission",
                passed=has_permission,
                reason=reason_str,
                severity="critical" if not has_permission else "info"
            ))
            if not has_permission:
                blocking_issues.append("No write permission")

        is_safe = len(blocking_issues) == 0

        return ValidationResult(
            path=classification.path,
            is_safe=is_safe,
            checks=checks,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )
