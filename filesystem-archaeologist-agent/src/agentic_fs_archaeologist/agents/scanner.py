import time

from typing import (
    Callable,
    Dict,
    List,
    Optional,
)

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.config import get_settings
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
    """

    def __init__(self):
        super().__init__()
        self.findings = []  # Accumulate partial results
        settings = get_settings()
        self.scan_threshold_mb = settings.scan_min_size_mb

    async def _analyse_directory(
            self, path: str, depth: Optional[int] = None) -> Dict:
        """
        Helper function used to analyse directory wrapper.
        """
        logger.debug(f"Analysing directory {path}")
        return FileSystemTools.analyse_directory(path=path, depth=depth)

    def _build_react_prompt(
            self,
            state: AgentState,
            history: ReActHistory) -> str:

        # Build context from state using base class method
        context_str = self._format_context(state=state)

        # Build history using base class method
        history_str = self._format_history(history=history)\
            if history.thoughts else ""

        # Get the JSON formatting rules
        json_formatting_rules = self._get_json_formatting_rules()

        prompts = load_prompts(prompt_json_file_path=None)
        k = "react_prompt_lines"
        prompt_lines = prompts["scanner_agent"].get(k, [])

        # Join the lines and format the template
        template = "\n".join(prompt_lines)
        formatted_prompt = template.format(
            context_str=context_str,
            history_str=history_str,
            json_formatting_rules=json_formatting_rules
        )

        return formatted_prompt

    def _build_system_prompt(self) -> str:
        """
        Helper function used to build system prompt for scanner agent.
        """
        prompts = load_prompts(prompt_json_file_path=None)
        scanner_agent_prompt = prompts["scanner_agent"]
        if "system_prompt_lines" in scanner_agent_prompt:
            lines = scanner_agent_prompt["system_prompt_lines"]
            prompt_text = "\n".join(lines)
            prompt_text = prompt_text.replace(">1GB",
                                              f">{self.scan_threshold_mb}MB")
        else:
            prompt_text = scanner_agent_prompt["system_prompt"]

        return prompt_text

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
        disk_usage = FileSystemTools.get_disk_usage(path=path)
        self._monitoring_data_collected = time.time()
        return disk_usage

    async def _get_recycle_bin_stats(self) -> Dict:
        """
        Async helper function used for recycle bin statistics.
        """
        logger.debug("Getting recycle bin statistics")
        return FileSystemTools.get_recycle_bin_stats()

    def _get_tools(self) -> Dict[str, Callable]:
        """
        Helper function used to get the tools available to the scanner agent.
        This function will dynamically filter tools based on execution state
        to optimise agent performance:
        - Base tools always available for core scanning workflow
        - Monitoring tools only available if data collection is needed
        - Analysis tools only available after successful scanning operations
        """

        base_tools = {
            "select_random_unvisited_directory":
            self._select_random_unvisited_directory,
            "scan_directory": self._scan_directory,
            "finish": self._finish,
        }
        tools = {}
        tools.update(base_tools)

        # Add monitoring tools only if needed
        # (check once in 30 minutes)
        min_interval_secs = 1800
        if self._needs_monitoring_data(min_interval_secs=min_interval_secs):
            tools.update({
                "get_disk_usage": self._get_disk_usage,
                "get_recycle_bin_stats": self._get_recycle_bin_stats,
                "check_directory_changes": self._check_directory_changes,
            })

        # Add analysis tools only if scanning occurred
        if self._has_scan_results():
            tools.update({
                "analyse_directory": self._analyse_directory,
            })

        # Check and log the number of tolls used
        num_tools = len(tools) if tools else 0
        if len(tools) < 4:
            logger.debug("Using base tools - optimal")
        else:
            logger.debug(f"Using {num_tools} tools")

        return tools

    def _has_scan_results(self) -> bool:
        """
        Helper function used to check if scanning has produced results for
        analysis.
        """
        return bool(self.findings)

    def _needs_monitoring_data(self, min_interval_secs: int) -> bool:
        """
        Helper function used to check if monitoring data is still needed.
        """
        return not hasattr(self, "_monitoring_data_collected") or \
            time.time() - self._monitoring_data_collected > min_interval_secs

    async def _scan_directory(
            self,
            path: str,
            depth: int = 2) -> Dict:
        """
        Helper function used to scan directory wrapper.
        """
        logger.debug(f"Scanning directory {path} with depth {depth}")

        result = FileSystemTools.scan_directory(
            path=path,
            depth=depth,
            min_size_mb=self.scan_threshold_mb)

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
