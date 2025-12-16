import asyncio
import json
import logging
import os

from datetime import datetime

from playwright.async_api import async_playwright
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from logging_config import logger as config_logger
from models import (
    NextActionDecision,
    PostAnalysis,
    ShouldRunDecision,
)
from prompts import load_prompts
from state import AgentState
from li_ui_actions import (
    login as ui_action_login,
    extract_posts as ui_action_extract_posts,
    get_authenticated_context,
)


logger = logging.getLogger(__name__)
# Ensure the module logger inherits the configuration
logger.handlers = config_logger.handlers
logger.setLevel(config_logger.level)


class AgenticLinkedInAgent:
    """
    An agentic agent that:
    - Operates autonomously towards a goal
    - Makes decisions about what to do next
    - Learns from its actions
    """

    def __init__(self):
        self.state = AgentState.load_or_create()
        self.interesting_posts = []
        self._init_agents()

    async def _analyze_post(
            self,
            post: dict,
            post_num: int) -> PostAnalysis | None:
        """
        Helper function used to analyze a single post
        """
        try:
            analysis = await self.analysis_agent.run(
                f"""
                Post #{post_num}
                Author: {post["author"]}
                Content: {post["text"]}

                Analyze this post.
                """
            )

            # Parse response
            result = self._parse_json_response(
                analysis.output,
                PostAnalysis,
                f"post {post_num} analysis"
            )

            if result:
                # Update state
                self.state.categories_seen[result.category] = \
                    self.state.categories_seen.get(result.category, 0) + 1

                # Log result
                is_interesting_str = "YES" if result.is_interesting else "NO"
                author = post["author"]
                text = post.get("text", "").strip()
                url = post.get("url", "N/A")
                post_info_lines = []  # Capture information of LinkedIn post
                post_info_lines.append(f"LinkedIn Post #{post_num}")
                post_info_lines.append(f"   URL: {url}")
                post_info_lines.append(f"   Author: {author}")
                post_info_lines.append(f"   Category: {result.category}")
                post_info_lines.append(f"   Interesting: {is_interesting_str}")
                post_info_lines.append(f"   Insight: {result.key_insight}")
                text_for_snipping = text.replace("\n", " ")
                snipped_text = (text_for_snipping[:300] + "..."
                                if len(text_for_snipping) > 300
                                else text_for_snipping)
                post_info_lines.append(f"   Text: {snipped_text}")
                logger.info("\n".join(post_info_lines))

                # Save if interesting
                if result.is_interesting:
                    self.interesting_posts.append({
                        **post,
                        "analysis": result.model_dump(),
                    })
                    self.state.interesting_posts_count += 1

                return result

            return None

        except Exception as e:
            logger.error(f"Error in _analyze_post: {e}")
            return None

    async def _analyze_post_and_decide(
            self,
            post: dict,
            post_num: int) -> str:
        """
        Helper function used to analyze a post and decide what to do next.

        PERCEPTION → REASONING → ACTION
        """
        try:
            # PERCEPTION: Analyze the post
            analysis_result = await self._analyze_post(
                post=post,
                post_num=post_num)

            if not analysis_result:
                return "skip_post"

            # REASONING: Decide next action
            next_action = await self._decide_next_action(
                analysis=analysis_result,
                post_num=post_num)

            return next_action

        except Exception as e:
            logger.error(f"Error analyzing post {post_num}: {e}")
            return "skip_post"

    def _build_prompt(
            self,
            lines: list[str],
            json_instruction: str) -> str:
        """
        Helper function used to build a complete prompt with JSON formatting
        instruction
        """
        base_prompt = "\n".join(lines)
        return f"{base_prompt}\n\n{json_instruction}"

    def _calculate_hours_since_last_run(self) -> float:
        """
        Helper function used to calculate hours since last run
        """
        if self.state.last_run == "never":
            return 0.0

        try:
            last_run_dt = datetime.fromisoformat(self.state.last_run)
            delta = datetime.now() - last_run_dt
            return delta.total_seconds() / 3600
        except Exception as e:
            logger.error(f"Error calculating time since last run: {e}")
            return 0.0

    async def generate_summary(self):
        """
        Helper function used to generate and log summary of agent run
        """
        lines = []  # Capture the summary lines
        lines.append("\n" + "=" * 80)
        lines.append("AGENT SUMMARY")
        lines.append("=" * 80)

        lines.append(f"Goal: {self.state.goal}")
        lines.append(f"Posts analyzed: {len(self.state.action_history)}")
        n = len(self.interesting_posts)
        lines.append(f"Interesting posts found: {n}")

        # Interesting posts
        if self.interesting_posts:
            lines.append("")  # Blank line
            lines.append("INTERESTING POSTS:")
            for i, post in enumerate(self.interesting_posts, 1):
                analysis = post["analysis"]
                author = post["author"]
                url = post.get("url", "N/A")
                key_insight = analysis["key_insight"]
                category = analysis["category"]
                lines.append("")  # Blank line
                lines.append(f"LinkedIn Post #{i} URL: {url} By {author}")
                lines.append(f"   Category: {category}")
                lines.append(f"Key insight: {key_insight}")

        else:
            lines.append("No particularly interesting posts found today")

        # Category breakdown
        lines.append("")  # Blank line
        lines.append("Category breakdown:")
        for cat, count in self.state.categories_seen.items():
            lines.append(f"   {cat}: {count}")

        lines.append("\n" + "=" * 80)
        logger.info("\n".join(lines))

    def _init_agents(self):
        """
        Initialize AI agents
        """
        logger.info("Initializing AI agents...")

        # Get API key and validate
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in your .env file:\n"
                "OPENAI_API_KEY=your_api_key_here"
            )

        # Create OpenAI model
        try:
            # Create model
            model = OpenAIChatModel(
                "gpt-4o-mini",
                provider=OpenAIProvider(api_key=api_key)
            )
        except Exception as e:
            logger.error("Failed to initialize model: %s", str(e))
            raise

        # Load prompts from JSON
        prompts = load_prompts()

        # Build system prompts with JSON instruction
        decision_prompt = self._build_prompt(
            prompts["decision_agent"]["lines"],
            "Respond ONLY with valid JSON matching: "
            '{"action": "continue_analyzing"|"stop_and_summarize"|'
            '"skip_post", "reasoning": "string"}'
        )

        analysis_prompt = self._build_prompt(
            prompts["analysis_agent"]["lines"],
            "Respond ONLY with valid JSON matching: "
            '{"category": "technical"|"celebration"|"promotional"|"other", '
            '"is_interesting": true|false, "key_insight": "string", '
            '"text": "string",'
            '"confidence": "high"|"medium"|"low"}'
        )

        startup_prompt = self._build_prompt(
            prompts["startup_agent"]["lines"],
            "Respond ONLY with valid JSON matching: "
            '{"should_run": true|false, "reasoning": "string"}'
        )

        # Create agents
        self.decision_agent = Agent(model=model, system_prompt=decision_prompt)
        self.analysis_agent = Agent(model=model, system_prompt=analysis_prompt)
        self.startup_agent = Agent(model=model, system_prompt=startup_prompt)

        logger.info("All agents initialized successfully")

    async def should_i_run(self) -> bool:
        """
        AUTONOMOUS DECISION: Should the agent run now?
        """
        logger.info("Agent evaluating whether to run...")

        try:
            # Calculate hours since last run
            hours_since_last_run = self._calculate_hours_since_last_run()

            # Ask agent to decide
            decision = await self.startup_agent.run(
                f"""
                Agent state:
                - Goal: {self.state.goal}
                - Last run: {self.state.last_run}
                - Hours since last run: {hours_since_last_run:.1f}
                - Total posts seen: {self.state.total_posts_seen}
                - Interesting posts found: {self.state.interesting_posts_count}

                Should I check LinkedIn now?
                """
            )

            # Parse response
            result = self._parse_json_response(
                decision.output,
                ShouldRunDecision,
                "startup decision"
            )

            decision_str = "RUN" if result and result.should_run else "SKIP"
            if result:
                logger.info(f"   Decision: {decision_str}")
                logger.info(f"   Reasoning: {result.reasoning}")
                return result.should_run
            else:
                logger.warning("Failed to get startup decision,"
                               "defaulting to RUN")
                return True

        except Exception as e:
            logger.error(f"Error in should_i_run: {e}")
            return True  # Default to running on error

    async def _decide_next_action(
            self,
            analysis: PostAnalysis,
            post_num: int) -> str:
        """
        Helper function used to decide what to do after analyzing a post
        """
        try:
            # Ask agent to decide next action
            intereating_str = "interesting" if analysis.is_interesting \
                else "not interesting"
            decision = await self.decision_agent.run(
                f"""
                Current situation:
                - Posts analyzed so far: {post_num}
                - Interesting posts found: {len(self.interesting_posts)}
                - Last post was: {analysis.category} ({intereating_str})
                - Goal: {self.state.goal}

                What should I do next?
                """
            )

            # Parse response
            result = self._parse_json_response(
                decision.output,
                NextActionDecision,
                "next action decision"
            )

            if result:
                logger.info(f"Next action: {result.action}")
                logger.info(f"        Why: {result.reasoning}\n")

                # Record decision in history
                self.state.action_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "post_num": post_num,
                    "action": result.action,
                    "reasoning": result.reasoning,
                })

                return result.action
            else:
                return "continue_analyzing"

        except Exception as e:
            logger.error(f"Error in _decide_next_action: {e}")
            return "continue_analyzing"

    def _parse_json_response(
            self,
            output: str,
            model_class,
            context: str):
        """
        Helper function used to parse the JSON response from agent,
        with error handling
        """
        try:
            # Try to parse as JSON
            data = json.loads(output)
            return model_class(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for {context}: {e}")
            logger.debug(f"Raw output: {output[:200]}...")

            # Try to extract JSON from markdown code blocks
            if "```json" in output:
                try:
                    start = output.find("```json") + 7
                    end = output.find("```", start)
                    json_str = output[start:end].strip()
                    data = json.loads(json_str)
                    return model_class(**data)
                except Exception as e2:
                    logger.error(f"Failed to extract JSON from markdown: {e2}")

            return None
        except Exception as e:
            logger.error(f"Error parsing {context}: {e}")
            return None

    async def run_autonomously(self):
        """
        Main agentic loop - autonomous operation
        """
        logger.info("=" * 80)
        logger.info("AGENTIC LINKEDIN AGENT STARTING")
        logger.info("=" * 80)
        logger.info(f"Goal: {self.state.goal}")
        logger.info(f"Last run: {self.state.last_run}")

        try:
            # DECISION 1: Should I even run?
            if not await self.should_i_run():
                logger.info("Agent decided not to run. Shutting down.")
                return

            logger.info("Agent decided to check LinkedIn feed")

            # Use persistent browser context

            async with async_playwright() as p:
                context = await get_authenticated_context(p)

                try:
                    # Get or create page
                    pages = context.pages
                    page = pages[0] if pages else await context.new_page()

                    # Login (will skip if already authenticated)
                    await ui_action_login(page)

                    # Extract posts
                    posts = await ui_action_extract_posts(page)
                    logger.info(f"Found {len(posts)} posts to analyze")

                    if not posts:
                        logger.warning("No posts found, ending run")
                        return

                    # AGENTIC LOOP: Process each post
                    for i, post in enumerate(posts, 1):
                        self.state.total_posts_seen += 1

                        # Analyze and decide
                        action = await self._analyze_post_and_decide(post, i)

                        # Act on decision
                        if action == "stop_and_summarize":
                            logger.info(f"Agent decided to stop at post {i}")
                            break
                        elif action == "skip_post":
                            logger.info("Skipping post...")
                            continue

                        # Brief pause between posts
                        await asyncio.sleep(1)

                    # Generate summary
                    await self.generate_summary()

                    # Update and save state
                    self.state.last_run = datetime.now().isoformat()
                    self.state.save()
                    logger.info("Agent state saved to memory")

                except Exception as e:
                    logger.exception(f"Error during agent run: {e}")

                finally:
                    await context.close()

        except Exception as e:
            logger.exception(f"Fatal error in run_autonomously: {e}")
