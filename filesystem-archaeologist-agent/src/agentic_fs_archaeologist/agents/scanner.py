from typing import (
    Callable,
    Dict,
    List,
    Optional,
)

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.prompts.prompts import load_prompts
from agentic_fs_archaeologist.agents.react_agent import ReActAgent
from agentic_fs_archaeologist.models import (
    AgentState,
    AgentResult,
    ReActHistory,
)
from agentic_fs_archaeologist.tools import FileSystemTools


logger = get_logger(__name__)


class ScannerAgent(ReActAgent):
    """
    Scanner (Discovery) agent that explores filesystem using ReAct pattern.

    Agentic Aspects:
    - LLM selects tools (scan_directory, analyse_directory, finish)
    - LLM decides when exploration is complete

    Non-Agentic Aspects:
    - Follows prescriptive prompt with step-by-step instructions
    - Discovery strategy is guided, not autonomous
    - Size thresholds (>1GB) and patterns hardcoded in prompt
    """

    async def _analyse_directory(
            self, path: str, depth: Optional[int] = None) -> Dict:
        """
        Helper function used to analyse directory wrapper.
        """
        logger.debug(f"Analysing directory {path}")
        return FileSystemTools.analyse_directory(path=path, depth=depth)

    def _build_system_prompt(self) -> str:
        """
        Helper function used to build system prompt for scanner agent.
        """
        prompts = load_prompts(prompt_json_file_path=None)
        return prompts["scanner_agent"]["system_prompt"]

    async def _compile_results(
        self,
        history: ReActHistory,
        state: AgentState
    ) -> AgentResult:
        """
        Helper function used to compile discovery results.
        """
        # Find the finish observation
        findings = []
        for obs in history.observations:
            if obs.action == "finish":
                findings = obs.result.get("findings", [])
                break

        return AgentResult(
            success=True,
            data={"discoveries": findings},
            reasoning=self._extract_reasoning(history),
            metadata={"total_opportunities": len(findings)}
        )

    async def _finish(self, findings: List) -> Dict:
        """
        Helper function used to signal completion with findings.
        """
        n_findings = len(findings) if findings else 0
        return {
            "action": "finish",
            "findings": findings if findings else [],
            "total": n_findings,
        }

    def _get_tools(self) -> Dict[str, Callable]:
        """
        Helper function used to get the tools available to the scanner agent.
        """
        return {
            "scan_directory": self._scan_directory,
            "analyse_directory": self._analyse_directory,
            "finish": self._finish,
        }

    async def _scan_directory(
            self,
            path: str,
            min_size_mb: float = 100,
            depth: int = 2) -> Dict:
        """
        Helper function used to scan directory wrapper.
        """
        logger.debug(f"Scanning directory {path} with depth {depth}")
        return FileSystemTools.scan_directory(
            path=path,
            depth=depth,
            min_size_mb=min_size_mb)
