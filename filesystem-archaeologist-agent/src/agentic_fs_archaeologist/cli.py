"""
Command-line interface for the Filesystem Archaeologist Agent.
"""

import asyncio

import typer

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.agents import OrchestratorAgent
from agentic_fs_archaeologist.config import get_settings
from agentic_fs_archaeologist.hitl import ApprovalGate
from agentic_fs_archaeologist.memory import (
    MemoryRetrieval,
    MemoryStore,
)
from agentic_fs_archaeologist.models import (
    AgentState,
    MemoryEntry,
)


app = typer.Typer()
logger = get_logger(__name__)


def _echo_banner():
    """
    Helper function
    """
    typer.echo(f"\n{'='*60}")
    typer.echo("Filesystem Archaeologist Agent")
    typer.echo(f"{'='*60}\n")


def _echo_and_log(message: str):
    """
    Helper function
    """
    typer.echo(message)
    logger.info(message.replace("\n", ""))


@app.command()
def info():
    """
    Helper function used to show information about the agent.
    """
    _echo_banner()
    typer.echo("  fs-archaeologist scan <path>")
    typer.echo("\nExample:")
    typer.echo("  fs-archaeologist scan ~/Downloads")
    typer.echo("")


def main():
    app()


@app.command()
def scan(
    path: str = typer.Argument(..., help="Path to scan for cleanup"),
    model: str = typer.Option(None, help="OpenAI model to use"),
):
    """
    Scan a directory for cleanup opportunities.
    """

    # Check API key
    settings = get_settings()
    if not settings.openai_api_key:
        error_message = "OPENAI_API_KEY environment variable not set"
        typer.echo(f"Error: {error_message}", err=True)
        raise typer.Exit(1)

    # Run async scan
    asyncio.run(scan_async(path=path, model=model))


async def scan_async(path: str, model: str):
    """
    Async scan implementation.
    """

    _echo_banner()
    _echo_and_log(f"Scanning: {path}\n")

    # Initialize memory
    store = MemoryStore()
    memory = MemoryRetrieval(store=store)

    # Initialize orchestrator
    orchestrator = OrchestratorAgent()

    # Create initial state
    state = AgentState(context={"target_path": path})

    # Execute workflow
    result = await orchestrator.execute(state)

    if not result.success:
        typer.echo(f"Error: {result.error}", err=True)
        return

    # Show reasoning
    _echo_and_log("Workflow completed!\n")
    for line in result.reasoning:
        _echo_and_log(line)

    # Get classifications
    all_classifications = result.data.get("classifications", []) \
        if result.data else []

    # Filter to only show cleanup opportunities
    # (DELETE or REVIEW recommendations)
    classifications = [
        c for c in all_classifications
        if hasattr(c, 'recommendation') and
        c.recommendation in ['delete', 'review']
    ]

    _echo_and_log(f"\nTotal items analyzed: {len(all_classifications)}")
    _echo_and_log(f"Cleanup opportunities found: {len(classifications)}")

    if not classifications:
        _echo_and_log("\nNo cleanup opportunities found.")
        return

    # HITL: Request approval
    approval_gate = ApprovalGate()
    decisions = approval_gate.request_approval(classifications)

    # Save decisions to memory
    _echo_and_log("\nSaving decisions to memory...")

    for decision in decisions:
        # Extract pattern
        pattern = memory._extract_pattern(decision.path)

        # Log detailed information about what we're saving
        logger.info(f"Processing decision save: path={decision.path}, "
                    f"decision={decision.status.value}")
        logger.info(f"Extracted pattern: {pattern}")

        # Check if pattern already exists
        existing = store.find_by_pattern(pattern)
        if existing:
            logger.info(f"Existing pattern found: approval_rate={existing.approval_rate:.2%}, "
                       f"approval_count={existing.approval_count}, "
                       f"rejection_count={existing.rejection_count}")
        else:
            logger.info("New pattern: will create initial memory entry")

        # Create memory entry
        entry = MemoryEntry(
            path_pattern=pattern,
            file_type=decision.classification.file_type,
            directory_type=decision.classification.directory_type,
            user_decision=decision.status,
            confidence=decision.classification.confidence,
        )

        # Log the entry structure
        entry_details = (f"path_pattern={entry.path_pattern}, "
                        f"file_type={entry.file_type}, "
                        f"directory_type={entry.directory_type}, "
                        f"user_decision={entry.user_decision.value}, "
                        f"confidence={entry.confidence.value}")
        logger.info(f"Saving MemoryEntry: {entry_details}")

        saved_entry = store.save(entry)

        # Verify what was actually saved (read back from DB)
        refreshed = store.find_by_pattern(pattern)
        if refreshed:
            final_details = (f"approval_count={refreshed.approval_count}, "
                           f"rejection_count={refreshed.rejection_count}, "
                           f"approval_rate={refreshed.approval_rate:.2%}")
            logger.info(f"After save - memory state: {final_details}")

    _echo_and_log("Done! Decisions saved for future sessions.")
    _echo_and_log("\nNote: MVP stops here (no actual deletion)")


if __name__ == "__main__":
    main()
