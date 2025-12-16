import json

from pathlib import Path

from app_logger import get_logger


logger = get_logger(__name__)


def load_prompts():
    p = Path(__file__).parent / "prompts.json"
    if not p.exists():
        raise FileNotFoundError("prompts.json not found in current directory")
    logger.debug(f"Loading prompts from {p}...")
    return json.loads(p.read_text(encoding="utf-8"))
