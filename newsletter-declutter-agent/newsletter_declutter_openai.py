"""
OpenAI Implementation of the Newsletter Declutter Agent.

This implementation uses GPT-4o-mini with function calling
to analyze and clean up newsletter subscriptions.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app_logger import get_logger
from gmail_auth import create_gmail_service
from newsletter_analysis import available_functions
from prompts import load_prompts
from tools import load_openai_tools


load_dotenv("newsletter-declutter-agent.env")
logger = get_logger(__name__)
tools = load_openai_tools()

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def _log_function_result(function_name, function_response):
    """
    Helper function used to log a summary of function execution results.

    Args:
        function_name: Name of the function that was called
        function_response: Response from the function execution
    """
    if not function_response.get('success'):
        logger.error(f"Function {function_name} failed")
        return

    if function_name == "scan_newsletters":
        n = function_response["total_newsletters"]
        logger.info(f"   Found {n} newsletters")
    elif function_name == "analyze_engagement":
        n = len(function_response["engagement_data"])
        logger.info(f"   Analyzed {n} newsletters")
    elif function_name == "extract_unsubscribe_links":
        n = len(function_response["unsubscribe_data"])
        logger.info(f"   Extracted links for {n} newsletters")


def run_newsletter_agent():
    """
    Run the newsletter declutter agent with OpenAI GPT-4o-mini.
    Implements the ReAct pattern with function calling.
    """
    logger.info("="*60)
    logger.info("NEWSLETTER DECLUTTER AGENT - OpenAI Implementation")
    logger.info("="*60)

    # Initialize Gmail service
    logger.info("Authenticating with Gmail...")
    try:
        service = create_gmail_service()
        logger.info("Gmail authentication successful")
    except Exception as e:
        logger.error(f"Failed to authenticate with Gmail: {e}")
        return None

    # Initialize conversation
    # First, load the prompt data
    prompt_data = load_prompts()["newsletter_declutter_agent"]
    # Next, transform into proper OpenAI message format
    messages = [{
        "role": "user",  # or "system" depending on your preference
        "content": "\n".join(prompt_data["lines"])
    }]
    logger.info("Starting newsletter analysis with GPT-4o-mini...")
    logger.info("")

    iteration, max_iterations = 0, 10
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"--- Iteration {iteration} ---")

        try:
            # Call OpenAI with function calling enabled
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            finish_reason = response.choices[0].finish_reason

            logger.info(f"Finish reason: {finish_reason}")

            # Add assistant's response to message history
            messages.append(response_message)

            # Check if the model wants to call functions
            if tool_calls:
                logger.info(f"Model requesting {len(tool_calls)} tool call(s)")

                for tool_call in tool_calls:
                    # Check if tool_call has function attribute
                    # and it is not None
                    if not hasattr(tool_call, "function") \
                            or not tool_call.function:
                        logger.warning("Invalid tool call structure: "
                                       f"{tool_call}")
                        continue

                    # Check if function has name attribute
                    if not hasattr(tool_call.function, "name"):
                        logger.warning("Tool call missing function name: "
                                       f"{tool_call}")
                        continue

                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    logger.info(f"   Tool: {function_name}")
                    logger.info(f"   Args: {function_args}")

                    # Get the function to call
                    function_to_call = available_functions.get(function_name)

                    if function_to_call:
                        # Execute the function
                        function_response = function_to_call(
                            service,
                            **function_args)

                        # Log summary of results
                        _log_function_result(
                            function_name=function_name,
                            function_response=function_response)

                        # Add function response to messages
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(function_response)
                        })
                    else:
                        logger.error(f"Unknown function: {function_name}")
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({
                                "error":
                                f"Unknown function: {function_name}"})
                        })

                logger.info("")

            elif finish_reason == "stop":
                # Model has finished - extract final response
                final_text = response_message.content

                logger.info("")
                logger.info("="*60)
                logger.info("ANALYSIS COMPLETE")
                logger.info("="*60)
                logger.info("")
                logger.info(final_text)
                logger.info("")
                logger.info("="*60)

                break

            else:
                logger.warning(f"Unexpected finish reason: {finish_reason}")
                break

        except Exception as e:
            logger.error(f"Error during iteration {iteration}: {e}",
                         exc_info=True)
            break

    if iteration >= max_iterations:
        logger.warning(f"Reached maximum iterations ({max_iterations})")

    logger.info(f"Agent completed in {iteration} iterations")
    return messages


def main():
    """
    Main entry point
    """
    try:
        # Check for OpenAI API key
        if not os.environ.get("OPENAI_API_KEY"):
            logger.error("OPENAI_API_KEY environment variable not set")
            return

        # Run the agent
        conversation_history = run_newsletter_agent()

        if conversation_history:
            logger.info("Newsletter analysis completed successfully!")
        else:
            logger.error("Newsletter analysis failed")

    except KeyboardInterrupt:
        logger.info("\nAgent interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
