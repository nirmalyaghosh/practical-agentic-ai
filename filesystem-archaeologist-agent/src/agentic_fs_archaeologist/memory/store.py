import json

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
    ReflectionOutcome,
    ReflectionMetrics,
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
        conn.row_factory = sqlite3.Row
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
                path_pattern = ?
        """, (pattern,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_entry(row)
        return None

    def _generate_improvement_suggestions(
            self,
            accuracy_rate: float,
            error_patterns: List[str]) -> List[str]:
        """
        Helper function used to generate improvement suggestions
        based on metrics.

        Args:
            accuracy_rate: Overall accuracy rate
            error_patterns: List of common error patterns

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        if accuracy_rate < 0.8:
            suggestions.append("Overall accuracy below 80%"
                               " - review reflection criteria")

        if error_patterns:
            suggestions.append("Address low-accuracy decisions: "
                               f"{', '.join(error_patterns[:2])}")

        if not suggestions:
            suggestions.append("Reflection performance is good"
                               " - continue monitoring")

        return suggestions

    def get_all(self, limit: int = 100) -> List[MemoryEntry]:
        """
        Helper function used to get all memory entries.

        Args:
            limit: Maximum number of entries

        Returns:
            List of MemoryEntry objects
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM memory_entries ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def get_reflection_history(
            self,
            path_pattern: str,
            limit: int = 10) -> List[ReflectionOutcome]:
        """
        Helper function used to get the reflection history for a path pattern.

        Args:
            path_pattern: Path pattern to search for
            limit: Maximum number of results

        Returns:
            List of ReflectionOutcome objects
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                path,
                decision,
                reasoning,
                accuracy_confirmed,
                confidence_before,
                confidence_after,
                context,
                timestamp
            FROM
                reflection_history
            WHERE
                path LIKE ?
            ORDER BY
                timestamp DESC
            LIMIT ?
        """, (f"%{path_pattern}%", limit))

        rows: List[sqlite3.Row] = cursor.fetchall()
        conn.close()

        outcomes = []
        for row in rows:
            outcomes.append(ReflectionOutcome(
                path=Path(row["path"]),
                decision=row["decision"],
                reasoning=row["reasoning"],
                accuracy_confirmed=row["accuracy_confirmed"],
                confidence_before=DeletionConfidence(row["confidence_before"]),
                confidence_after=DeletionConfidence(row["confidence_after"]),
                context=json.loads(row["context"]) if row["context"] else {},
                timestamp=datetime.fromisoformat(row["timestamp"])
            ))

        return outcomes

    def get_reflection_metrics(self) -> ReflectionMetrics:
        """
        Helper function used to calculate the reflection metrics from the
        database.

        Returns:
            ReflectionMetrics object
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get total reflections
        cursor.execute("SELECT COUNT(*) FROM reflection_history")
        total_reflections = cursor.fetchone()[0]

        # Get accuracy rate for confirmed outcomes
        cursor.execute("""
            SELECT
                COUNT(*) as total_confirmed,
                SUM(CASE WHEN accuracy_confirmed = 1 THEN 1 ELSE 0 END)
                as correct
            FROM reflection_history
            WHERE accuracy_confirmed IS NOT NULL
        """)
        row = cursor.fetchone()
        total_confirmed = row[0] if row[0] else 0
        correct = row[1] if row[1] else 0
        accuracy_rate = correct / total_confirmed \
            if total_confirmed > 0 else 0.0

        # Get common error patterns (decisions with low accuracy)
        cursor.execute("""
            SELECT decision,
                COUNT(*) as total,
                AVG(CASE WHEN accuracy_confirmed = 1 THEN 1.0 ELSE 0.0 END)
                as acc_rate
            FROM reflection_history
            WHERE accuracy_confirmed IS NOT NULL
            GROUP BY decision
            HAVING acc_rate < 0.8 AND total >= 3
            ORDER BY total DESC
            LIMIT 5
        """)
        error_rows = cursor.fetchall()
        common_error_patterns = [f"{row[0]} ({row[2]:.1%} accuracy)"
                                 for row in error_rows]

        conn.close()

        return ReflectionMetrics(
            total_reflections=total_reflections,
            accuracy_rate=accuracy_rate,
            common_error_patterns=common_error_patterns,
            improvement_suggestions=self._generate_improvement_suggestions(
                accuracy_rate=accuracy_rate,
                error_patterns=common_error_patterns)
        )

    def _init_db(self):
        """
        Helper function used to initialise the database schema.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        self._init_table_memory_entries(cursor=cursor)
        self._init_table_reflection_history(cursor=cursor)
        conn.commit()
        conn.close()

    def _init_table_memory_entries(self, cursor: sqlite3.Cursor):
        """
        Helper function used to initialise the `memory_entries` table
        (used for classification learning).
        """
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

    def _init_table_reflection_history(self, cursor: sqlite3.Cursor):
        """
        Helper function used to initialise the `reflection_history` table
        (used for reflection learning).

        Noteable fields:
        - `accuracy_confirmed` is stored as INTEGER: NULL=unconfirmed,
        0=false, 1=true
        - `context` is stored as JSON string
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reflection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                decision TEXT NOT NULL,
                reasoning TEXT,
                accuracy_confirmed INTEGER,
                confidence_before TEXT NOT NULL,
                confidence_after TEXT NOT NULL,
                context TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        # Create index on path for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reflection_path
            ON reflection_history(path)
        """)

        # Create index on timestamp for ordering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reflection_timestamp
            ON reflection_history(timestamp)
        """)

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
                path_pattern = ?
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

    def save_reflection_outcome(self, outcome: ReflectionOutcome):
        """
        Helper function used to save a reflection outcome to the database.

        Args:
            outcome: ReflectionOutcome to save
        """

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reflection_history (
                path,
                decision,
                reasoning,
                accuracy_confirmed,
                confidence_before,
                confidence_after,
                context,
                timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(outcome.path),
            outcome.decision,
            outcome.reasoning,
            outcome.accuracy_confirmed,
            outcome.confidence_before.value,
            outcome.confidence_after.value,
            json.dumps(outcome.context),
            outcome.timestamp.isoformat()
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
        conn.row_factory = sqlite3.Row
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
                LIMIT ?
        """, (f"%{query}%", limit))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def update_reflection_accuracy(self, path: str, confirmed: bool):
        """
        Helper function used to update the accuracy confirmation for reflection
        outcomes at a specific path.

        Args:
            path: Path to update
            confirmed: Whether the reflection was accurate
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE reflection_history
            SET accuracy_confirmed = ?
            WHERE path = ?
        """, (1 if confirmed else 0, path))

        conn.commit()
        conn.close()
