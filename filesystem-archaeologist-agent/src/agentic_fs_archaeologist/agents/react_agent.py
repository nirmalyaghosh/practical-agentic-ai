import json
import re

from datetime import datetime
from typing import List

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents.base import ToolBasedAgent
from agentic_fs_archaeologist.agents.exceptions import (
    InvalidActionError,
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

You can execute single actions OR action sequences for efficiency:

Single Action (legacy):
{{"action": "scan_directory", "action_input": "{{\\"path\\": \\"/tmp\\"}}"}}

Action Sequence (recommended for related operations):
{{"actions": [
  {{"action": "scan_directory", "action_input": "{{\\"path\\": \\"/tmp\\"}}"}},
  {{"action": "analyse_directory", "action_input": "{{\\"path\\": \\"/tmp\\"}}"}}
]}}

Use sequences when multiple related tools should execute together.

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

                # Clean up action name - remove trailing parentheses if present
                if thought.action and thought.action.endswith("()"):
                    thought.action = thought.action[:-2]

                history.thoughts.append(thought)

                # 2. Check if done
                # - but execute finish action first if specified
                if not thought.should_continue:
                    # If action is not specified but action_input has data,
                    # assume it's meant for "finish" action
                    if (thought.action is None or thought.action == "null") \
                            and thought.action_input:
                        thought.action = "finish"

                    if thought.action and thought.action != "null":
                        # Execute final action (e.g., finish) before breaking
                        if thought.action not in self._get_tools():
                            raise InvalidActionError(
                                thought.action,
                                list(self._get_tools().keys())
                            )
                        observation = await self._execute_action(thought)
                        history.observations.append(observation)
                    history.final_answer = thought.thought
                    break

                if thought.action is None or thought.action == "null":
                    history.final_answer = thought.thought
                    break

                # Batch Action Sequences optimisation
                # Executes multiple related tools per reasoning step instead
                # of one tool call per iteration. This will help to improve
                # efficiency for agents like ScannerAgent that perform related
                # operations

                # 3. ACT - Execute actions (single or batch)
                if thought.actions:
                    # Execute action sequence
                    for action_spec in thought.actions:
                        action_name = action_spec.get("action")
                        action_input_json =\
                            action_spec.get("action_input", "{}")

                        if action_name is None \
                                or action_name not in self._get_tools():
                            available_actions = list(self._get_tools().keys())
                            raise InvalidActionError(
                                action=action_name,
                                available_actions=available_actions)

                        # Create temporary thought for this action
                        temp_thought = ReActThought(
                            thought=f"Executing {action_name} from batch",
                            action=action_name,
                            action_input=action_input_json,
                            should_continue=True
                        )

                        try:
                            observation = await self._execute_action(
                                thought=temp_thought)
                            history.observations.append(observation)
                        except Exception as e:
                            error_observation = ReActObservation(
                                action=action_name,
                                result={
                                    "error":
                                    f"Batch action failed: {str(e)}"
                                },
                                timestamp=datetime.now()
                            )
                            history.observations.append(error_observation)
                            w = f"Batch action '{action_name}' failed: {e}"
                            logger.warning(w)

                elif thought.action and thought.action != "null":
                    # Legacy single action execution
                    if thought.action not in self._get_tools():
                        raise InvalidActionError(
                            thought.action,
                            list(self._get_tools().keys())
                        )

                    try:
                        observation = await self._execute_action(thought)
                        history.observations.append(observation)
                    except Exception as e:
                        # Add error observation so ReAct can learn and adapt
                        error_observation = ReActObservation(
                            action=thought.action,
                            result={
                                "error": f"Tool execution failed: {str(e)}"
                            },
                            timestamp=datetime.now()
                        )
                        history.observations.append(error_observation)
                        logger.warning(f"Tool '{thought.action}' failed: {e}")
                        # Continue to next iteration
                        # (so agent can try different approach)
                        continue

            else:
                # Loop completed without finishing - compile partial results
                logger.info(f"{self.__class__.__name__} "
                            "reached max iterations "
                            f"({self.max_iterations}). "
                            "Proceeding with partial results.")

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

            # First, try parsing without any sanitization
            try:
                action_input = json.loads(thought.action_input)
                logger.debug("Successfully parsed action_input: "
                             f"{action_input}")
            except json.JSONDecodeError as e:
                # Only sanitize if initial parsing fails
                logger.debug(f"Initial parse failed: {e}. "
                             "Attempting sanitization...")

                sanitized_input = thought.action_input.strip()

                # Only apply minimal sanitization
                # Escape backslashes in Windows paths
                sanitized_input = sanitized_input.replace("\\", "\\\\")

                # Remove trailing commas before closing brackets/braces
                # But NOT commas between array/object elements
                sanitized_input = re.sub(r",(\s*[}\]])", r"\1",
                                         sanitized_input)

                # Replace single quotes with double quotes to make valid JSON
                sanitized_input = sanitized_input.replace("'", '"')

                logger.debug(
                    "Sanitized action_input: "
                    f"{repr(sanitized_input)}"
                )

                try:
                    action_input = json.loads(sanitized_input)
                    logger.debug("Successfully parsed after sanitization: "
                                 f"{action_input}")
                except json.JSONDecodeError as e2:
                    logger.warning(
                        f"Failed to parse action_input after sanitization. "
                        f"Original: {repr(thought.action_input)}. "
                        f"Sanitized: {repr(sanitized_input)}. "
                        f"Error: {e2}. Attempting fallback parsing..."
                    )
                    # Fallback: try to extract key-value pairs manually
                    try:
                        # Enhanced regex-based extraction for common patterns
                        action_input = {}

                        # Extract "key": "value" or "key": number
                        # or "key": boolean
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

        # Handle case where action_input is a list instead of dict
        if isinstance(action_input, list):
            # Wrap list in dict for the tool
            # This handles cases like finish([]) or finish([item1, item2])
            result = await self._execute_tool(
                tool_name=tool_to_execute,
                items=action_input
            )
        else:
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
        # Handle variable number of observations per thought
        # due to batch actions
        obs_idx = 0
        for i, thought in enumerate(history.thoughts):
            parts.append(f"\nIteration {i+1}:")
            parts.append(f"  Thought: {thought.thought}")

            if thought.actions:
                parts.append("  Action Sequence:")
                for j, action_spec in enumerate(thought.actions):
                    act_name = action_spec.get("action", "unknown")
                    act_input = action_spec.get("action_input", "{}")
                    parts.append(f"    {j+1}. {act_name}({act_input})")
                    # Add observation if available
                    if obs_idx < len(history.observations):
                        obs = history.observations[obs_idx]
                        parts.append(f"      Observation: {obs.result}")
                        obs_idx += 1
            elif thought.action:
                act_str = f"  Action: {thought.action}({thought.action_input})"
                parts.append(act_str)
                # Add observation if available
                if obs_idx < len(history.observations):
                    obs = history.observations[obs_idx]
                    parts.append(f"  Observation: {obs.result}")
                    obs_idx += 1

        return "\n".join(parts)

    def _get_action_or_actions_formatting_lines(self) -> List[str]:
        return [
            "You can execute single actions "
            "OR action sequences for efficiency:",
            "",
            "Single Action:",
            "{{\"action\": \"scan_directory\", "
            "\"action_input\": \"{{\\\"path\\\": \\\"/tmp\\\"}}\"}}",
            "",
            "Action Sequence (recommended for related operations):",
            "{{\"actions\": ["
            "  {{\"action\": \"scan_directory\", "
            "\"action_input\": \"{{\\\"path\\\": \\\"/tmp\\\"}}\"}},",
            "  {{\"action\": \"analyse_directory\", "
            "\"action_input\": \"{{\\\"path\\\": \\\"/tmp\\\"}}\"}}",
            "]}}",
        ]

    def _get_action_or_actions_formatting(self) -> str:
        return "\n".join(self._get_action_or_actions_formatting_lines())

    def _get_json_formatting_lines(self) -> List[str]:
        return [
            "CRITICAL JSON FORMATTING RULES for action_input:",
            "1. MUST be valid JSON - double quotes for keys & string values",
            "2. NO trailing commas anywhere",
            "3. NO empty strings followed by commas",
            "4. For Windows paths, use forward slashes OR escape backslashes",
            "5. Close all braces and brackets properly",
            "",
            "Valid Examples:",
            '- Single param: \'{"path": "C:/Users/user/Downloads"}\'',
            '- Multiple params: \'{"path": "/tmp", "size_bytes": 1000,'
            ' "is_directory": true}\'',
        ]

    def _get_json_formatting_rules(self) -> str:
        return "\n".join(self._get_json_formatting_lines())

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
