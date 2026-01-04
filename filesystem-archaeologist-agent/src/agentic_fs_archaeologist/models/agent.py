from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from agentic_fs_archaeologist.models.filesystem import FileMetadata
from agentic_fs_archaeologist.models.classification import (
    Classification,
    ReflectionCritique,
)


class AgentState(BaseModel):
    """
    Pydantic data model used for the state object passed between agents.
    """
    context: Dict[str, Any] = Field(default_factory=dict)
    discoveries: List[FileMetadata] = Field(default_factory=list)
    classifications: List[Classification] = Field(default_factory=list)
    critiques: List[ReflectionCritique] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """
    Pydantic data model used for the result returned by an agent.
    """
    success: bool
    data: Optional[Any] = None
    reasoning: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReActThought(BaseModel):
    """
    Pydantic data model used for thoughts in the ReAct reasoning loop.
    """
    thought: str
    action: Optional[str] = None
    action_input: Optional[str] = None
    should_continue: bool = True


class ReActObservation(BaseModel):
    """
    Pydantic data model used for observations from executing an action.
    """
    action: str
    result: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class ReActHistory(BaseModel):
    """
    Pydantic data model used for the history of thoughts and observations
    in a ReAct loop.
    """
    thoughts: List[ReActThought] = Field(default_factory=list)
    observations: List[ReActObservation] = Field(default_factory=list)
    final_answer: Optional[str] = None
