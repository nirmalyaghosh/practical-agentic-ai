from pathlib import Path

from agentic_fs_archaeologist.app_logger import get_logger


logger = get_logger(__name__)


def validate_file_path(file_path: Path) -> bool:
    """
    Helper function used to check if the indicated file path is valid;
    and that a file of indicated type exists at the specified location.
    """
    is_valid = False
    if file_path is None:
        logger.warning("Invalid file path passed (arg is None)")
        return is_valid

    if file_path.exists() is False:
        logger.warning("Invalid file path passed (no such file)")
        return is_valid

    if file_path.is_dir() is False:
        logger.warning("Invalid file path passed (is a directory)")
        return is_valid

    is_valid = True  # Finally, if it reaches here, is valid
    return is_valid
