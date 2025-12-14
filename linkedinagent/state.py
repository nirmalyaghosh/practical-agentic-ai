import json

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AgentState:
    """
    Persistent memory - the agent remembers its past
    """
    goal: str
    last_run: str
    total_posts_seen: int
    interesting_posts_count: int
    categories_seen: dict[str, int]
    action_history: list[dict]

    def save(self):
        """
        Persist state to disk
        """
        memory_json_str = json.dumps(asdict(self), indent=2)
        Path("agent-memory.json").write_text(memory_json_str)

    @classmethod
    def load_or_create(cls):
        """
        Load previous state or create new
        """
        if Path("agent-memory.json").exists():
            data = json.loads(Path("agent-memory.json").read_text())
            return cls(**data)
        return cls(
            goal="Keep me informed of technical content in my LinkedIn feed",
            last_run="never",
            total_posts_seen=0,
            interesting_posts_count=0,
            categories_seen={},
            action_history=[],
        )
