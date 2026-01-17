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

    def __init__(self):
        super().__init__()
        self.findings = []  # Accumulate partial results

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
        scanner_agent_prompt = prompts["scanner_agent"]
        if "system_prompt_lines" in scanner_agent_prompt:
            return "\n".join(scanner_agent_prompt["system_prompt_lines"])
        else:
            return scanner_agent_prompt["system_prompt"]

    async def _check_directory_changes(
        self,
        csv_file: str = "filesystem_monitor.csv"
    ) -> Dict:
        """
        Async helper function used for directory change analysis.
        """
        logger.debug(f"Checking directory changes from {csv_file}")
        return FileSystemTools.check_directory_changes(csv_file=csv_file)

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
                logger.debug("Found finish observation with "
                             f"{len(findings)} findings")
                logger.debug(f"Observation result keys: {obs.result.keys()}")
                break

        logger.debug(f"Returning discoveries: {len(findings)}")
        return AgentResult(
            success=True,
            data={"discoveries": findings},
            reasoning=self._extract_reasoning(history),
            metadata={"total_opportunities": len(findings)}
        )

    async def _extract_paths_from_scan(self, scan_result: Dict) -> List[str]:
        """
        Helper function used to extract paths from scan_directory result
        """
        if "items" not in scan_result:
            return []
        return [item["path"] for item in scan_result["items"]]

    async def _finish(
        self,
        findings: Optional[List] = None,
        items: Optional[List] = None
    ) -> Dict:
        """
        Helper function used to signal completion with findings.
        Accepts either 'findings' or 'items' parameter for flexibility.
        """
        # Handle both 'findings' and 'items' parameters
        result_list = findings if findings is not None else items
        if result_list is None:
            result_list = []

        n_findings = len(result_list)
        return {
            "action": "finish",
            "findings": result_list,
            "total": n_findings,
        }

    async def _get_disk_usage(self, path: str = "~") -> Dict:
        """
        Async helper function used for disk usage monitoring.
        """
        logger.debug(f"Getting disk usage for {path}")
        return FileSystemTools.get_disk_usage(path=path)

    async def _get_recycle_bin_stats(self) -> Dict:
        """
        Async helper function used for recycle bin statistics.
        """
        logger.debug("Getting recycle bin statistics")
        return FileSystemTools.get_recycle_bin_stats()

    def _get_tools(self) -> Dict[str, Callable]:
        """
        Helper function used to get the tools available to the scanner agent.
        """
        return {
            "get_disk_usage": self._get_disk_usage,
            "get_recycle_bin_stats": self._get_recycle_bin_stats,
            "check_directory_changes": self._check_directory_changes,
            "scan_directory": self._scan_directory,
            "select_random_unvisited_directory":
            self._select_random_unvisited_directory,
            "analyse_directory": self._analyse_directory,
            "update_scanned_paths": self._update_scanned_paths,
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

        result = FileSystemTools.scan_directory(
            path=path,
            depth=depth,
            min_size_mb=min_size_mb)

        # Accumulate findings as discovered
        if "items" in result:
            self.findings.extend(result["items"])
            # Auto-update CSV with discovered paths
            paths_found = [item["path"] for item in result["items"]]
            if paths_found:
                await self._update_scanned_paths(paths_found)

        return result

    async def _select_random_unvisited_directory(self) -> Dict:
        """
        Async helper function used to select a random unvisited directory
        from the CSV.
        """
        return FileSystemTools.select_random_unvisited_directory(
            csv_file="filesystem_monitor.csv")

    async def _update_scanned_paths(self, paths: List[str]) -> Dict:
        """
        Async helper function used to update CSV to mark paths as visited
        """
        return FileSystemTools.update_scanned_paths(
            csv_file="filesystem_monitor.csv",
            paths=paths)
