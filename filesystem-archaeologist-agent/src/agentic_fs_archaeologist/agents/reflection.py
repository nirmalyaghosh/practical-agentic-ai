from pathlib import Path
from typing import (
    Callable,
    Dict,
    List,
)

from agentic_fs_archaeologist.agents.react_agent import ReActAgent
from agentic_fs_archaeologist.memory import (
    MemoryRetrieval,
    MemoryStore,
)
from agentic_fs_archaeologist.utils.file_utils import format_file_size
from agentic_fs_archaeologist.tools.reflection_tools import ReflectionTools
from agentic_fs_archaeologist.models import (
    AgentResult,
    AgentState,
    ReflectionCritique,
    ReActHistory,
)


class ReflectionAgent(ReActAgent):
    """
    An autonomous reflection agent that reviews classifications for errors.
    It uses LLM self-critique with specialized tools + learning from past
    decisions.
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

    def __init__(self):
        super().__init__()
        # Create shared memory once in constructor
        self.memory_store = MemoryStore()
        self.memory_retrieval = MemoryRetrieval(self.memory_store)

    async def _add_safety_risk(
            self,
            path: str,
            description: str,
            severity: str) -> Dict:
        return ReflectionTools.add_safety_risk(
            path=path,
            description=description,
            severity=severity)

    async def _analyse_reflection_accuracy_metrics(self) -> Dict:
        return ReflectionTools.analyse_reflection_accuracy_metrics(
            memory_store=self.memory_store)

    async def _check_file_dependencies(self, path: str) -> Dict:
        return ReflectionTools.check_file_dependencies(path)

    async def _compile_results(
        self,
        history: ReActHistory,
        state: AgentState
    ) -> AgentResult:
        """
        Helper function used to compile ReAct history into final reflection
        results.
        """
        # Extract all critiques from tool calls
        critiques: List[ReflectionCritique] = []

        for observation in history.observations:
            if observation.result and "critiques" in observation.result:
                critiques.extend(observation.result["critiques"])

        # Apply any critiques to the classifications
        for critique in critiques:
            # Find and modify the matching classification
            matching_cls = next(
                (cls for cls in state.classifications
                 if cls.path == Path(critique.classification_path)),
                None
            )
            if matching_cls and critique.suggested_confidence:
                matching_cls.confidence = critique.suggested_confidence
                matching_cls.risks.extend(critique.additional_risks)

        tools_used = list(self._get_tools().keys())
        return AgentResult(
            success=True,
            data={"critiques": critiques},
            reasoning=[
                f"Reviewed {len(state.classifications)} classifications "
                "using LLM self-critique",
                f"Applied {len(critiques)} critiques "
                "with enhanced safety reasoning",
                "Used learning tools to inform "
                f"{len([c for c in critiques if "learning"
                        in c.critique_reasoning.lower()])} decisions"
            ],
            metadata={
                "total_reviewed": len(state.classifications),
                "critiques_applied": len(critiques),
                "tools_used": tools_used,
                "autonomous_reflection": True
            }
        )

    async def _downgrade_confidence(
            self,
            path: str,
            level: str,
            reasoning: str) -> Dict:
        return ReflectionTools.downgrade_confidence(path, level, reasoning)

    def _finish_with_critiques(
            self,
            critiques: List[ReflectionCritique]) -> Dict:
        """
        Helper function used for the finish action that compiles critiques
        into final result format.
        """
        return {"critiques": critiques}

    def _format_context(self, state: AgentState) -> str:
        """
        Helper function used to include classifications in context.
        It overrides the `_format_context` function of the `ReActAgent`.
        """
        parts = []

        # Include basic context
        for key, value in state.context.items():
            parts.append(f"- {key}: {value}")

        # Include classifications to review
        if state.classifications:
            n = len(state.classifications)
            parts.append(f"\nClassifications to review ({n} total):")
            # Show first 10
            for i, item in enumerate(state.classifications[:10], 1):
                size_str = format_file_size(item.estimated_savings_bytes)
                parts.append(f"  {i}. {item.path} ({size_str}, "
                             f"{item.recommendation.value}, "
                             f"{item.confidence.value}) - "
                             f"{item.reasoning[:100]}...")
            if n > 10:
                parts.append(f"  ... and {n - 10} more classifications")

        return "\n".join(parts) if parts else "No context provided"

    async def _get_file_metadata(self, path: str) -> Dict:
        return ReflectionTools.get_file_metadata(path)

    def _get_tools(self) -> Dict[str, Callable]:
        """
        Helper function used to get the tools available to the reflection
        agent.
        """

        return {
            "get_file_metadata": self._get_file_metadata,
            "check_file_dependencies": self._check_file_dependencies,
            "search_related_patterns": self._search_related_patterns,
            "query_reflection_history": self._query_reflection_history,
            "analyze_reflection_accuracy_metrics":
            self._analyse_reflection_accuracy_metrics,
            "downgrade_confidence": self._downgrade_confidence,
            "add_safety_risk": self._add_safety_risk,
            "store_reflection_outcome": self._store_reflection_outcome,
            "trigger_reclassification": self._trigger_reclassification,
            "finish": self._finish_with_critiques
        }

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

    async def _query_reflection_history(self, path_pattern: str) -> Dict:
        return ReflectionTools.query_reflection_history(
            path_pattern=path_pattern,
            memory_store=self.memory_store)

    async def _search_related_patterns(self, criteria: str) -> Dict:
        return ReflectionTools.search_related_patterns(
            criteria=criteria,
            memory=self.memory_retrieval)

    async def _store_reflection_outcome(
            self,
            path: str,
            decision: str,
            reasoning: str,
            confidence_before: str,
            confidence_after: str) -> Dict:
        return ReflectionTools.store_reflection_outcome(
            path=path,
            decision=decision,
            reasoning=reasoning,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            memory_store=self.memory_store)

    async def _trigger_reclassification(
            self,
            path: str,
            context: str) -> Dict:
        return ReflectionTools.trigger_reclassification(
            path=path,
            context=context)
