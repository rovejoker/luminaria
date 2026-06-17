"""SQLite database with WAL mode — init schema and CRUD for generations."""
import sqlite3
import os
from app.config import DB_PATH, DATA_DIR


def _get_connection() -> sqlite3.Connection:
    """Create a new connection with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Call once on startup."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_input TEXT NOT NULL,
            prompt_enhanced TEXT,
            duration INTEGER NOT NULL,
            filename TEXT NOT NULL,
            enhanced INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def insert_generation(user_input: str, prompt_enhanced: str | None, duration: int, filename: str, enhanced: bool) -> int:
    """Insert a new generation record. Returns the new row ID."""
    conn = _get_connection()
    cursor = conn.execute(
        "INSERT INTO generations (user_input, prompt_enhanced, duration, filename, enhanced) VALUES (?, ?, ?, ?, ?)",
        (user_input, prompt_enhanced, duration, filename, 1 if enhanced else 0)
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_history(limit: int = 50) -> list[dict]:
    """Return recent generations, newest first."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT id, created_at, user_input, duration, filename, enhanced FROM generations ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_generation(generation_id: int) -> dict | None:
    """Return a single generation by ID, or None."""
    conn = _get_connection()
    row = conn.execute(
        "SELECT id, created_at, user_input, prompt_enhanced, duration, filename, enhanced FROM generations WHERE id = ?",
        (generation_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_generation(generation_id: int) -> bool:
    """Delete a generation record. Returns True if a row was deleted."""
    conn = _get_connection()
    cursor = conn.execute("DELETE FROM generations WHERE id = ?", (generation_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def delete_all_generations() -> list[str]:
    """Delete ALL generation records. Returns list of deleted filenames."""
    conn = _get_connection()
    rows = conn.execute("SELECT filename FROM generations").fetchall()
    filenames = [r["filename"] for r in rows]
    conn.execute("DELETE FROM generations")
    conn.commit()
    conn.close()
    return filenames
