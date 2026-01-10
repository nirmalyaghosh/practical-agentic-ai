from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.models import (
    ApprovalStatus,
    Classification,
    UserDecision,
)


logger = get_logger(__name__)


class ApprovalGate:
    """
    Simple CLI-based approval gate.
    """

    def __init__(self):
        self.console = Console()

    def _construct_decorator(self) -> str:
        decorator_str = "\n".join([
            "\n" + "="*80,
            "APPROVAL REQUIRED",
            "="*80
        ])
        return decorator_str

    def _construct_descriptor_for_uncertainty(self, c: Classification) -> str:
        desc_str = "\n".join([
            "-"*60,
            f"  Path: {c.path}",
            f"  Size: {c.savings_gb:.2f} GB",
            f"  Reasoning: {c.reasoning[:100]}..."
        ])
        return desc_str

    def _display_approval_header(self):
        """
        Helper function used to display the approval required header.
        """
        header_panel = Panel.fit(
            "[bold red]APPROVAL REQUIRED[/bold red]",
            title="Human Approval Needed",
            border_style="red"
        )
        self.console.print(header_panel)

    def _display_batch_approval(
        self,
        classifications: List[Classification],
        title: str,
        border_color: str,
        log_message: str,
        max_rows: int = 5
    ) -> List[UserDecision]:
        """
        Helper function used to display and handle batch approval for a group
        of classifications.
        """
        if not classifications:
            return []

        count = len(classifications)
        logger.info(f"{log_message}: {count} items")

        table_title = f"[{border_color}]{count} {title}[/{border_color}]"
        table = Table(title=table_title)
        table.add_column("File Path", style="cyan")
        table.add_column("Size (MB)", justify="right", style="yellow")

        for c in classifications[:max_rows]:
            size_mb_str = f"{(c.estimated_savings_bytes / (1024*1024)):.1f} MB"
            table.add_row(str(c.path), f"{size_mb_str}")
            logger.info(f"Item: {str(c.path)} ({size_mb_str})")

        if count > max_rows:
            table.add_row(f"... and {count - 5} more", "")
            logger.info(f"... and {count - 5} more items")

        self.console.print(table)

        a_str = f"\n[bold]Approve all {count} {title.lower()}?[/bold] [y/N]: "
        self.console.print(a_str, end="")
        response = input().strip().lower()
        status = ApprovalStatus.APPROVED if response == "y" \
            else ApprovalStatus.REJECTED
        a_str = "approved" if status == ApprovalStatus.APPROVED else "rejected"
        logger.info(f"User {a_str} all {count} {title.lower()}")

        return [
            UserDecision(path=c.path, classification=c, status=status)
            for c in classifications
        ]

    def _display_uncertain_item_approval(
            self,
            classification: Classification,
            index: int) -> UserDecision:
        """
        Helper function used to display and handle individual approval for
        uncertain items.
        """
        clsf_path_str = str(classification.path)
        logger.info(f"Reviewing uncertain item {index}: {clsf_path_str}")

        size_mb = classification.estimated_savings_bytes / (1024*1024)
        size_mb_str = f"{(size_mb):.1f} MB"
        item_panel = Panel(
            f"[bold]Path:[/bold] {clsf_path_str}\n"
            f"[bold]Size:[/bold] {size_mb_str}\n"
            f"[bold]Reasoning:[/bold] {classification.reasoning[:100]}...",
            title=f"Review Item {index}",
            border_style="red"
        )
        self.console.print(item_panel)

        self.console.print("  [bold]Approve?[/bold] [y/N]: ", end="")
        response = input().strip().lower()
        status = ApprovalStatus.APPROVED if response == "y" \
            else ApprovalStatus.REJECTED
        a_str = "approved" if status == ApprovalStatus.APPROVED else "rejected"
        logger.info(f"User {a_str} uncertain item: {clsf_path_str}")

        return UserDecision(
            path=classification.path,
            classification=classification,
            status=status)

    def _display_summary(self, approved: int, total: int):
        """
        Helper function used to display the approval summary.
        """
        logger.info("Approval process complete"
                    f" - approved {approved}/{total} items")

        summary_panel = Panel.fit(
            f"[green]Approved {approved}/{total} items[/green]",
            title="SUMMARY",
            border_style="green"
        )
        self.console.print(summary_panel)

    def request_approval(
            self,
            classifications: List[Classification]) -> List[UserDecision]:
        """
        Request user approval for classifications.

        Args:
            classifications: List of classifications to approve

        Returns:
            List of UserDecision objects
        """
        decisions = []

        # Group by confidence
        safe = [c for c in classifications if c.confidence.value == "safe"]
        likely_safe = [c for c in classifications
                       if c.confidence.value == "likely_safe"]
        uncertain = [c for c in classifications
                     if c.confidence.value == "uncertain"]

        # Log overview of the files for which approval is required
        logger.info(f"Approval required for {len(classifications)} items "
                    f"({len(safe)} safe, {len(likely_safe)} likely safe, "
                    f"{len(uncertain)} uncertain)")

        # Display header
        self._display_approval_header()

        # Handle each group
        decisions = []
        decisions.extend(self._display_batch_approval(
            classifications=safe,
            title="SAFE items (high confidence)",
            border_color="green",
            log_message="Requesting batch approval for safe"
        ))
        decisions.extend(self._display_batch_approval(
            classifications=likely_safe,
            title="LIKELY SAFE items",
            border_color="orange",
            log_message="Requesting batch approval for likely safe"
        ))

        # Handle uncertain items individually
        for i, c in enumerate(uncertain, 1):
            decisions.append(self._display_uncertain_item_approval(c, i))

        # Display summary
        approved = sum(1 for d in decisions
                       if d.status == ApprovalStatus.APPROVED)
        self._display_summary(approved, len(decisions))

        return decisions
