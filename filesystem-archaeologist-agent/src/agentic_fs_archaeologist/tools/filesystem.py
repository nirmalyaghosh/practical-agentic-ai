import csv
import os
import platform
import shutil
import string
import time

from datetime import datetime
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
                        for line in gitignore_content.split("\n"):
                            line = line.strip()
                            if line and not line.startswith("#"):
                                # Simple pattern matching
                                pattern = line.rstrip("/")
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
    def get_disk_usage(path: str) -> Dict:
        """
        Helper function used to get disk usage statistics for the given
        path/drive.
        """
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return {"error": "Path does not exist"}

            usage = shutil.disk_usage(target)
            free_percent = (usage.free / usage.total * 100) \
                if usage.total > 0 else 0
            return {
                "path": path,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "free_percent": free_percent,
            }
        except Exception as e:
            return {"error": str(e)}

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
    def get_file_size(path: str) -> int:
        try:
            stat = os.stat(path)
            if os.path.isdir(path):
                size = FileSystemTools._get_dir_size(Path(path))
            else:
                size = stat.st_size
        except (OSError, PermissionError):
            size = 0

        return size

    @staticmethod
    def get_recycle_bin_stats() -> Dict:
        """
        Helper function used to get recycle bin statistics by calculating
        total size of recycle bin folders.
        """

        system = platform.system()
        total_size = 0
        drives_checked = []
        try:
            if system == "Windows":
                for drive_letter in string.ascii_uppercase:
                    drive_root = f"{drive_letter}:\\"
                    if Path(drive_root).exists():
                        recycle_bin_path = Path(f"{drive_root}$RECYCLE.BIN")
                        if recycle_bin_path.exists() \
                                and recycle_bin_path.is_dir():
                            drives_checked.append(drive_letter)
                            try:
                                size = FileSystemTools._get_dir_size(
                                    path=recycle_bin_path)
                                total_size += size
                            except Exception:
                                continue

            elif system == "Darwin":  # macOS (warning: untested)
                trash_path = Path.home() / ".Trash"
                if trash_path.exists():
                    drives_checked.append("macOS_Trash")
                    try:
                        total_size = FileSystemTools._get_dir_size(trash_path)
                    except Exception:
                        pass

            elif system == "Linux":  # (warning: untested)
                trash_path =\
                    Path.home() / ".local" / "share" / "Trash" / "files"
                if trash_path.exists():
                    drives_checked.append("Linux_Trash")
                    try:
                        total_size = FileSystemTools._get_dir_size(trash_path)
                    except Exception:
                        pass

            status = "success" if len(drives_checked) > 0 \
                else "no_recycle_bin_found"

            return {
                "total_size_bytes": total_size,
                "size_gb": total_size / (1024 * 1024 * 1024),
                "drives_checked": drives_checked,
                "status": status,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def is_system_path(path: str) -> bool:
        """
        Helper function used to check if path is a system director.
        """
        if platform.system() == "Windows":
            return path.upper().startswith((
                "C:\\WINDOWS",
                "C:\\PROGRAM FILES",
                "C:\\$RECYCLE.BIN"
            ))
        return False

    @staticmethod
    def monitor_filesystem(
            path: str = "~",
            csv_file: str = "filesystem_monitor.csv") -> Dict:
        """
        Helper function used to monitor filesystem using tree-like traversal,
        save paths to CSV with timestamps and priorities.
        """
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return {"error": f"Path does not exist: {path}"}

            paths_found = {}
            # Tree traversal
            for root, dirs, files in os.walk(target):
                for name in files + dirs:
                    full_path = os.path.join(root, name)
                    is_syspath = FileSystemTools.is_system_path(path=full_path)
                    priority = 0 if is_syspath else 1
                    size = FileSystemTools.get_file_size(path=full_path)
                    paths_found[full_path] = (priority, size)

            # Load existing CSV
            existing = {}
            if os.path.exists(csv_file):
                with open(csv_file, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        lv = datetime.fromisoformat(row["last_visited"])
                        size_bytes = int(row.get("size_bytes", 0)) \
                            if "size_bytes" in row else 0
                        existing[row["path"]] =\
                            (lv, int(row["priority"]), size_bytes)

            # Iterate/create entries
            default_ts = datetime(2026, 1, 1, 0, 0, 0)
            updated = []
            for p, (pri, sz) in paths_found.items():
                if p in existing:
                    existing_ts = existing[p][0]
                    updated.append((p, existing_ts, pri, sz))
                else:
                    updated.append((p, default_ts, pri, sz))  # New entry

            # For unchanged paths, keep existing
            for p, (ts, pri, sz) in existing.items():
                if p not in paths_found:
                    updated.append((p, ts, pri, sz))

            # Save CSV
            col_names = ["path", "last_visited", "priority", "size_bytes"]
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(col_names)
                for p, ts, pri, sz in updated:
                    writer.writerow([p, ts.isoformat(), pri, sz])

            return {
                "scanned_paths": len(paths_found),
                "total_monitored": len(updated),
                "csv_file": csv_file
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
