from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.database import get_connection, initialize_database, table_names


@pytest.fixture

def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    initialize_database(path)
    return path


def seed_parent(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO investor_profile VALUES (?,?,?,?,?,?)",
        ("INV-000001", "Test Investor", "test@example.com", "MODERATE", "2026-01-01T00:00:00", "ACTIVE"),
    )
    conn.execute(
        "INSERT INTO portfolio VALUES (?,?,?,?,?,?)",
        ("PORT-INV-000001-01", "INV-000001", "Primary", "INR", "2026-01-01T00:00:00", "ACTIVE"),
    )
    conn.execute(
        "INSERT INTO instrument VALUES (?,?,?,?,?,?,?,?)",
        ("INS-000001", "SIMEQ", "Synthetic Equity", "EQUITY", "ETF", "INR", 1, 0),
    )


def test_schema_has_eleven_tables_and_primary_keys(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        names = table_names(conn)
        assert len(names) == 11
        for table in names:
            columns = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
            assert any(column[5] for column in columns), table


def test_application_connection_enforces_foreign_keys(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO portfolio VALUES (?,?,?,?,?,?)",
                ("PORT-INV-999999-01", "INV-999999", "Orphan", "INR", "2026-01-01", "ACTIVE"),
            )


def test_invalid_risk_profile_is_rejected(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO investor_profile VALUES (?,?,?,?,?,?)",
                ("INV-000001", "Bad Risk", "bad@example.com", "ULTRA", "2026-01-01", "ACTIVE"),
            )


def test_duplicate_primary_key_is_rejected(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        seed_parent(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO investor_profile VALUES (?,?,?,?,?,?)",
                ("INV-000001", "Duplicate", "other@example.com", "MODERATE", "2026-01-02", "ACTIVE"),
            )


def test_negative_holding_quantity_is_rejected(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        seed_parent(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO holding VALUES (?,?,?,?,?,?)",
                ("HOLD-PORT-INV-000001-01-INS-000001", "PORT-INV-000001-01", "INS-000001", "-1", "2026-01-01", "2026-01-01T00:00:00"),
            )


def test_valid_parent_child_inserts_and_constraint_scope(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        seed_parent(conn)
        conn.execute(
            "INSERT INTO holding VALUES (?,?,?,?,?,?)",
            ("HOLD-PORT-INV-000001-01-INS-000001", "PORT-INV-000001-01", "INS-000001", "10", "2026-01-01", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO constraint_rule VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("CON-000001", "PORT-INV-000001-01", None, "MIN_TRADE_SIZE", "GTE", "500", "INR", "2026-01-01", None, "ACTIVE"),
        )
        assert conn.execute("SELECT COUNT(*) FROM holding").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO constraint_rule VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("CON-000002", "PORT-INV-000001-01", "INS-000001", "MIN_TRADE_SIZE", "GTE", "500", "INR", "2026-01-01", None, "ACTIVE"),
            )


def test_duplicate_holding_snapshot_is_rejected(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        seed_parent(conn)
        row = ("HOLD-PORT-INV-000001-01-INS-000001", "PORT-INV-000001-01", "INS-000001", "10", "2026-01-01", "2026-01-01T00:00:00")
        conn.execute("INSERT INTO holding VALUES (?,?,?,?,?,?)", row)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO holding VALUES (?,?,?,?,?,?)", row)


def test_lifecycle_transition_rules_reject_reopening_rejected_proposal(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        seed_parent(conn)
        conn.execute(
            "INSERT INTO rebalance_proposal VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("RB-2026-000001", "PORT-INV-000001-01", "2026-01-01", "REJECTED", "1000", None, "0", None, 0, "{}", "2026-01-01T00:00:00"),
        )
        with pytest.raises(sqlite3.IntegrityError, match="lifecycle transition"):
            conn.execute("UPDATE rebalance_proposal SET status='GENERATED' WHERE proposal_id='RB-2026-000001'")


def test_entity_event_is_append_only(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO entity_event VALUES (?,?,?,?,?,?,?,?)",
            ("EVT-000000001", "PORTFOLIO", "PORT-INV-000001-01", "CREATED", None, "ACTIVE", "2026-01-01T00:00:00", "test"),
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE entity_event SET reason='changed' WHERE event_id='EVT-000000001'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM entity_event WHERE event_id='EVT-000000001'")
