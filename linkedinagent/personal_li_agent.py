"""Minimal runner for the Agentic LinkedIn agent."""

import asyncio
import logging
import os

from dotenv import load_dotenv

from agents import AgenticLinkedInAgent


load_dotenv("linkedinagent.env")
logger = logging.getLogger(__name__)


async def main():
    # Check for API key
    github_token = os.getenv("OPENAI_API_KEY")
    if not github_token:
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    agent = AgenticLinkedInAgent()
    await agent.run_autonomously()


if __name__ == "__main__":
    asyncio.run(main())
