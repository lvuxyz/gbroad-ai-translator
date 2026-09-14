"""SQLite Database manager for Translation History.

Stores translation events, supports full text search, deletion,
and honors Privacy Mode to protect sensitive data.
"""

import os
import sqlite3
import threading
import contextlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger()


class DatabaseManager:
    """Thread-safe SQLite database manager for translation history."""

    def __init__(self, db_dir: Optional[Path] = None):
        if db_dir is None:
            app_data = os.getenv("APPDATA")
            if app_data:
                self.db_dir = Path(app_data) / "AITranslator"
            else:
                self.db_dir = Path(__file__).resolve().parent
        else:
            self.db_dir = db_dir

        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "history.db"
        self._lock = threading.Lock()
        self._init_db()

    @contextlib.contextmanager
    def _connection(self):
        """Yields a managed SQLite connection and guarantees closing it."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Creates the necessary schema if it does not already exist."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS translations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_text TEXT NOT NULL,
                        translated_text TEXT NOT NULL,
                        source_language TEXT NOT NULL,
                        target_language TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_translations_created_at
                    ON translations(created_at DESC);
                """)
                conn.commit()
                logger.info("Database initialized at %s", self.db_path)

    def add_translation(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        provider: str,
        privacy_mode: bool = False,
        history_enabled: bool = True
    ) -> Optional[int]:
        """Inserts a translation record if history is enabled and privacy mode is off."""
        if privacy_mode or not history_enabled:
            logger.debug("Translation not saved (Privacy Mode or History disabled)")
            return None

        if not source_text.strip():
            return None

        with self._lock:
            try:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO translations (
                            source_text,
                            translated_text,
                            source_language,
                            target_language,
                            provider
                        ) VALUES (?, ?, ?, ?, ?);
                    """, (
                        source_text,
                        translated_text,
                        source_language,
                        target_language,
                        provider
                    ))
                    conn.commit()
                    inserted_id = cursor.lastrowid
                    logger.debug("Translation record inserted with ID %s", inserted_id)
                    return inserted_id
            except Exception as e:
                logger.error("Failed to insert translation to DB: %s", e)
                return None

    def search_translations(
        self,
        query: str = "",
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Searches translations matching query in source or translated text."""
        with self._lock:
            try:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    if query.strip():
                        search_term = f"%{query.strip()}%"
                        cursor.execute("""
                            SELECT id, source_text, translated_text, source_language,
                                   target_language, provider, created_at
                            FROM translations
                            WHERE source_text LIKE ? OR translated_text LIKE ?
                            ORDER BY id DESC
                            LIMIT ? OFFSET ?;
                        """, (search_term, search_term, limit, offset))
                    else:
                        cursor.execute("""
                            SELECT id, source_text, translated_text, source_language,
                                   target_language, provider, created_at
                            FROM translations
                            ORDER BY id DESC
                            LIMIT ? OFFSET ?;
                        """, (limit, offset))

                    rows = cursor.fetchall()
                    return [dict(row) for row in rows]
            except Exception as e:
                logger.error("Failed to query translation history: %s", e)
                return []

    def delete_translation(self, item_id: int) -> bool:
        """Deletes a single translation entry by ID."""
        with self._lock:
            try:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM translations WHERE id = ?;", (item_id,))
                    conn.commit()
                    deleted = cursor.rowcount > 0
                    logger.info("Deleted translation ID %s (success=%s)", item_id, deleted)
                    return deleted
            except Exception as e:
                logger.error("Failed to delete translation ID %s: %s", item_id, e)
                return False

    def clear_history(self) -> bool:
        """Clears all translation history records."""
        with self._lock:
            try:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM translations;")
                    conn.commit()
                    logger.info("All translation history cleared")
                    return True
            except Exception as e:
                logger.error("Failed to clear translation history: %s", e)
                return False

    def get_count(self) -> int:
        """Returns the total number of translation records."""
        with self._lock:
            try:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM translations;")
                    result = cursor.fetchone()
                    return result[0] if result else 0
            except Exception as e:
                logger.error("Failed to get translation count: %s", e)
                return 0


# Singleton instance
_db_instance: Optional[DatabaseManager] = None


def get_database() -> DatabaseManager:
    """Gets or initializes the global DatabaseManager singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
