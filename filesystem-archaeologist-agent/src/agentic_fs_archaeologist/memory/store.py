import sqlite3

from datetime import datetime
from pathlib import Path
from typing import (
    List,
    Optional,
)

from agentic_fs_archaeologist.config import get_settings
from agentic_fs_archaeologist.models import (
    ApprovalStatus,
    DeletionConfidence,
    DirectoryType,
    FileType,
    MemoryEntry,
)


class MemoryStore:
    """
    Used to implement a SQLite-based memory storage.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the SQLite-based memory  store.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.memory_db_path

        self.db_path = db_path
        self._init_db()

    def find_by_pattern(self, pattern: str) -> Optional[MemoryEntry]:
        """
        Helper function used to find entry by exact pattern match.

        Args:
            pattern: Path pattern to find

        Returns:
            MemoryEntry if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                path_pattern,
                file_type,
                directory_type,
                user_decision,
                confidence,
                approval_count,
                rejection_count,
                created_at,
                updated_at
            FROM
                memory_entries
            WHERE
                path_pattern = ?",
        """, (pattern,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_entry(row)
        return None

    def get_all(self, limit: int = 100) -> List[MemoryEntry]:
        """
        Helper function used to get all memory entries.

        Args:
            limit: Maximum number of entries

        Returns:
            List of MemoryEntry objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM memory_entries ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def _init_db(self):
        """
        Helper function used to initialize database schema.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path_pattern TEXT NOT NULL,
                file_type TEXT,
                directory_type TEXT,
                user_decision TEXT NOT NULL,
                confidence TEXT NOT NULL,
                approval_count INTEGER DEFAULT 0,
                rejection_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create index on path_pattern for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_path_pattern
            ON memory_entries(path_pattern)
        """)

        conn.commit()
        conn.close()

    def _row_to_entry(self, row) -> MemoryEntry:
        """
        Helper function used to convert a database row into an instance of
        `MemoryEntry`.

        Args:
            row: Database row tuple

        Returns:
            MemoryEntry object
        """
        r_dir_type = row["directory_type"]
        r_file_type = row["file_type"]
        return MemoryEntry(
            path_pattern=row["path_pattern"],
            file_type=FileType(r_file_type) if r_file_type else None,
            directory_type=DirectoryType(r_dir_type) if r_dir_type else None,
            user_decision=ApprovalStatus(row["user_decision"]),
            confidence=DeletionConfidence(row["confidence"]),
            approval_count=row["approval_count"],
            rejection_count=row["rejection_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )

    def save(self, entry: MemoryEntry):
        """
        Helper function used to save or update a memory entry.

        Args:
            entry: MemoryEntry to save
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if pattern exists
        cursor.execute("""
            SELECT
                id,
                approval_count,
                rejection_count
            FROM
                memory_entries
            WHERE
                path_pattern = ?",
        """, (entry.path_pattern,))
        existing = cursor.fetchone()

        if existing:
            # Update existing entry
            entry_id, approval_count, rejection_count = existing

            # Update counts based on decision
            if entry.user_decision == ApprovalStatus.APPROVED:
                approval_count += 1
            elif entry.user_decision == ApprovalStatus.REJECTED:
                rejection_count += 1

            cursor.execute("""
                UPDATE memory_entries
                SET
                    user_decision = ?,
                    confidence = ?,
                    approval_count = ?,
                    rejection_count = ?,
                    updated_at = ?
                WHERE
                    id = ?
            """, (
                entry.user_decision.value,
                entry.confidence.value,
                approval_count,
                rejection_count,
                datetime.now().isoformat(),
                entry_id
            ))
        else:
            # Insert new entry
            cursor.execute("""
                INSERT INTO memory_entries (
                    path_pattern,
                    file_type,
                    directory_type,
                    user_decision,
                    confidence,
                    approval_count,
                    rejection_count,
                    created_at,
                    updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.path_pattern,
                entry.file_type.value if entry.file_type else None,
                entry.directory_type.value if entry.directory_type else None,
                entry.user_decision.value,
                entry.confidence.value,
                1 if entry.user_decision == ApprovalStatus.APPROVED else 0,
                1 if entry.user_decision == ApprovalStatus.REJECTED else 0,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat()
            ))

        conn.commit()
        conn.close()

    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """
        Helper function used to search for entries matching query.

        Args:
            query: Search query (uses LIKE matching)
            limit: Maximum number of results

        Returns:
            List of matching MemoryEntry objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                path_pattern,
                file_type,
                directory_type,
                user_decision,
                confidence,
                approval_count,
                rejection_count,
                created_at,
                updated_at
            FROM
                memory_entries
            WHERE
                path_pattern LIKE ?
                LIMIT ?",
        """, ((f"%{query}%", limit)))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]
