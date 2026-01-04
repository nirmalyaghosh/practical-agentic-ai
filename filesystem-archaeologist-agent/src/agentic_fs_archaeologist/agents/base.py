from abc import ABC, abstractmethod
from inspect import signature
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
)

from openai import AsyncOpenAI

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.config import get_settings
from agentic_fs_archaeologist.agents.exceptions import AgentError
from agentic_fs_archaeologist.models import (
    AgentState,
    AgentResult,
)


logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents. It has common functions used by all
    agent subsclasses, as well as abstract execute function that the agent
    subsclasses must implement.
    """

    def __init__(self, model: Optional[str] = None):
        self.settings = get_settings()
        self.model = model or self.settings.model_name
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.max_iterations = self.settings.max_iterations
        self.temperature = self.settings.temperature

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentResult:
        """
        Execute the agent's task.

        This is the main entry point for agent execution; and implemented by
        each agent subsclass to contain its own logic.

        Args:
            state: Current agent state with context and data

        Returns:
            AgentResult with success status, data, and reasoning

        Raises:
            AgentError: If execution fails
        """
        pass

    def _build_system_prompt(self) -> str:
        """
        Helper function used to build the system prompt for this agent.

        Each agent should override this to provide its specific prompt.

        The default prompt string is "You are a helpful AI agent.".
        """
        return "You are a helpful AI agent."

    async def _call_llm(
        self,
        messages: list,
        response_format: Optional[Any] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        """
        Helper function used to make a call to the LLM.

        Args:
            messages: List of message dicts with role and content
            response_format: Optional Pydantic model for structured output
            temperature: Optional temperature override

        Returns:
            LLM response (parsed if response_format provided)

        Raises:
            AgentError: If LLM call fails
        """
        try:
            if self._is_client_initialized() is False:
                error_message = "LLM API client is not initialised"
                logger.error(error_message)
                raise AgentError(error_message)

            if response_format:
                response = await self.client.chat.completions.parse(
                    model=self.model,
                    messages=messages,
                    response_format=response_format,
                    temperature=temperature or self.temperature,
                )
                return response.choices[0].message.parsed
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature or self.temperature,
                )
                return response.choices[0].message.content
        except Exception as e:
            error_message = f"LLM call failed: {str(e)}"
            logger.exception(f"Caught exception : {error_message}")
            raise AgentError(error_message) from e

    def _format_reasoning_trace(self, reasoning: list) -> str:
        """
        Helper function used to format reasoning trace for result.

        Args:
            reasoning: List of reasoning strings

        Returns:
            Formatted reasoning string
        """
        if not reasoning:
            return "No reasoning trace available"
        return "\n".join(f"{i+1}. {r}" for i, r in enumerate(reasoning))

    def _is_client_initialized(self) -> bool:
        """
        Helper function used to check if AsyncOpenAI client is initialized
        and has a valid API key.
        """
        return (
            self.client is not None and
            hasattr(self.client, "api_key") and
            isinstance(self.client.api_key, str) and
            len(self.client.api_key.strip()) > 0
        )

    def __repr__(self) -> str:
        """
        Helper function used to return a string representation of the agent.
        """
        return f"{self.__class__.__name__}(model={self.model})"


class ToolBasedAgent(BaseAgent):
    """
    Base class for agents that use tools.

    This class extends `BaseAgent` class to add tool management capabilities,
    which is used by ReAct and other agents that need to execute
    actions/tools during their reasoning process.
    """

    @abstractmethod
    def _get_tools(self) -> Dict[str, Callable]:
        """
        Helper function used to get the tools available to this agent.

        Each tool-based agent must implement this to provide its
        specific set of tools.

        Returns:
            Dictionary mapping tool names to callable functions
        """
        pass

    async def _execute_tool(
        self,
        tool_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Helper function used to execute a tool by name with arguments.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool execution result as dictionary

        Raises:
            AgentError: If tool doesn't exist or execution fails
        """
        tools = self._get_tools()

        if tool_name not in tools:
            available = ", ".join(tools.keys())
            error_message = f"Tool '{tool_name}' not found. " +\
                            f"Available tools: {available}"
            logger.error(error_message)
            raise AgentError(error_message)

        try:
            result = await tools[tool_name](**kwargs)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            error_message = f"Tool '{tool_name}' execution failed: {str(e)}"
            logger.error(error_message)
            raise AgentError(error_message) from e

    def _get_tool_descriptions(self) -> str:
        """
        Helper function used to get the descriptions of available tools.

        Returns:
            Formatted string describing all available tools with parameters
        """
        tools = self._get_tools()
        descriptions = []

        for name, func in tools.items():
            # Get function signature
            try:
                sig = signature(func)
                params = []
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    # Format parameter with type hint if available
                    if param.annotation != param.empty:
                        type_str = param.annotation.__name__ \
                            if hasattr(param.annotation, '__name__') \
                            else str(param.annotation)
                    else:
                        type_str = "Any"

                    # Add default value if present
                    if param.default != param.empty:
                        params.append("{}: {} = {}".format(
                            param_name,
                            type_str,
                            param.default))
                    else:
                        params.append(f"{param_name}: {type_str}")

                signature_str = f"{name}({', '.join(params)})"
            except Exception:
                signature_str = f"{name}(...)"

            # Get first line of docstring
            doc = func.__doc__ or "No description available"
            first_line = doc.strip().split('\n')[0]

            descriptions.append(f"- {signature_str}: {first_line}")

        return "\n".join(descriptions)
