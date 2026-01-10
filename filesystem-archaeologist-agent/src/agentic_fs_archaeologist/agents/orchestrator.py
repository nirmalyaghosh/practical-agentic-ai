from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
)

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents.classifier import ClassifierAgent
from agentic_fs_archaeologist.agents.plan_execute_agent import (
    PlanAndExecuteAgent,
    PlanStep,
)
from agentic_fs_archaeologist.agents.reflection import ReflectionAgent
from agentic_fs_archaeologist.agents.scanner import ScannerAgent
from agentic_fs_archaeologist.agents.validator import ValidatorAgent
from agentic_fs_archaeologist.hitl import ApprovalGate
from agentic_fs_archaeologist.memory import (
    MemoryRetrieval,
    MemoryStore,
)
from agentic_fs_archaeologist.models import (
    AgentState,
    AgentResult,
    ExecutionPlan,
)
from agentic_fs_archaeologist.models.classification import Classification
from agentic_fs_archaeologist.models.base import (
    CleanupRecommendation,
    DeletionConfidence,
)
from agentic_fs_archaeologist.models.filesystem import FileMetadata


logger = get_logger(__name__)


class OrchestratorAgent(PlanAndExecuteAgent):
    """
    Orchestrates the cleanup workflow.
    """

    def __init__(self):
        super().__init__()
        self.discovery_agent = ScannerAgent()
        memory_retrieval = MemoryRetrieval(store=MemoryStore())
        self.classifier_agent = ClassifierAgent(memory=memory_retrieval)
        self.reflection_agent = ReflectionAgent()
        self.validator_agent = ValidatorAgent()
        self.approval_gate = ApprovalGate()

    async def _create_plan(self, state: AgentState) -> ExecutionPlan:
        """
        Create the execution plan for the cleanup workflow.

        Args:
            state: Current agent state

        Returns:
            ExecutionPlan with steps
        """
        # Create a basic plan
        # (with discovery, classification, reflection, and validation)
        steps = [
            PlanStep(
                step_id="discovery",
                description="Run discovery agent to find files",
                agent_name="DiscoveryAgent",
                status="pending"
            ),
            PlanStep(
                step_id="classification",
                description="Classify discovered files",
                agent_name="ClassifierAgent",
                status="pending"
            ),
            PlanStep(
                step_id="reflection",
                description="Reflect on classification results",
                agent_name="ReflectionAgent",
                status="pending"
            ),
            PlanStep(
                step_id="validation",
                description="Validate cleanup plan",
                agent_name="ValidatorAgent",
                status="pending"
            )
        ]

        return ExecutionPlan(steps=steps)

    async def _execute_step(
        self,
        step: PlanStep,
        state: AgentState
    ) -> AgentResult:
        """
        Execute a single plan step.

        Args:
            step: Plan step to execute
            state: Current agent state

        Returns:
            AgentResult from step execution
        """
        try:
            agent = self._get_agent(step.agent_name)
            result = await agent.execute(state)
            return result
        except KeyError:
            return AgentResult(
                success=False,
                error=f"Agent {step.agent_name} not found"
            )

    def _get_agent(self, agent_name: str):
        """
        Helper function used to get an instance of an agent based on the name.
        """
        agents = {
            "DiscoveryAgent": self.discovery_agent,
            "ClassifierAgent": self.classifier_agent,
            "ReflectionAgent": self.reflection_agent,
            "ValidatorAgent": self.validator_agent,
            "ApprovalGate": self.approval_gate,
        }
        return agents[agent_name]

    def _get_metadata(self, item: Dict[str, Any]) -> FileMetadata:
        """
        Helper function used to get the metadata.
        """
        path = Path(item["path"])
        size_mb = item.get("size_mb", 0)
        size_bytes = item.get("size_bytes", int(size_mb * 1024 * 1024))
        is_directory = item.get("is_directory", True)

        stat = path.stat() if path.exists() else None
        dt_now = datetime.now()

        # Get the file creation time
        # NOTE: (reference https://sicorps.com/) As of version 3.12,
        # `os.stat()` on Windows has deprecated the use of `st_ctime`. Instead,
        # you should start using the new `st_birthtime` attribute for file
        # creation time (which is what `st_ctime` used to be).
        dt_created = datetime.fromtimestamp(stat.st_birthtime) \
            if stat else dt_now

        dt_modified = datetime.fromtimestamp(stat.st_mtime) if stat else dt_now
        dt_accessed = datetime.fromtimestamp(stat.st_atime) if stat else dt_now
        metadata = FileMetadata(
            path=path,
            size_bytes=size_bytes,
            created_at=dt_created,
            modified_at=dt_modified,
            accessed_at=dt_accessed,
            is_directory=is_directory
        )
        return metadata

    def _update_state(
        self,
        state: AgentState,
        step: PlanStep,
        result: AgentResult
    ) -> AgentState:
        """
        Helper function used to update the state based on step results.
        """
        if result.data is None:
            logger.warning("No result.data")
            return state

        if step.agent_name == "DiscoveryAgent":
            discoveries = result.data.get("discoveries", [])
            for item in discoveries:
                try:
                    metadata = self._get_metadata(item=item)
                    state.discoveries.append(metadata)
                except Exception as e:
                    logger.warning("Failed to create FileMetadata for "
                                   f"{item.get('path')}: {e}")
        elif step.agent_name == "ClassifierAgent":
            classification_dicts = result.data.get("classifications", [])
            state.classifications.extend([
                Classification(
                    path=Path(cls["path"]),
                    recommendation=CleanupRecommendation(
                        cls["recommendation"].lower()),
                    confidence=DeletionConfidence(cls["category"].lower()),
                    reasoning=cls.get("reasoning", ""),
                    estimated_savings_bytes=cls.get("size_bytes", 0)
                )
                for cls in classification_dicts
            ])
        elif step.agent_name == "ReflectionAgent":
            state.critiques.extend(result.data.get("critiques", []))

        logger.debug(f"Updated state for {step.agent_name}: "
                     f"{len(state.discoveries)} discoveries")
        return state
