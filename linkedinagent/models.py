from typing import Literal

from pydantic import BaseModel


class ShouldRunDecision(BaseModel):
    """
    Agent decides whether to run at all
    """
    should_run: bool
    reasoning: str


class NextActionDecision(BaseModel):
    """
    Agent decides what to do next
    """
    action: Literal[
        "continue_analyzing",
        "stop_and_summarize",
        "skip_post"
    ]
    reasoning: str


class PostAnalysis(BaseModel):
    """
    Agent's analysis of a LinkedIn post
    """
    category: Literal[
        "technical",
        "celebration",
        "promotional",
        "other"
    ]
    is_interesting: bool
    key_insight: str
    confidence: Literal["high", "medium", "low"]
