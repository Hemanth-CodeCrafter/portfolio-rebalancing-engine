"""SQLite connection and schema initialization utilities."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "generated" / "database" / "portfolio_rebalancing.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a row-aware SQLite connection with FK enforcement enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> Path:
    """Create the database schema and return the database path."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(db_path) as connection:
        connection.executescript(schema)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise sqlite3.IntegrityError(f"Foreign-key violations after initialization: {violations}")
    return Path(db_path)


def table_names(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]
