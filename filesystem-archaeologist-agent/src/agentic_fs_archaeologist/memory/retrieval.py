from pathlib import Path
from typing import List

from agentic_fs_archaeologist.memory.store import MemoryStore
from agentic_fs_archaeologist.models import MemoryEntry


class MemoryRetrieval:
    """
    Used to retrieve and match memory entries.
    """

    def __init__(self, store: MemoryStore):
        self.store = store or MemoryStore()

    def _extract_pattern(self, path: Path) -> str:
        """
        Helper function used to extract a pattern from a path for storage.

        Patterns are generalized versions of paths:
        - /home/user/code/project/node_modules → */node_modules
        - /home/user/file.extn → *.extn
        - /home/user/.cache/something → */.cache/*

        Args:
            path: Path to extract pattern from

        Returns:
            Pattern string
        """
        path_obj = Path(path)

        # Handle common directory patterns
        name = path_obj.name.lower()

        if name in ["node_modules", ".git", ".venv", "venv", "env"]:
            return f"*/{name}"

        if "cache" in name:
            return "*/cache/*"

        if name in ["build", "dist", "target", ".next", "out"]:
            return f"*/{name}"

        # Handle file extensions
        if path_obj.is_file() or path_obj.suffix:
            return f"*{path_obj.suffix}"

        # Default: use full name
        return f"*/{name}"

    async def find_similar(
            self,
            path: Path,
            limit: int = 5) -> List[MemoryEntry]:
        """
        Helper function used to find similar entries for a given path.

        This function uses the following matching strategies:
        1. Exact pattern match
        2. Extension match
        3. Parent directory match
        4. Name pattern match

        Args:
            path: Path to find similar entries for
            limit: Maximum number of results

        Returns:
            List of similar MemoryEntry objects, sorted by relevance
        """
        similar = []
        seen_patterns = set()

        # Strategy 1: Exact pattern match
        pattern = self._extract_pattern(path)
        exact = self.store.find_by_pattern(pattern)
        if exact and pattern not in seen_patterns:
            similar.append((exact, 1.0))  # Perfect match
            seen_patterns.add(pattern)

        # Strategy 2: Extension match (for files)
        if path.is_file() or not Path(path).exists():
            ext = Path(path).suffix
            if ext:
                entries = self.store.search(ext, limit=limit * 2)
                for entry in entries:
                    if entry.path_pattern not in seen_patterns:
                        similar.append((entry, 0.8))  # Good match
                        seen_patterns.add(entry.path_pattern)

        # Strategy 3: Parent directory pattern
        parent_name = Path(path).parent.name
        if parent_name:
            entries = self.store.search(parent_name, limit=limit * 2)
            for entry in entries:
                if entry.path_pattern not in seen_patterns:
                    similar.append((entry, 0.6))  # Moderate match
                    seen_patterns.add(entry.path_pattern)

        # Strategy 4: Name pattern
        name = Path(path).name
        entries = self.store.search(name, limit=limit * 2)
        for entry in entries:
            if entry.path_pattern not in seen_patterns:
                similar.append((entry, 0.4))  # Weak match
                seen_patterns.add(entry.path_pattern)

        # Sort by relevance score (descending)
        similar.sort(key=lambda x: x[1], reverse=True)

        # Return top results without scores
        return [entry for entry, score in similar[:limit]]
