import json
import re

from datetime import datetime
from typing import List

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents.base import ToolBasedAgent
from agentic_fs_archaeologist.agents.exceptions import (
    InvalidActionError,
    MaxIterationsExceeded,
)
from agentic_fs_archaeologist.models import (
    AgentState,
    AgentResult,
    ReActThought,
    ReActObservation,
    ReActHistory,
)


logger = get_logger(__name__)


class ReActAgent(ToolBasedAgent):
    """
    Parent class of the agent subclasses which implement the ReAct
    (Reasoning + Acting) pattern.

    ReAct interleaves reasoning (thinking about what to do) with acting
    (executing actions), using observations from actions to inform subsequent
    reasoning.

    Core Loop:
        1. Thought: Reason about current situation
        2. Action: Decide what action to take
        3. Observation: Observe result of action
        4. Repeat until done

    Agents extending this class must implement:
        - _get_tools(): Provide available tools
        - _compile_results(): Convert history to final result
    """

    def _build_react_prompt(
        self,
        state: AgentState,
        history: ReActHistory
    ) -> str:
        """
        Helper function (used by an agent subclass) to build a prompt for
        ReAct iteration.

        Args:
            state: Current agent state
            history: ReAct history so far

        Returns:
            Prompt string
        """
        # Build context from state
        context_str = self._format_context(state)

        # Build history
        history_str = self._format_history(history)

        # Build tool descriptions
        tools_str = self._get_tool_descriptions()

        prompt = f"""Context:
{context_str}

Available Tools:
{tools_str}

Previous Reasoning:
{history_str if history_str else "None - this is the first iteration"}

Based on the above, reason about what to do next. Think step-by-step.

If you have enough information to finish, set should_continue to false.
Otherwise, choose an action and provide the required inputs as a JSON string.

CRITICAL JSON FORMATTING RULES for action_input:
1. MUST be valid JSON - use double quotes for keys and string values
2. NO trailing commas anywhere
3. NO empty strings followed by commas (e.g., "","  is INVALID)
4. For Windows paths, use forward slashes OR escape backslashes
5. Close all braces and brackets properly

Valid Examples:
- Single param: '{{"path": "C:/Users/user/Downloads"}}'
- Multiple params: '{{"path": "/tmp", "size_bytes": 1000,
                      "is_directory": true}}'
- No params needed: leave action_input empty or use '{{}}'

INVALID (will cause errors):
- '{{"path": "C:\\Users",}}' (trailing comma)
- '{{"path": "",}}' (empty string with comma)
- '{{"path": value}}' (unquoted string value)
"""
        return prompt

    async def _compile_results(
        self,
        history: ReActHistory,
        state: AgentState
    ) -> AgentResult:
        """
        Helper function (used by an agent subclass) to cmpile ReAct history
        into the final result. This function needs to be implemented by the
        agent subclasses to extract their specific results from the
        ReAct history.

        Args:
            history: Complete ReAct history
            state: Current agent state

        Returns:
            AgentResult with success and data
        """
        raise NotImplementedError(
            "Subclasses must implement _compile_results()"
        )

    async def execute(self, state: AgentState) -> AgentResult:
        """
        USed to execute the ReAct loop.

        Args:
            state: Current agent state

        Returns:
            AgentResult with discoveries/classifications and reasoning trace

        Raises:
            MaxIterationsExceeded: If loop exceeds max iterations
            InvalidActionError: If agent tries to use invalid tool
        """
        history = ReActHistory()

        try:
            m = self.max_iterations
            for iteration in range(self.max_iterations):
                logger.debug(f"Working on iteration #{iteration + 1} of {m}")

                # 1. REASON - Get next thought from LLM
                thought = await self._get_thought(
                    state=state,
                    history=history)
                history.thoughts.append(thought)

                # 2. Check if done
                if (not thought.should_continue or
                        thought.action is None or
                        thought.action == "null"):
                    history.final_answer = thought.thought
                    break

                # 3. Validate action exists
                if thought.action not in self._get_tools():
                    raise InvalidActionError(
                        thought.action,
                        list(self._get_tools().keys())
                    )

                # 4. ACT - Execute the chosen action
                observation = await self._execute_action(thought)
                history.observations.append(observation)

            else:
                # Loop completed without finishing
                raise MaxIterationsExceeded(
                    iterations=self.max_iterations,
                    agent_name=self.__class__.__name__)

            # Compile final results
            return await self._compile_results(history, state)

        except Exception as e:
            logger.exception(f"Caught exception: {str(e)}")
            return AgentResult(
                success=False,
                data=None,
                reasoning=self._extract_reasoning(history),
                error=str(e)
            )

    async def _execute_action(
        self,
        thought: ReActThought
    ) -> ReActObservation:
        """
        Helper function (used by an agent subclass) to execute an action
        and return observation.

        Args:
            thought: `ReActThought` containing action and inputs. If it does
            not have the `action`, an `InvalidActionError` will be raised.

        Returns:
            ReActObservation with action result
        """
        if thought.action is None:
            logger.error("Action should not be None")
            raise InvalidActionError("None", list(self._get_tools().keys()))

        # Parse action_input from JSON string
        action_input = {}
        if thought.action_input:
            # Log raw action_input for debugging
            logger.debug(
                "Raw action_input from LLM: "
                f"{repr(thought.action_input)}"
            )

            sanitized_input = thought.action_input
            try:
                # Additional JSON sanitization for common LLM formatting errors

                # 1. Remove leading/trailing whitespace
                sanitized_input = sanitized_input.strip()

                # 2. Escape backslashes in Windows paths
                sanitized_input = sanitized_input.replace("\\", "\\\\")

                # 3. Remove multiple consecutive commas
                sanitized_input = re.sub(r",+", ",", sanitized_input)

                # 4. Remove trailing commas before closing brackets/braces
                sanitized_input = re.sub(
                    r",(\s*[}\]])", r"\1", sanitized_input
                )

                # 5. Fix empty string followed by comma: "",  -> ""
                sanitized_input = re.sub(r'""(\s*),', r'""', sanitized_input)

                # 6. Remove commas after closing braces/brackets
                sanitized_input = re.sub(r"([}\]])(\s*),", r"\1",
                                         sanitized_input)

                # 7. Normalize whitespace around colons and commas
                sanitized_input = re.sub(r"\s*:\s*", ": ", sanitized_input)
                sanitized_input = re.sub(r"\s*,\s*", ", ", sanitized_input)

                logger.debug(
                    "Sanitized action_input: "
                    f"{repr(sanitized_input)}"
                )

                # Parse the sanitized JSON
                action_input = json.loads(sanitized_input)
                logger.debug("Successfully parsed action_input: "
                             f"{action_input}")

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse action_input after sanitization. "
                    f"Original: {repr(thought.action_input)}. "
                    f"Sanitized: {repr(sanitized_input)}. "
                    f"Error: {e}. Attempting fallback parsing..."
                )
                # Fallback: try to extract key-value pairs manually
                try:
                    # Enhanced regex-based extraction for common patterns
                    action_input = {}

                    # Extract "key": "value" or "key": number or "key": boolean
                    pattern = (
                        r'"(\w+)"\s*:\s*("(?:[^"\\]|\\.)*"|\d+\.?\d*|'
                        'true|false|null)'
                    )
                    matches = re.findall(pattern, thought.action_input)

                    for key, value in matches:
                        # Try to parse the value
                        try:
                            action_input[key] = json.loads(value)
                        except json.JSONDecodeError:
                            # Strip quotes and use as string
                            action_input[key] = value.strip('"')

                    logger.info(
                        "Fallback parsing extracted: "
                        f"{action_input}"
                    )

                    if not action_input:
                        logger.error(
                            f"Fallback parsing produced empty result. "
                            f"Raw input: {repr(thought.action_input)}"
                        )

                except Exception as fallback_error:
                    logger.error(
                        f"Fallback parsing also failed: {fallback_error}. "
                        f"Raw input: {repr(thought.action_input)}"
                    )

        # Executing a tool
        tool_to_execute = thought.action
        logger.debug(
            f"Executing tool '{tool_to_execute}' "
            f"with inputs: {action_input}"
        )
        result = await self._execute_tool(
            tool_name=tool_to_execute,
            **action_input
        )

        return ReActObservation(
            action=thought.action,
            result=result,
            timestamp=datetime.now()
        )

    def _extract_reasoning(self, history: ReActHistory) -> List[str]:
        """
        Helper function (used by an agent subclass) to extract reasoning trace
        from history.

        Args:
            history: ReAct history

        Returns:
            List of reasoning strings
        """
        reasoning = []
        for i, thought in enumerate(history.thoughts):
            reasoning.append(f"Iteration {i+1}: {thought.thought}")
        return reasoning

    def _format_context(self, state: AgentState) -> str:
        """
        Helper function (used by an agent subclass) to format agent state
        context for prompt.

        Args:
            state: Agent state

        Returns:
            Formatted context string
        """
        parts = []
        for key, value in state.context.items():
            parts.append(f"- {key}: {value}")
        return "\n".join(parts) if parts else "No context provided"

    def _format_history(self, history: ReActHistory) -> str:
        """
        Helper function (used by an agent subclass) to format ReAct history
        for the prompt.

        Args:
            history: ReAct history

        Returns:
            Formatted history string
        """
        if not history.thoughts:
            return ""

        parts = []
        thoughts_observations = zip(history.thoughts, history.observations)
        for i, (thought, obs) in enumerate(thoughts_observations):
            parts.append(f"\nIteration {i+1}:")
            parts.append(f"  Thought: {thought.thought}")
            if thought.action:
                act_str = f"  Action: {thought.action}({thought.action_input})"
                parts.append(act_str)
                parts.append(f"  Observation: {obs.result}")

        return "\n".join(parts)

    async def _get_thought(
        self,
        state: AgentState,
        history: ReActHistory
    ) -> ReActThought:
        """
        Helper function (used by an agent subclass) to get next thought using
        a language model.

        Args:
            state: Current agent state
            history: ReAct history so far

        Returns:
            ReActThought with reasoning and action
        """
        prompt = self._build_react_prompt(state, history)

        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        thought = await self._call_llm(
            messages=messages,
            response_format=ReActThought,
        )

        # Log the parsed thought for debugging
        logger.debug(
            f"LLM returned ReActThought: "
            f"action={thought.action}, "
            f"action_input={repr(thought.action_input)}, "
            f"should_continue={thought.should_continue}"
        )

        return thought
