"""Re-export the current SQLite database to CSV, JSON and SQL seed files."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import DEFAULT_DB_PATH, get_connection
from scripts.generate_data import export_tables

if __name__ == "__main__":
    if not DEFAULT_DB_PATH.exists():
        raise SystemExit("Database not found. Run python -m scripts.generate_data first.")
    with get_connection(DEFAULT_DB_PATH) as connection:
        print(export_tables(connection))
