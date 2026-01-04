from typing import List
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

        logger.info(self._construct_decorator())

        # Batch approve safe items
        if safe:
            ns = len(safe)
            logger.info(f"{ns} SAFE items (high confidence):")
            for c in safe[:5]:  # Show first 5 safe items
                logger.info(f"  • {c.path} ({c.savings_gb:.2f} GB)")
            if ns > 5:
                logger.info(f"  ... and {ns-5} more")

            input_question = f"\nApprove all {ns} safe items? [y/N]: "
            response = input(input_question).strip().lower()
            status = ApprovalStatus.APPROVED if response == "y" \
                else ApprovalStatus.REJECTED

            for c in safe:
                decisions.append(UserDecision(
                    path=c.path,
                    classification=c,
                    status=status
                ))

        # Batch approve likely safe
        if likely_safe:
            nls = len(likely_safe)
            ls_items_str_components = []
            for c in likely_safe[:5]:
                likely_safe_desc_str = f"  • {c.path} ({c.savings_gb:.2f} GB)"
                ls_items_str_components.append(likely_safe_desc_str)
            if nls > 5:
                ls_items_str_components.append(f"  ... and {nls-5} more")
            likely_safe_items_str = "\n".join(ls_items_str_components)
            logger.info(f"{nls} LIKELY SAFE items:\n{likely_safe_items_str}")

            input_question = f"\nApprove all {nls} likely safe items? [y/N]: "
            response = input(input_question).strip().lower()
            status = ApprovalStatus.APPROVED if response == "y" \
                else ApprovalStatus.REJECTED

            for c in likely_safe:
                decisions.append(UserDecision(
                    path=c.path,
                    classification=c,
                    status=status
                ))

        # Individual review for uncertain
        if uncertain:
            nu = len(uncertain)
            logger.info(f"{nu} UNCERTAIN items (need individual review):")
            for c in uncertain:
                desc_str = self._construct_descriptor_for_uncertainty(c=c)
                logger.info(desc_str)

                response = input("  Approve? [y/N]: ").strip().lower()
                status = ApprovalStatus.APPROVED if response == "y" \
                    else ApprovalStatus.REJECTED

                decisions.append(UserDecision(
                    path=c.path,
                    classification=c,
                    status=status
                ))

        # Summary
        approved = sum(1 for d in decisions
                       if d.status == ApprovalStatus.APPROVED)
        summary_str = "\n".join([
            f"\n{'='*80}",
            f"SUMMARY: Approved {approved}/{len(decisions)} items",
            f"{'='*80}"
        ])
        logger.info(f"\n{summary_str}")

        return decisions
