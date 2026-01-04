from datetime import datetime
from typing import (
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from agentic_fs_archaeologist.models.agent import AgentResult


class PlanStep(BaseModel):
    """
    Pydantic data model used for a single step in an execution plan.
    """
    step_id: str
    agent_name: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[AgentResult] = None


class ExecutionPlan(BaseModel):
    """
    Pydantic data model used for a plan for executing the cleanup workflow.
    """
    steps: List[PlanStep]
    created_at: datetime = Field(default_factory=datetime.now)
    current_step_index: int = 0

    @property
    def is_complete(self) -> bool:
        """
        Helper function used to check if all steps are completed.
        """
        return all(step.status == "completed" for step in self.steps)

    @property
    def next_step(self) -> Optional[PlanStep]:
        """
        Helper function used to get the next pending step.
        """
        for step in self.steps:
            if step.status == "pending":
                return step
        return None
