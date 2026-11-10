"""Inspect and validate the SQLite schema. Run: python -m scripts.validate_schema"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import DEFAULT_DB_PATH, get_connection, initialize_database, table_names

EXPECTED_TABLES = {
    "investor_profile", "portfolio", "instrument", "holding", "market_price",
    "target_allocation", "trade", "fee_schedule", "constraint_rule",
    "rebalance_proposal", "entity_event",
}


def validate(db_path: Path = DEFAULT_DB_PATH) -> dict:
    initialize_database(db_path)
    checks: dict[str, bool] = {}
    details: dict = {}
    with get_connection(db_path) as conn:
        tables = set(table_names(conn))
        checks["expected_tables_present"] = EXPECTED_TABLES <= tables
        details["tables"] = sorted(tables)
        details["table_count"] = len(tables)
        pk_tables = []
        fk_tables = []
        for table in sorted(EXPECTED_TABLES):
            info = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
            if any(row[5] for row in info):
                pk_tables.append(table)
            if conn.execute(f"PRAGMA foreign_key_list('{table}')").fetchall():
                fk_tables.append(table)
        checks["all_tables_have_primary_key"] = len(pk_tables) == len(EXPECTED_TABLES)
        details["tables_with_primary_keys"] = pk_tables
        details["tables_with_foreign_keys"] = fk_tables
        checks["foreign_keys_enabled_on_application_connection"] = conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        checks["foreign_key_integrity"] = len(fk_violations) == 0
        details["foreign_key_violations"] = [tuple(row) for row in fk_violations]
        indexes = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchall()
        details["index_count"] = len(indexes)
        details["indexes"] = sorted(row[0] for row in indexes)
        checks["expected_indexes_present"] = len(indexes) >= 8
        triggers = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        details["trigger_count"] = len(triggers)
        details["triggers"] = sorted(row[0] for row in triggers)
        checks["lifecycle_and_audit_triggers_present"] = len(triggers) >= 4
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "details": details}


if __name__ == "__main__":
    result = validate()
    output = ROOT / "reports" / "schema_validation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
