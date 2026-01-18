import mimetypes
import platform

from datetime import datetime
from pathlib import Path
from typing import (
    Dict,
    List,
    Optional,
)

from agentic_fs_archaeologist.models import (
    DeletionConfidence,
    ReflectionOutcome
)
from agentic_fs_archaeologist.memory.retrieval import MemoryRetrieval
from agentic_fs_archaeologist.memory.store import MemoryStore


class ReflectionTools:
    """
    Tools for autonomous reflection and self-critique.
    """

    @staticmethod
    def add_safety_risk(path: str, description: str, severity: str) -> Dict:
        """
        Helper function used to add a new safety risk to be flagged with
        escalation.
        """
        return {
            "action": "add_safety_risk",
            "path": path,
            "description": description,
            "severity": severity
        }

    @staticmethod
    def analyse_reflection_accuracy_metrics(
            memory_store: Optional[MemoryStore] = None) -> Dict:
        """
        Helper function used to calculate continuous improvement metrics
        for reflection.

        Args:
            memory_store: Optional MemoryStore instance

        Returns:
            Learning insights and improvement suggestions
        """

        if memory_store is None:
            memory_store = MemoryStore()

        metrics = memory_store.get_reflection_metrics()

        return {
            "total_reflections_recorded": metrics.total_reflections,
            "overall_accuracy_rate": metrics.accuracy_rate,
            "identified_error_patterns": metrics.common_error_patterns,
            "system_improvement_recommendations":
            metrics.improvement_suggestions,
            "learning_status":
            "active" if metrics.total_reflections > 0
                else "awaiting_reflections"
        }

    @staticmethod
    def check_file_dependencies(path: str) -> Dict:
        """
        Helper function used to analyse cross-platform dependencies including
        config references and running processes.
        """
        try:
            target = Path(path).expanduser().resolve()

            dependencies = {
                "config_references": [],
                "running_processes": [],
                "symlink_targets": [],
                "parent_configs": []
            }

            # Check for config file references
            path_str = str(target)
            config_files = [
                Path.home() / ".bashrc", Path.home() / ".zshrc",
                Path.home() / ".profile", Path.home() / ".bash_profile"
            ]

            for config in config_files:
                if config.exists():
                    try:
                        content = config.read_text()
                        if path_str in content:
                            dependencies["config_references"]\
                                .append(str(config))
                    except Exception:
                        continue

            # Check if it is a symlink
            if target.is_symlink():
                try:
                    target_path = target.readlink()
                    dependencies["symlink_targets"].append(str(target_path))
                except Exception:
                    pass

            # Platform-specific process checking
            system = platform.system()
            if system == "Windows":
                # Use tasklist or similar for Windows
                # Note: Process checking requires admin privileges on Windows
                pass
            else:
                # For Unix-like systems,
                # check if any process references this path
                try:
                    import subprocess
                    result = subprocess.run(
                        ["pgrep", "-f", path_str],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        dependencies["running_processes"] =\
                            result.stdout.strip().split("\n")
                except Exception:
                    # Note: Could not check running processes
                    pass

            l_cr = len(dependencies["config_references"])
            l_rp = len(dependencies["running_processes"])
            return {
                "path": str(target),
                "has_dependencies": l_cr > 0 or l_rp > 0,
                "dependency_count": l_cr + l_rp,
                "dependencies": dependencies
            }

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def downgrade_confidence(path: str, level: str, reasoning: str) -> Dict:
        """
        Helper function used to create a confidence downgrade critique
        for an item.
        """
        # This will be used by ReflectionAgent to create ReflectionCritique
        return {
            "action": "downgrade_confidence",
            "path": path,
            "level": level,
            "reasoning": reasoning,
            "original_confidence": "TO_BE_FILLED_BY_AGENT"
        }

    @staticmethod
    def get_file_metadata(path: str) -> Dict:
        """
        Helper function used to get the extended file attributes
        including MIME types, ownership, and encryption status.
        """
        try:
            target = Path(path).expanduser().resolve()

            if not target.exists():
                return {"error": "Path does not exist"}

            stat_info = target.stat()

            # MIME type detection
            mime_type, encoding = mimetypes.guess_type(str(target))
            if mime_type is None and target.is_file():
                mime_type = "application/octet-stream"

            # Owner/group info (platform dependent)
            owner_id = stat_info.st_uid
            group_id = stat_info.st_gid

            owner_name = "unknown"
            group_name = "unknown"
            try:
                import pwd
                import grp
                owner_name = pwd.getpwuid(owner_id).pw_name  # type: ignore
                group_name = grp.getgrgid(group_id).gr_name  # type: ignore
            except (ImportError, KeyError):
                # Windows or permission issues
                pass

            # Check for encryption (basic check)
            is_encrypted = False
            try:
                # Simple heuristic: check file extension
                encrypted_exts = [".enc", ".gpg", ".pgp", ".aes"]
                is_encrypted = target.suffix.lower() in encrypted_exts

                # Read first few bytes to check for encryption signatures
                if target.is_file():
                    with open(target, "rb") as f:
                        header = f.read(16)
                        # Check common encryption signatures
                        if header.startswith(b"\x00\x01") \
                                or header.startswith(b"Salted__"):
                            is_encrypted = True
            except Exception:
                pass

            return {
                "path": str(target),
                "size_bytes": stat_info.st_size,
                "modified_time": stat_info.st_mtime,
                "created_time":
                getattr(stat_info, "st_birthtime", stat_info.st_ctime),
                "accessed_time": stat_info.st_atime,
                "permissions":
                oct(stat_info.st_mode)[-3:],  # Last 3 octal digits
                "owner_id": owner_id,
                "owner_name": owner_name,
                "group_id": group_id,
                "group_name": group_name,
                "mime_type": mime_type,
                "encoding": encoding,
                "is_directory": target.is_dir(),
                "is_hidden": target.name.startswith("."),
                "is_encrypted": is_encrypted,
                "inode":
                stat_info.st_ino if hasattr(stat_info, "st_ino") else None
            }

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _map_confidence_string(confidence_str: str) -> DeletionConfidence:
        """
        Helper function used to map confidence strings from LLM to
        `DeletionConfidence` enum values.

        This mapping allows to deal with scenarios where confidence level
        strings like "high", "medium" and "low" are returned by the LLM, which
        differ from the expected enum values of `DeletionConfidence`,
        namely "safe", "likely_safe", "uncertain", "unsafe".
        """
        confidence_mapping = {
            "high": DeletionConfidence.SAFE,
            "medium": DeletionConfidence.LIKELY_SAFE,
            "low": DeletionConfidence.UNCERTAIN,
            "safe": DeletionConfidence.SAFE,
            "likely_safe": DeletionConfidence.LIKELY_SAFE,
            "uncertain": DeletionConfidence.UNCERTAIN,
            "unsafe": DeletionConfidence.UNSAFE
        }

        confidence_lower = confidence_str.lower().strip()
        if confidence_lower in confidence_mapping:
            return confidence_mapping[confidence_lower]
        else:
            l_k_str = list(confidence_mapping.keys())
            raise ValueError(f"Invalid confidence value: {confidence_str}. "
                             f"Valid values: {l_k_str}")

    @staticmethod
    def query_reflection_history(
            path_pattern: str,
            memory_store: Optional[MemoryStore] = None) -> Dict:
        """
        Helper function used to query past reflection decisions for learning.

        Args:
            path_pattern: Path pattern to search
            (e.g., "installer.exe", "cache", "*")
            memory_store: Optional MemoryStore instance
            for dependency injection

        Returns:
            Dict with search results and learning data
        """

        if memory_store is None:
            memory_store = MemoryStore()

        # Uses LIKE pattern matching for flexible path searches
        # e.g., searching "installer" finds
        # "installer.exe", "~/Downloads/installer"
        outcomes: List[ReflectionOutcome] =\
            memory_store.get_reflection_history(
                path_pattern=path_pattern,
                limit=10)

        return {
            "path_pattern": path_pattern,
            "results_count": len(outcomes),
            "past_reflection_insights": [
                {
                    "path": str(outcome.path),
                    "decision_type": outcome.decision,
                    "reasoning_used": outcome.reasoning,
                    "was_later_confirmed_accurate": outcome.accuracy_confirmed,
                    "confidence_level_before": outcome.confidence_before.value,
                    "confidence_level_after": outcome.confidence_after.value,
                    "additional_context": outcome.context,
                    "decision_timestamp": outcome.timestamp.isoformat()
                } for outcome in outcomes
            ]
        }

    @staticmethod
    def search_related_patterns(
            criteria: str,
            memory: MemoryRetrieval) -> Dict:
        """
        Helper function used to perform a semantic search over classification
        memory using criteria.
        """
        try:
            # Use synchronous search via the underlying store
            search_term = criteria.strip("*")  # Remove wildcards
            similar_entries = memory.store.search(search_term, limit=10)

            return {
                "search_criteria": criteria,
                "results_count": len(similar_entries),
                "similar_patterns": [
                    {
                        "pattern": entry.path_pattern,
                        "approval_rate": entry.approval_rate,
                        "confidence": entry.confidence.value,
                        "decisions":
                        entry.approval_count + entry.rejection_count
                    }
                    for entry in similar_entries
                ]
            }

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def store_reflection_outcome(
        path: str,
        decision: str,
        reasoning: str,
        confidence_before: str,
        confidence_after: str,
        memory_store: Optional[MemoryStore] = None
    ) -> Dict:
        """
        Helper function used to record a reflection decision
        for future learning.

        Args:
            path: Path of item reflected on
            decision: Type of decision made (e.g., "downgraded_to_likely_safe")
            reasoning: LLM reasoning for the decision
            confidence_before: Original confidence level
            confidence_after: New confidence level after reflection
            memory_store: Optional MemoryStore instance

        Returns:
            Acknowledgment of storage
        """

        if memory_store is None:
            memory_store = MemoryStore()

        accuracy_confirmed = None  # To be confirmed later via HITL
        # Note: This is a deferred confirmation
        # and updated later when user actions provide ground truth

        c_before = ReflectionTools._map_confidence_string(confidence_before)
        c_after = ReflectionTools._map_confidence_string(confidence_after)

        outcome = ReflectionOutcome(
            path=Path(path),
            decision=decision,
            reasoning=reasoning,
            accuracy_confirmed=accuracy_confirmed,  # Confirmed later via HITL
            confidence_before=c_before,
            confidence_after=c_after,
            context={},  # Could be expanded with item metadata
            timestamp=datetime.now()
        )

        memory_store.save_reflection_outcome(outcome)

        return {
            "stored_decision": decision,
            "for_path": path,
            "reasoning": reasoning,
            "learning_enabled": True
        }

    @staticmethod
    def trigger_reclassification(path: str, context: str) -> Dict:
        """
        Helper function used to queue an item for re-classification
        with additional context.
        """
        return {
            "action": "trigger_reclassification",
            "path": path,
            "context": context
        }
