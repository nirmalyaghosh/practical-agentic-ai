import mimetypes
import platform

from pathlib import Path
from typing import Dict

from agentic_fs_archaeologist.memory.retrieval import MemoryRetrieval


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
