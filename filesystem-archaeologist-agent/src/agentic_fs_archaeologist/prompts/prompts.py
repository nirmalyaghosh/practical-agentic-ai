import json

from functools import lru_cache
from pathlib import Path
from typing import (
    Any,
    Dict,
    Optional,
)

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.utils.file_utils import validate_file_path


logger = get_logger(__name__)


@lru_cache(maxsize=1)
def load_prompts(
        prompt_json_file_path: Optional[Path] = None) -> Dict[str, Any]:
    if prompt_json_file_path:
        if validate_file_path(file_path=prompt_json_file_path) is False:
            error_message = "Unable to read file containing prompts " +\
                            "Invalid file path passed"
            raise FileNotFoundError(error_message)
        p = Path(prompt_json_file_path)
    else:
        p = Path(__file__).parent / "prompts.json"
    if not p.exists():
        raise FileNotFoundError("prompts.json not found in current directory")
    logger.debug(f"Loading prompts from {p}...")
    return json.loads(p.read_text(encoding="utf-8"))
