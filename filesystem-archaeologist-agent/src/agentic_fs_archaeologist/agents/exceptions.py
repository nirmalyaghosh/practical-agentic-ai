from agentic_fs_archaeologist.exceptions import BaseExceptionFSArchaeologist


class AgentError(BaseExceptionFSArchaeologist):
    """
    Base exception for agent execution errors.
    """
    pass


class LLMError(AgentError):
    """
    Used to indicate the error scenario where an error was encountered
    when communicating with the LLM API.
    """
    pass


class LLMRateLimitError(LLMError):
    """
    Used to indicate the error scenario where LLM API rate limit exceeded.
    """
    pass


class LLMTimeoutError(LLMError):
    """
    Used to indicate the error scenario where LLM API request timed out.
    """
    pass


class ReActLoopError(AgentError):
    """
    Used to indicate an error during ReAct loop execution.
    """
    pass


class InvalidActionError(ReActLoopError):
    """
    Used to indicate error when an agent attempted
    to use an invalid action/tool.
    """

    def __init__(self, action: str, available_actions: list):
        self.action = action
        self.available_actions = available_actions

        invalid_action_str = f"Invalid action '{action}'"
        available_actions_str = f"Available: {', '.join(available_actions)}"
        exception_message = f"{invalid_action_str}. {available_actions_str}"

        super().__init__(exception_message)


class MaxIterationsExceeded(ReActLoopError):
    """
    Used to indicate scenario where the ReAct loop exceeded maximum iterations.
    """

    def __init__(self, iterations: int, agent_name: str):
        self.iterations = iterations
        self.agent_name = agent_name
        super().__init__(
            f"{agent_name} exceeded maximum iterations ({iterations})"
        )


class PlanExecutionError(AgentError):
    """
    Used to indicate error during plan execution.
    """
    pass


class PlanStepFailed(PlanExecutionError):
    """
    Used to indicate error when a plan step failed to execute.
    """

    def __init__(self, step_id: str, error: str):
        self.step_id = step_id
        self.error = error
        exception_message = f"Step '{step_id}' failed: {error}"
        super().__init__(exception_message)
