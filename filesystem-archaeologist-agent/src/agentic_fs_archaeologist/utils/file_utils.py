from pathlib import Path

from agentic_fs_archaeologist.app_logger import get_logger


logger = get_logger(__name__)


def format_file_size(bytes_size: int) -> str:
    """
    Helper function used to format file size with appropriate units
    (GB, MB, KB, or bytes).

    Uses adaptive units:
    - GB for files >= 1 GB
    - MB for files >= 100 KB
    - KB for files >= 1 KB
    - bytes for smaller files
    """
    if bytes_size >= 1024 * 1024 * 1024:  # >= 1 GB
        gb_size = bytes_size / (1024 * 1024 * 1024)
        return f"{gb_size:.1f} GB"
    elif bytes_size >= 100 * 1024:  # >= 100 KB
        mb_size = bytes_size / (1024 * 1024)
        return f"{mb_size:.1f} MB"
    elif bytes_size >= 1024:  # >= 1 KB
        kb_size = bytes_size / 1024
        return f"{kb_size:.1f} KB"
    else:  # < 1 KB
        return f"{bytes_size} bytes"


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
