from pathlib import Path
from typing import List

from agentic_fs_archaeologist.agents.base import BaseAgent
from agentic_fs_archaeologist.models import (
    AgentResult,
    AgentState,
    ReflectionCritique,
    DeletionConfidence,
)


class ReflectionAgent(BaseAgent):
    """
    A reflection agent that reviews classifications for errors.
    The current implementation uses rule-based checks.
    """

    # System paths that should never be deleted
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

    # Important user directories to be cautious about
    IMPORTANT_DIRS = [
        "Desktop",
        "Documents",
        "Downloads",
        "Photos",
        "Pictures",
    ]

    # File extensions that are safe to delete from Downloads
    CLEANUP_SAFE_EXTENSIONS = [
        ".exe",
        ".msi",
        ".dmg",
        ".pkg",  # Installers
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",  # Archives
        ".iso",
        ".img",  # Disk images
    ]

    async def execute(self, state: AgentState) -> AgentResult:
        """
        Execute reflection by reviewing classifications.

        Args:
            state: Current agent state with classifications

        Returns:
            AgentResult with critiques and classifications
        """
        classifications = state.classifications
        critiques: List[ReflectionCritique] = []

        for classification in classifications:
            issues = []
            additional_risks = []
            suggested_confidence = None

            # Check 1: System path detection
            if self._is_system_path(classification.path):
                issues.append("System path detected - marking as UNSAFE")
                additional_risks.append("Critical system file or directory")
                suggested_confidence = DeletionConfidence.UNSAFE

            # Check 2: Overconfidence on very large items (>10GB)
            if classification.confidence == DeletionConfidence.SAFE:
                if classification.estimated_savings_bytes > 10 * 1024**3:
                    s = "Very large item (>10GB) marked as SAFE - downgrading"
                    issues.append(s)
                    r = "Large size warrants extra caution"
                    additional_risks.append(r)
                    suggested_confidence = DeletionConfidence.LIKELY_SAFE

            # Check 3: Important user directories
            # Exception: installers/archives in Downloads are
            # cleanup candidates
            if self._in_important_dir(classification.path):
                if classification.confidence in [
                    DeletionConfidence.SAFE,
                    DeletionConfidence.LIKELY_SAFE
                ]:
                    # Do not downgrade installers/archives in Downloads
                    if not self._is_cleanup_safe_file(classification.path):
                        s = "Located in important user directory - downgrading"
                        issues.append(s)
                        r = "May contain personal or important files"
                        additional_risks.append(r)
                        suggested_confidence = DeletionConfidence.UNCERTAIN

            # Check 4: Recently modified files marked as safe
            # If reasoning mentions recent modification but still marked safe
            if classification.confidence == DeletionConfidence.SAFE:
                if "recent" in classification.reasoning.lower():
                    s = "Recently modified but marked SAFE - needs review"
                    issues.append(s)
                    suggested_confidence = DeletionConfidence.LIKELY_SAFE

            # If issues found, create critique and apply fixes
            if issues:
                critique = ReflectionCritique(
                    classification_path=classification.path,
                    issues_found=issues,
                    suggested_confidence=suggested_confidence,
                    additional_risks=additional_risks,
                    should_review=True,
                    critique_reasoning=" | ".join(issues)
                )

                # Apply critique - modify the classification
                if suggested_confidence:
                    classification.confidence = suggested_confidence

                classification.risks.extend(additional_risks)

                critiques.append(critique)

        return AgentResult(
            success=True,
            data={"critiques": critiques},
            reasoning=[
                f"Reviewed {len(classifications)} classifications",
                f"Found issues in {len(critiques)} items",
                f"Modified {len(critiques)} confidence levels"
            ],
            metadata={
                "total_reviewed": len(classifications),
                "issues_found": len(critiques)
            }
        )

    def _in_important_dir(self, path: Path) -> bool:
        """
        Helper function used to check if the indicated path is in an important
        user directory.
        """
        path_str = str(path)
        for important_dir in self.IMPORTANT_DIRS:
            if f"/{important_dir}/" in path_str or \
                    f"\\{important_dir}\\" in path_str:
                return True
        return False

    def _is_cleanup_safe_file(self, path: Path) -> bool:
        """
        Helper function used to check if file type is safe to cleanup
        from Downloads. Installers and archives are typically safe to
        delete.
        """
        suffix = path.suffix.lower()
        return suffix in self.CLEANUP_SAFE_EXTENSIONS

    def _is_system_path(self, path: Path) -> bool:
        """
        Helper function used to check if the indicated path is a system path
        that should never be deleted.
        """
        path_str = str(path)
        for sys_path in self.SYSTEM_PATHS:
            if path_str.startswith(sys_path):
                return True
        return False
