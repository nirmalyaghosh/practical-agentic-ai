import subprocess
import time

from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
)

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents.react_agent import ReActAgent
from agentic_fs_archaeologist.config import get_settings
from agentic_fs_archaeologist.memory import MemoryRetrieval
from agentic_fs_archaeologist.models import (
    AgentState,
    AgentResult,
    ReActHistory,
)
from agentic_fs_archaeologist.prompts.prompts import load_prompts
from agentic_fs_archaeologist.tools import FileSystemTools
from agentic_fs_archaeologist.utils.file_utils import format_file_size


logger = get_logger(__name__)


class ClassifierAgent(ReActAgent):
    """
    Classifier using ReAct pattern for tool orchestration + Memory +
    contextual reasoning.

    Agentic Aspects:
    - Model orchestrates tool calls (such as `classify_item_using_llm`,
      `check_dependencies`, etc.)
    - Model decides when to query memory for similar past decisions
    - Analyzes deletion safety considering purpose, dependencies,
      and recoverability
    - Makes contextual classification decisions
      (SAFE/LIKELY_SAFE/UNCERTAIN/UNSAFE)

    Non-Agentic Aspects (by design):
    - Fallback pattern matching for error cases
    - Tool implementations remain deterministic

    Uses language model as both orchestrator AND decision-maker.
    """

    def __init__(self, memory: MemoryRetrieval):
        super().__init__()
        self.memory = memory
        settings = get_settings()
        self.session_cache = {}
        self.cache_ttl = settings.classifier_cache_ttl
        self.classifications = []  # Store intermediate results

    def _build_system_prompt(self) -> str:
        prompts = load_prompts(prompt_json_file_path=None)
        classifier_agent_prompt = prompts["classifier_agent"]
        if "system_prompt_lines" in classifier_agent_prompt:
            return "\n".join(classifier_agent_prompt["system_prompt_lines"])
        else:
            return classifier_agent_prompt["system_prompt"]

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

    async def _classify_item_fallback(
            self,
            path: str,
            size_bytes: int,
            is_directory: bool) -> Dict:
        """
        Helper function used as a fallback to use deterministic pattern
        to classify an item.

        This is the original classification logic, kept as a safety net
        when classification using language models fails.
        """
        target = Path(path)

        # Deterministic pattern matching (not LLM-driven)
        item_type = None
        dir_type = None
        recommendation = "keep"

        if is_directory:
            name = target.name.lower()
            if name == "node_modules":
                dir_type = "node_modules"
                recommendation = "review"
            elif name in ["venv", ".venv", "env"]:
                dir_type = "venv"
                recommendation = "review"
            elif "cache" in name:
                dir_type = "cache_dir"
                recommendation = "review"
            elif name in ["build", "dist", "target", ".next"]:
                dir_type = "build_dir"
                recommendation = "review"
        else:
            ext = target.suffix.lower()
            if ext in [".dmg", ".pkg", ".exe"]:
                item_type = "old_download"
                recommendation = "review"
            elif ext == ".log":
                item_type = "log_file"
                recommendation = "review"

        # Check age
        age_info = FileSystemTools.get_file_age(path)
        age_days = age_info.get("age_days", 0)

        # Return
        xpl = "Fallback pattern matching used since LLM classification failed."
        return {
            "path": path,
            "size_bytes": size_bytes,
            "size_gb": size_bytes / (1024**3),
            "is_directory": is_directory,
            "type": dir_type or item_type or "other",
            "category": "UNCERTAIN",
            "confidence": "LOW",
            "reasoning": xpl,
            "age_days": age_days,
            "recommendation": recommendation,
        }

    async def _classify_item_using_llm(
            self,
            path: str,
            size_bytes: int = 0,
            is_directory: bool = False) -> Dict:
        """
        Classify an item and store the result in self.classifications.
        """
        result = await self._do_classification(path, size_bytes, is_directory)
        self.classifications.append(result)
        return result

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

        # If no finish observation found, use accumulated classifications
        if not classifications:
            classifications = self.classifications
            logger.debug("Using accumulated classifications: "
                         f"{len(classifications)}")

        return AgentResult(
            success=True,
            data={"classifications": classifications},
            reasoning=self._extract_reasoning(history),
            metadata={"total_classified": len(classifications)}
        )

    async def _do_classification(
            self,
            path: str,
            size_bytes: int = 0,
            is_directory: bool = False) -> Dict:
        """
        Helper function used for classification (using language model) with
        contextual analysis of deletion safety.

        It uses language model inference to analyze the item considering:
        - Purpose (system, cache, user data, build artifacts)
        - Dependencies (symlinks, active processes)
        - Recoverability (can it be regenerated?)

        Returns classification with reasoning.
        Falls back to pattern matching on error.
        """
        try:
            logger.debug(f"Classifying {path}: size_bytes={size_bytes}, "
                         f"is_directory={is_directory}")

            # Check for and correct LLM parameter parsing errors
            # LLM sometimes incorrectly sets is_directory=True
            # for files with extensions
            is_directory_corrected = False
            if is_directory and Path(path).suffix:
                logger.debug("Correcting is_directory from True to False "
                             f"for {path} (has file extension)")
                is_directory = False
                is_directory_corrected = True
                # Clear cached result from incorrect
                # is_directory=True classification
                if path in self.session_cache:
                    logger.debug(f"Clearing cached result for {path} "
                                 "due to is_directory correction")
                    del self.session_cache[path]

            # If size_bytes is 0 or missing, try to get it from filesystem
            if size_bytes == 0:
                size_bytes = self._get_file_size(path=path)
                logger.debug(f"File {path}: size_bytes={size_bytes}")

            # Check cache first
            ts = self.session_cache[path]["timestamp"] \
                if path in self.session_cache else None
            if (path in self.session_cache and ts is not None and
                is_directory_corrected is False and
               (time.time() - ts) < self.cache_ttl):
                logger.info(f"Cache hit for {path}")
                return self.session_cache[path]["result"]

            # Fix any drive letter with space after colon
            if ": " in path:
                path = path.replace(": ", ":/", 1)

            # Get age information
            age_info = FileSystemTools.get_file_age(path)
            age_days = age_info.get("age_days", 0)

            # Get memory context
            memory_context = ""
            similar = await self.memory.find_similar(Path(path))
            if similar:
                avg_approval = (
                    sum(e.approval_rate for e in similar) / len(similar)
                )
                memory_context = (
                    f"\nPast user decisions for similar items:\n"
                    f"- {len(similar)} similar patterns found\n"
                    f"- Average approval rate: {avg_approval:.1%}\n"
                )
                for entry in similar[:3]:
                    memory_context += (
                        f"- {entry.path_pattern}: "
                        f"{entry.user_decision.value} "
                        f"({entry.approval_rate:.1%} approval)\n"
                    )

            # Build the prompt
            prompts = load_prompts(prompt_json_file_path=None)
            prompt_template = prompts["llm_classification"]["template"]

            item_type = "directory" if is_directory else "file"
            size_str = format_file_size(bytes_size=size_bytes)

            prompt = prompt_template.format(
                path=path,
                size_gb=size_str,
                age_days=age_days,
                item_type=item_type,
                memory_context=memory_context if memory_context else
                "No similar past decisions found."
            )

            # Call LLM for classification
            messages = [
                {"role": "system",
                 "content": (
                    "You are a filesystem safety analyst. "
                    "Analyze items and classify deletion safety."
                 )},
                {"role": "user", "content": prompt}
            ]
            response = await self._call_llm(
                messages=messages,
                temperature=self.temperature)

            # Parse LLM response
            content = response

            # Extract recommendation
            recommendation = "KEEP"
            recommendations = ["DELETE", "REVIEW", "KEEP"]
            for rec in recommendations:
                if f"Recommendation: {rec}" in content or \
                   f"recommendation: {rec.lower()}" in content.lower():
                    recommendation = rec.lower()
                    break

            # Extract category
            category = "UNCERTAIN"
            categories = ["SAFE", "LIKELY_SAFE", "UNCERTAIN", "UNSAFE"]
            for cat in categories:
                if cat in content.upper():
                    category = cat
                    break

            # Extract confidence
            confidence = "MEDIUM"
            for conf in ["HIGH", "MEDIUM", "LOW"]:
                if conf in content.upper():
                    confidence = conf
                    break

            # Extract reasoning (everything after "Reasoning:")
            reasoning = content
            if "Reasoning:" in content:
                reasoning = content.split("Reasoning:", 1)[1].strip()
            elif "reasoning:" in content.lower():
                idx = content.lower().find("reasoning:")
                reasoning = content[idx + 10:].strip()

            classification_dict = {
                "path": path,
                "size_bytes": size_bytes,
                "is_directory": is_directory,
                "age_days": age_days,
                "recommendation": recommendation,
                "category": category,
                "confidence": confidence,
                "reasoning": reasoning,
                "method": "llm"
            }

            # Store in cache
            self.session_cache[path] = {
                "result": classification_dict,
                "timestamp": time.time()
            }

            # Clean expired entries
            self.session_cache = {
                k: v for k, v in self.session_cache.items()
                if time.time() - v["timestamp"] < self.cache_ttl
            }

            return classification_dict

        except Exception as e:
            logger.warning(
                f"Classification (using language model) failed for {path}: "
                f"{e}. Falling back to pattern matching."
            )
            # Fallback to deterministic classification
            result = await self._classify_item_fallback(
                path, size_bytes, is_directory
            )
            result["method"] = "fallback"
            return result

    async def execute(self, state: AgentState) -> AgentResult:
        """
        Used to store the state for tools to access.
        """
        self._current_state = state
        return await super().execute(state)

    async def _finish(
        self,
        classifications: Optional[list] = None,
        items: Optional[list] = None
    ) -> Dict:
        """
        Helper function used to signal completion with classifications.
        Accepts either 'classifications' or 'items' parameter for flexibility.
        """
        result_list = (
            classifications if classifications is not None else items
        )
        if result_list is None:
            result_list = []

        return {
            "action": "finish",
            "classifications": result_list,
            "total": len(result_list),
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
                size_str = format_file_size(item.size_bytes)
                parts.append(f"  {i}. {item.path} ({size_str}, "
                             f"{'dir' if item.is_directory else 'file'})")
            if n > 10:
                parts.append(f"  ... and {n - 10} more items")

        return "\n".join(parts) if parts else "No context provided"

    def _get_file_size(self, path: str) -> int:
        size_bytes = 0
        try:
            target = Path(path).expanduser().resolve()
            if target.exists():
                if target.is_file():
                    size_bytes = target.stat().st_size
                else:
                    size_bytes = FileSystemTools._get_dir_size(target)
                logger.debug("Got size from filesystem: "
                             f"{size_bytes} bytes")
        except Exception as e:
            logger.warning("Could not get size from filesystem "
                           f"for {path}: {e}")
        return size_bytes

    async def _get_items_to_classify(self) -> Dict:
        """
        Helper function used to retrieve the list of items from state.
        Refer to the `execute()` function.
        """
        # This will be set when the agent runs
        if not hasattr(self, "_current_state"):
            return {"items": [], "count": 0}

        items_list = []
        for item in self._current_state.discoveries:
            items_list.append({
                "path": str(item.path),
                "size_bytes": item.size_bytes,
                "is_directory": item.is_directory,
                "size_gb": item.size_gb
            })

        return {
            "items": items_list,
            "count": len(items_list)
        }

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
        """
        Helper function to get the tools. Note that the sequence matters.
        """
        return {
            "get_items_to_classify": self._get_items_to_classify,
            "classify_item_using_llm": self._classify_item_using_llm,
            "classify_item_fallback": self._classify_item_fallback,
            "check_git_status": self._check_git_status,
            "query_similar_decisions": self._query_similar_decisions,
            "check_dependencies": self._check_dependencies,
            "finish": self._finish,
        }
