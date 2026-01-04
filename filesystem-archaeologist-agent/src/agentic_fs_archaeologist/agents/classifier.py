import subprocess

from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
)

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents.react_agent import ReActAgent
from agentic_fs_archaeologist.memory import MemoryRetrieval
from agentic_fs_archaeologist.models import (
    AgentState,
    AgentResult,
    ReActHistory,
)
from agentic_fs_archaeologist.prompts.prompts import load_prompts
from agentic_fs_archaeologist.tools import FileSystemTools


logger = get_logger(__name__)


class ClassifierAgent(ReActAgent):
    """
    Classifier using ReAct pattern (for tool orchestration) + Memory.

    Agentic Aspects:
    - LLM orchestrates tool calls (`classify_item`, `check_dependencies`, etc.)
    - LLM decides when to query memory for similar past decisions

    Non-Agentic Aspects:
    - Actual classification uses deterministic pattern matching
    - Safety decisions based on hardcoded rules (name/type checks)
    - Prompts are highly prescriptive (step-by-step process)

    The LLM acts as an orchestrator, not a decision-maker.
    """

    def __init__(self, memory: MemoryRetrieval):
        super().__init__()
        self.memory = memory

    def _build_system_prompt(self) -> str:
        prompts = load_prompts(prompt_json_file_path=None)
        return prompts["classifier_agent"]["system_prompt"]

    async def _check_dependencies(self, path: str) -> Dict:
        """
        Helper function used to check dependencies for a path.

        The current implementation checks for:
        - Symlinks pointing to this path
        - Whether path is currently in use by running processes
        """
        target = Path(path)
        has_dependencies = False
        dependencies = []

        try:
            # Check 1: Is this a symlink target? (other files depend on it)
            if target.exists():
                parent_dir = target.parent
                for item in parent_dir.iterdir():
                    try:
                        if item.is_symlink() and item.resolve() == target:
                            has_dependencies = True
                            dependencies.append(f"Symlink: {item}")
                    except (OSError, RuntimeError):
                        continue

            # Check 2: Is path currently in use?
            # (do a basic check via lsof, if available)
            if target.exists():
                try:
                    result = subprocess.run(
                        ["lsof", str(target)],
                        capture_output=True,
                        timeout=1,
                        text=True
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        has_dependencies = True
                        dependencies.append("File currently in use by process")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    # lsof not available or timeout - skip this check
                    pass

        except Exception:
            # If any errors, fail safe - assume no dependencies
            pass

        return {
            "has_dependencies": has_dependencies,
            "dependencies": dependencies,
        }

    async def _check_git_status(self, path: str) -> Dict:
        """
        Helper function used to check git status wrapper.
        """
        return FileSystemTools.check_git_status(path)

    async def _classify_item(
            self,
            path: str,
            size_bytes: int,
            is_directory: bool) -> Dict:
        """
        Helper function used to classify an item.

        NOTE: This is DETERMINISTIC pattern matching, not LLM reasoning.
        The "agentic" part is the LLM deciding WHEN to call this tool,
        not how the tool itself works.
        """
        target = Path(path)

        # Deterministic pattern matching (not LLM-driven)
        item_type = None
        dir_type = None

        if is_directory:
            name = target.name.lower()
            if name == "node_modules":
                dir_type = "node_modules"
            elif name in ["venv", ".venv", "env"]:
                dir_type = "venv"
            elif "cache" in name:
                dir_type = "cache_dir"
            elif name in ["build", "dist", "target", ".next"]:
                dir_type = "build_dir"
        else:
            ext = target.suffix.lower()
            if ext in [".dmg", ".pkg"]:
                item_type = "old_download"
            elif ext == ".log":
                item_type = "log_file"

        # Check age
        age_info = FileSystemTools.get_file_age(path)
        age_days = age_info.get("age_days", 0)

        return {
            "path": path,
            "size_bytes": size_bytes,
            "size_gb": size_bytes / (1024**3),
            "is_directory": is_directory,
            "type": dir_type or item_type or "other",
            "age_days": age_days,
        }

    async def _compile_results(
        self,
        history: ReActHistory,
        state: AgentState
    ) -> AgentResult:
        """
        Helper function used to compile classification results.
        """
        # Find the finish observation
        classifications = []
        for obs in history.observations:
            if obs.action == "finish":
                classifications = obs.result.get("classifications", [])
                break

        return AgentResult(
            success=True,
            data={"classifications": classifications},
            reasoning=self._extract_reasoning(history),
            metadata={"total_classified": len(classifications)}
        )

    async def _finish(self, classifications: list) -> Dict:
        """
        Helper function used to signal completion with classifications.
        """
        return {
            "action": "finish",
            "classifications": classifications,
            "total": len(classifications),
        }

    def _format_context(self, state: AgentState) -> str:
        """
        Helper function used to include discovered items in context.
        It overrides the `_format_context` function of the `ReActAgent`.
        """
        parts = []

        # Include basic context
        for key, value in state.context.items():
            parts.append(f"- {key}: {value}")

        # Include discovered items to classify
        if state.discoveries:
            n = len(state.discoveries)
            parts.append(f"\nItems to classify ({n} total):")
            # Show first 10
            for i, item in enumerate(state.discoveries[:10], 1):
                parts.append(f"  {i}. {item.path} ({item.size_gb:.2f} GB, "
                             f"{'dir' if item.is_directory else 'file'})")
            if n > 10:
                parts.append(f"  ... and {n - 10} more items")

        return "\n".join(parts) if parts else "No context provided"

    async def _query_similar_decisions(
        self,
        path: str
    ) -> Dict[str, Any]:
        """
        Helper function used to query memory for similar past decisions.
        """
        similar = await self.memory.find_similar(Path(path))

        return {
            "similar_count": len(similar),
            "patterns": [
                {
                    "pattern": entry.path_pattern,
                    "approval_rate": entry.approval_rate,
                    "times_seen": entry.approval_count + entry.rejection_count,
                    "user_decision": entry.user_decision.value
                }
                for entry in similar[:5]  # Top 5 most similar
            ],
            "average_approval_rate": (
                sum(e.approval_rate for e in similar) / len(similar)
                if similar else None
            )
        }

    def _get_tools(self) -> Dict[str, Callable]:
        return {
            "classify_item": self._classify_item,
            "check_git_status": self._check_git_status,
            "query_similar_decisions": self._query_similar_decisions,
            "check_dependencies": self._check_dependencies,
            "finish": self._finish,
        }
