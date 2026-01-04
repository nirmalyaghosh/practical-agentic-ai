from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents.base import BaseAgent
from agentic_fs_archaeologist.agents.exceptions import PlanExecutionError
from agentic_fs_archaeologist.models import (
    AgentState,
    AgentResult,
    ExecutionPlan,
    PlanStep,
)


logger = get_logger(__name__)


class PlanAndExecuteAgent(BaseAgent):
    """
    Parent class of the agent subclasses which implement the
    Plan-and-Execute pattern.

    Plan-and-Execute separates planning (deciding what steps to take) from
    execution (actually taking those steps), allowing for dynamic planning
    and error handling.

    Core Phases:
        1. Plan: Generate sequence of steps
        2. Execute: Run steps in order
        3. Monitor: Track progress and errors
        4. Replan: Adjust plan if needed

    Agents extending this class must implement:
        - _create_plan(): Generate execution plan
        - _execute_step(): Execute a single plan step
        - _get_agent(): Get agent instance by name
    """

    async def _create_plan(self, state: AgentState) -> ExecutionPlan:
        """
        Helper function used to generate the execution plan using a language
        model. Each agent subclass must implement this function to create its
        own specific plan.

        Args:
            state: Current agent state

        Returns:
            ExecutionPlan with steps
        """
        raise NotImplementedError("Subclasses must implement _create_plan()")

    async def execute(self, state: AgentState) -> AgentResult:
        """
        Execute the agent's plan-and-execute workflow.

        Args:
            state: Current agent state

        Returns:
            AgentResult with complete workflow results

        Raises:
            PlanExecutionError: If planning or execution fails critically
        """
        try:
            # Phase 1: Create plan
            logger.debug("Creating the plan")
            plan = await self._create_plan(state)
            logger.debug("Created plan")

            # Phase 2: Execute plan
            logger.debug("Executing the plan")
            while not plan.is_complete:
                step = plan.next_step
                logger.debug(f"Step : {step}")
                if step is None:
                    break

                # Execute step
                step.status = "running"
                try:
                    result = await self._execute_step(step, state)
                    step.result = result
                    step.status = "completed" if result.success else "failed"

                    # Update state with results
                    state = self._update_state(state, step, result)

                except Exception as e:
                    step.status = "failed"
                    step.result = AgentResult(
                        success=False,
                        error=str(e)
                    )

                    # Decide whether to replan
                    if await self._should_replan(plan, step):
                        plan = await self._replan(state, plan, step)
                    else:
                        # Fatal error, stop execution
                        error_message = f"Step '{step.step_id}' failed fatally"
                        raise PlanExecutionError(error_message)

            return self._compile_results(state, plan)

        except Exception as e:
            return AgentResult(
                success=False,
                data=None,
                reasoning=["Plan-Execute workflow failed"],
                error=str(e)
            )

    async def _execute_step(
        self,
        step: PlanStep,
        state: AgentState
    ) -> AgentResult:
        """
        Helper function used to execute a single plan step.

        Subclasses must implement this to handle step execution.

        Args:
            step: Plan step to execute
            state: Current agent state

        Returns:
            AgentResult from step execution
        """
        raise NotImplementedError("Subclasses must implement _execute_step()")

    async def _replan(
        self,
        state: AgentState,
        old_plan: ExecutionPlan,
        failed_step: PlanStep
    ) -> ExecutionPlan:
        """
        Helper function ((used by an agent subclass)) to generate new plan
        given failure.

        Subclasses can override for custom replanning logic.

        Args:
            state: Current state
            old_plan: Previous plan
            failed_step: Step that failed

        Returns:
            New execution plan
        """
        # Default: create fresh plan, marking completed steps
        new_plan = await self._create_plan(state)

        # Mark previously completed steps as completed
        for old_step in old_plan.steps:
            if old_step.status == "completed":
                # Find corresponding step in new plan
                for new_step in new_plan.steps:
                    if new_step.step_id == old_step.step_id:
                        new_step.status = "completed"
                        new_step.result = old_step.result

        return new_plan

    async def _should_replan(
        self,
        plan: ExecutionPlan,
        failed_step: PlanStep
    ) -> bool:
        """
        Helper function (used by an agent subclass) to decide if it should
        replan after a failure.

        Default: replan if early step failed, fail if late step failed.
        Subclasses can override for custom logic.

        Args:
            plan: Current plan
            failed_step: Step that failed

        Returns:
            True if should replan, False otherwise
        """
        failed_index = plan.steps.index(failed_step)
        return failed_index < len(plan.steps) / 2

    def _update_state(
        self,
        state: AgentState,
        step: PlanStep,
        result: AgentResult
    ) -> AgentState:
        """
        Helper function used to update state based on step results.

        This function has a default implementation, and can be overriden by
        specific agent subclasses.

        Args:
            state: Current state
            step: Executed step
            result: Step result

        Returns:
            Updated agent state
        """
        # Store step result in state metadata
        if "step_results" not in state.metadata:
            state.metadata["step_results"] = {}
        state.metadata["step_results"][step.step_id] = result

        return state

    def _compile_results(
        self,
        state: AgentState,
        plan: ExecutionPlan
    ) -> AgentResult:
        """
        Helper function (used by an agent subclass) to compile final results
        from state and plan.

        Default implementation - subclasses can override.

        Args:
            state: Final agent state
            plan: Executed plan

        Returns:
            AgentResult with complete results
        """
        reasoning = []
        for step in plan.steps:
            status_symbol = "✓" if step.status == "completed" else "✗"
            reasoning.append(f"{status_symbol} {step.description}")

        return AgentResult(
            success=plan.is_complete,
            data=state.context,
            reasoning=reasoning,
            metadata={"plan": plan}
        )
