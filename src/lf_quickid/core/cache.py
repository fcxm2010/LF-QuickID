from __future__ import annotations

import sqlite3
from pathlib import Path


class FaceCache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS image_cache (
                    path TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def is_current(self, path: Path, size: int, mtime_ns: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT size, mtime_ns FROM image_cache WHERE path = ?",
                (str(path),),
            ).fetchone()
        return row == (size, mtime_ns)

    def mark_current(self, path: Path, size: int, mtime_ns: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO image_cache(path, size, mtime_ns, updated_at)
                VALUES(?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(path), size, mtime_ns),
            )
