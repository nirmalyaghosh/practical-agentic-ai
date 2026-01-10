import os

from pathlib import Path

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents.base import BaseAgent
from agentic_fs_archaeologist.models import (
    AgentResult,
    AgentState,
    Classification,
    DeletionConfidence,
    SafetyCheck,
    ValidationResult,
)


logger = get_logger(__name__)


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
        validations = []
        try:
            if not state or not hasattr(state, "classifications"):
                error_message = "Invalid state provided"
                logger.error(error_message)
                return AgentResult(success=False, error=error_message)

            classifications = state.classifications or []
            n_classifications = len(classifications) if classifications else 0
            logger.debug(f"Validating {n_classifications} classifications")
            for classification in classifications:
                validation = self._validate_classification(classification)
                validations.append(validation)

                # Update classification if not safe
                if not validation.is_safe:
                    classification.confidence = DeletionConfidence("unsafe")
                    classification.risks.extend(validation.blocking_issues)

            n_validations = len(validations)
            safe_count = sum(1 for v in validations if v.is_safe)
            unsafe_count = n_validations - safe_count
            logger.info(f"Completed {n_validations} validations "
                        f"({safe_count} safe, {unsafe_count} unsafe)")

            return AgentResult(
                success=True,
                data={"validations": validations},
                reasoning=[
                    f"Validated {n_validations} items",
                    f"Safe: {safe_count}, Unsafe: {unsafe_count}",
                ],
                metadata={
                    "safe_count": safe_count,
                    "unsafe_count": unsafe_count
                }
            )
        except Exception as e:
            logger.exception(e)
            return AgentResult(
                success=False,
                error=f"Validation failed: {str(e)}",
                data={
                    "validations": [],
                    "classifications": state.classifications or []
                },
                reasoning=["Validation process encountered an error"],
                metadata={}
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

    def _perform_path_exists_check(self, path: Path) -> SafetyCheck:
        exists, unk_str = False, None
        try:
            exists = path.exists()
        except OSError:
            exists = False
            unk_str = "Unable to determine existence"

        reason_str = "Path exists" if exists else \
            unk_str if unk_str else "Path does not exist"
        return SafetyCheck(
            check_name="path_exists",
            passed=exists,
            reason=reason_str,
            severity="critical" if not exists else "info"
        )

    def _perform_protected_pattern_check(self, path: Path) -> SafetyCheck:
        is_protected, reason = self._is_protected_pattern(path)
        return SafetyCheck(
            check_name="protected_pattern",
            passed=not is_protected,
            reason=reason,
            severity="warning" if is_protected else "info"
        )

    def _perform_system_path_check(self, path: Path) -> SafetyCheck:
        is_system, reason = self._is_system_path(path)
        return SafetyCheck(
            check_name="system_path",
            passed=not is_system,
            reason=reason,
            severity="critical" if is_system else "info"
        )

    def _perform_write_permission_check(self, path: Path) -> SafetyCheck:
        try:
            has_permission = os.access(path, os.W_OK)
            reason_str = "Has write permission" if has_permission \
                else "No write permission"
        except OSError:
            has_permission = False
            reason_str = "Unable to check permissions"
        return SafetyCheck(
            check_name="write_permission",
            passed=has_permission,
            reason=reason_str,
            severity="critical" if not has_permission else "info"
        )

    def _validate_classification(
            self,
            classification: Classification) -> ValidationResult:
        """
        Helper function used to validate a single classification.
        Sequence of checks:
        - is system path,
        - is protected pattern,
        - does the path exist,
        - does the file have write permission,
        """
        checks = []
        blocking_issues = []
        warnings = []

        path_to_check = classification.path
        system_check = self._perform_system_path_check(path=path_to_check)
        checks.append(system_check)
        if not system_check.passed:
            blocking_issues.append(system_check.reason)

        pp_check = self._perform_protected_pattern_check(path=path_to_check)
        checks.append(pp_check)
        if not pp_check.passed:
            warnings.append(pp_check.reason)

        exists_check = self._perform_path_exists_check(path=path_to_check)
        checks.append(exists_check)
        if not exists_check.passed:
            blocking_issues.append(exists_check.reason)

        permission_check = None
        if exists_check.passed:
            permission_check =\
                self._perform_write_permission_check(path=path_to_check)
            checks.append(permission_check)
            if not permission_check.passed:
                blocking_issues.append(permission_check.reason)

        is_safe = len(blocking_issues) == 0

        return ValidationResult(
            path=classification.path,
            is_safe=is_safe,
            checks=checks,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )
