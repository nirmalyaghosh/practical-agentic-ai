import time

from pathlib import Path
from typing import (
    Dict,
    Optional,
)

from agentic_fs_archaeologist.app_logger import get_logger


logger = get_logger(__name__)


class FileSystemTools:
    """
    Used for filesystem scanning and analysis tools.
    """

    @staticmethod
    def analyse_directory(path: str, depth: Optional[int] = None) -> Dict:
        """
        Helper function used to perform deep analysis of a directory.
        It returns a Dictionary with directory analysis
        """
        try:
            target = Path(path).expanduser().resolve()

            if not target.exists():
                return {"error": "Path does not exist"}

            if target.is_file():
                # Handle files differently than directories
                size = target.stat().st_size
                return {
                    "path": str(target),
                    "is_directory": False,
                    "file_count": 1,
                    "subdirectory_count": 0,
                    "file_types": {target.suffix or "no_extension": 1},
                    "size_bytes": size,
                    "size_gb": size / (1024 * 1024 * 1024),
                }

            if not target.is_dir():
                return {"error": "Invalid directory path"}

            # Determine directory type
            dir_name = target.name.lower()
            dir_type = "other"

            if dir_name == "node_modules":
                dir_type = "node_modules"
            elif dir_name in ["venv", ".venv", "env", ".env"]:
                dir_type = "venv"
            elif "cache" in dir_name:
                dir_type = "cache_dir"
            elif dir_name in ["build", "dist", "target", ".next", "out"]:
                dir_type = "build_dir"
            elif dir_name in ["temp", "tmp"]:
                dir_type = "temp_dir"
            elif dir_name == ".git":
                dir_type = "git_dir"

            # Get file types breakdown
            file_types = {}
            file_count = 0
            dir_count = 0

            def count_recursive(current_path: Path, current_depth: int):
                nonlocal file_count, dir_count
                try:
                    for item in current_path.iterdir():
                        try:
                            if item.is_file():
                                file_count += 1
                                ext = item.suffix or "no_extension"
                                file_types[ext] = file_types.get(ext, 0) + 1
                            elif item.is_dir():
                                dir_count += 1
                                # Recurse if depth allows
                                # (None means unlimited)
                                if depth is None or current_depth < depth:
                                    count_recursive(item, current_depth + 1)
                        except (PermissionError, OSError):
                            continue
                except (PermissionError, OSError):
                    pass

            count_recursive(target, 0)

            size = FileSystemTools._get_dir_size(target)

            return {
                "path": str(target),
                "directory_type": dir_type,
                "file_count": file_count,
                "subdirectory_count": dir_count,
                "file_types": dict(sorted(
                    file_types.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]),
                "size_bytes": size,
                "size_gb": size / (1024 * 1024 * 1024),
            }

        except Exception as e:
            logger.error(f"Error analyzing directory {path}: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def check_git_status(path: str) -> Dict:
        """
        Helper function used to check if path is in a git repository
        and in gitignore.

        Args:
            path: Path to check

        Returns:
            Git status information
        """
        target = Path(path).expanduser().resolve()

        # Walk up to find .git directory
        current = target if target.is_dir() else target.parent
        is_git_repo = False
        in_gitignore = False

        while current != current.parent:
            git_dir = current / ".git"
            if git_dir.exists():
                is_git_repo = True

                # Check if path is in gitignore
                gitignore = current / ".gitignore"
                if gitignore.exists():
                    try:
                        gitignore_content = gitignore.read_text()
                        rel_path = str(target.relative_to(current))
                        for line in gitignore_content.split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # Simple pattern matching
                                pattern = line.rstrip('/')
                                if rel_path.startswith(pattern) or \
                                        target.name == pattern:
                                    in_gitignore = True
                                    break
                    except Exception:
                        pass
                break
            current = current.parent

        return {
            "is_git_repo": is_git_repo,
            "in_gitignore": in_gitignore,
            "path": str(target),
        }

    @staticmethod
    def _get_dir_size(path: Path) -> int:
        """
        Helper function used to calculate total size of directory.

        Args:
            path: Directory path

        Returns:
            Total size in bytes
        """
        total = 0
        visited: set[Path] = set()
        try:
            for item in path.rglob("*"):
                # Skip symlinks to avoid infinite loops
                if item.is_symlink():
                    continue

                # Skip if already visited (for hardlinks)
                try:
                    stat_info = item.stat()
                    if item in visited:
                        continue
                    visited.add(item)

                    if item.is_file():
                        total += stat_info.st_size
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        return total

    @staticmethod
    def get_file_age(path: str) -> Dict:
        """
        Helper function used to get file age information.

        Args:
            path: Path to check

        Returns:
            Age information
        """
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return {"error": "Path does not exist"}

            stat = target.stat()
            now = time.time()
            age_seconds = now - stat.st_mtime
            age_days = int(age_seconds / (60 * 60 * 24))

            return {
                "path": str(target),
                "age_days": age_days,
                "age_months": age_days // 30,
                "last_modified": time.ctime(stat.st_mtime),
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def scan_directory(
            path: str,
            depth: int = 1,
            min_size_mb: float = 100) -> Dict:
        """
        Helper function used to scan a directory and return contents summary.

        Args:
            path: Directory path to scan
            depth: How many levels deep to scan
            min_size_mb: Minimum size in MB to include

        Returns:
            Dictionary with directory contents summary
        """
        try:
            if not isinstance(depth, int) or depth < 0:
                return {"error": "Depth must be a non-negative integer"}

            target = Path(path).expanduser().resolve()

            if not target.exists():
                return {"error": f"Path does not exist: {path}"}

            if not target.is_dir():
                return {"error": f"Path is not a directory: {path}"}

            items = []
            total_size = 0

            def scan_recursive(current_path: Path, current_depth: int):
                nonlocal total_size
                try:
                    for item in current_path.iterdir():
                        # Skip hidden files at root level
                        if item.name.startswith(".") and current_depth == 0:
                            continue

                        try:
                            if item.is_file():
                                size = item.stat().st_size
                            else:
                                size = FileSystemTools._get_dir_size(item)

                            total_size += size
                            size_mb = size / (1024 * 1024)

                            # Only include items above minimum size
                            if size_mb >= min_size_mb:
                                items.append({
                                    "path": str(item),
                                    "name": item.name,
                                    "is_directory": item.is_dir(),
                                    "size_bytes": size,
                                    "size_mb": size_mb,
                                    "size_gb": size / (1024 * 1024 * 1024),
                                })

                            # Recurse if directory and depth allows
                            if item.is_dir() and current_depth < depth:
                                scan_recursive(item, current_depth + 1)
                        except (PermissionError, OSError):
                            continue
                except (PermissionError, OSError):
                    pass

            scan_recursive(target, 0)

            # Sort by size
            items.sort(key=lambda x: x["size_bytes"], reverse=True)

            return {
                "path": str(target),
                "total_items": len(items),
                "total_size_bytes": total_size,
                "total_size_gb": total_size / (1024 * 1024 * 1024),
                "items": items[:20],  # Top 20
            }

        except Exception as e:
            return {"error": str(e)}
