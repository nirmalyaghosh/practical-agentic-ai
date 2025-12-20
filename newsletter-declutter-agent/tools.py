import json
import os

from typing import (
    Any,
    Dict,
    List,
)

from app_logger import get_logger


logger = get_logger(__name__)


def load_openai_tools() -> List[Dict[str, Any]]:
    """
    Helper function used to load OpenAI tool definitions from a JSON file.
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(dir_path, "tool-definitions-openai.json")
    logger.debug(f"Loading OpenAI tool definitions from {json_path}...")

    with open(json_path, "r") as f:
        return json.load(f)
