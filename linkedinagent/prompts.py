import json
from pathlib import Path


def load_prompts():
    p = Path(__file__).parent / "prompts.json"
    if not p.exists():
        raise FileNotFoundError("prompts.json not found in current directory")
    return json.loads(p.read_text(encoding="utf-8"))
