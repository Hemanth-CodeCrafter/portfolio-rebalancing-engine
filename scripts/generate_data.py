"""Deterministic synthetic portfolio data generator.

Usage:
  python -m scripts.generate_data --scale starter
  python -m scripts.generate_data --scale full
  python -m scripts.generate_data --scale starter --seed 20261022
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import DEFAULT_DB_PATH, initialize_database, get_connection

SEED = 20261022
ASSET_CLASSES = ("EQUITY", "DEBT", "GOLD", "CASH", "OTHER")
RISK_TARGETS = {
    "CONSERVATIVE": (30, 45, 10, 10, 5),
    "MODERATE": (50, 25, 10, 10, 5),
    "AGGRESSIVE": (70, 10, 10, 5, 5),
}
SCALE_CONFIG = {
    "starter": {"portfolios": 10, "instruments": 10, "trading_days": 30, "holdings_per_portfolio": 5},
    "full": {"portfolios": 1000, "instruments": 50, "trading_days": 250, "holdings_per_portfolio": 5},
}
CENT = Decimal("0.01")
QTY = Decimal("0.0001")


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def quantity(value: Decimal) -> str:
    return str(value.quantize(QTY, rounding=ROUND_HALF_UP))


def iso_now() -> str:
    return "2026-11-10T00:00:00+05:30"


def trading_dates(count: int, end: date = date(2026, 11, 9)) -> list[date]:
    result: list[date] = []
    cursor = end
    while len(result) < count:
        if cursor.weekday() < 5:
            result.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(result)


def create_master_data(conn: sqlite3.Connection, rng: random.Random, cfg: dict) -> dict:
    n_port = cfg["portfolios"]
    n_inst = cfg["instruments"]
    per_port = cfg["holdings_per_portfolio"]
    if n_inst < len(ASSET_CLASSES) or n_inst % len(ASSET_CLASSES) != 0:
        raise ValueError("Instrument count must be divisible by five asset classes")
    stamp = iso_now()
    investors = []
    portfolios = []
    instruments = []
    for i in range(1, n_port + 1):
        risk = rng.choices(["CONSERVATIVE", "MODERATE", "AGGRESSIVE"], [0.3, 0.5, 0.2])[0]
        investor_id = f"INV-{i:06d}"
        investors.append((investor_id, f"Synthetic Investor {i:04d}", f"investor{i:06d}@example.test", risk, stamp, "ACTIVE"))
        portfolios.append((f"PORT-{investor_id}-01", investor_id, f"Portfolio {i:04d}", "INR", stamp, "ACTIVE"))
    by_class: dict[str, list[str]] = {a: [] for a in ASSET_CLASSES}
    for i in range(1, n_inst + 1):
        asset = ASSET_CLASSES[(i - 1) % len(ASSET_CLASSES)]
        instrument_id = f"INS-{i:06d}"
        excluded = 1 if i % 17 == 0 else 0
        symbol = f"SYN{i:04d}"
        instruments.append((instrument_id, symbol, f"Synthetic {asset.title()} Instrument {i:04d}", asset, "ETF" if asset != "CASH" else "DEPOSIT", "INR", 1, excluded))
        by_class[asset].append(instrument_id)
    conn.executemany("INSERT INTO investor_profile VALUES (?,?,?,?,?,?)", investors)
    conn.executemany("INSERT INTO portfolio VALUES (?,?,?,?,?,?)", portfolios)
    conn.executemany("INSERT INTO instrument VALUES (?,?,?,?,?,?,?,?)", instruments)
    return {"investors": investors, "portfolios": portfolios, "instruments": instruments, "by_class": by_class}


def create_prices(conn: sqlite3.Connection, rng: random.Random, instruments: list, days: int) -> tuple[dict, list]:
    dates = trading_dates(days)
    latest_prices: dict[str, tuple[Decimal, date, int]] = {}
    rows = []
    seq = 0
    for inst in instruments:
        iid, _, _, asset, _, currency, _, _ = inst
        base = Decimal(str(rng.uniform(50, 1500))).quantize(CENT)
        price = base
        vol_base = {"EQUITY": 0.018, "DEBT": 0.004, "GOLD": 0.010, "CASH": 0.0002, "OTHER": 0.015}[asset]
        for d in dates:
            price = max(Decimal("1"), price * Decimal(str(1 + rng.gauss(0.0002, vol_base))))
            if rng.random() < 0.0015:
                continue  # intentionally missing observation; never fabricate a row
            seq += 1
            stale = 1 if rng.random() < 0.002 else 0
            volume = Decimal(str(rng.randint(1000, 250000)))
            row = (f"MP-{seq:09d}", iid, d.isoformat(), money(price), currency, "SYNTHETIC_FIXED_SEED", stale, str(volume), iso_now())
            rows.append(row)
            if iid not in latest_prices or d > latest_prices[iid][1]:
                latest_prices[iid] = (price.quantize(CENT), d, stale)
    conn.executemany("INSERT INTO market_price VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return latest_prices, dates


def create_dependent_data(conn: sqlite3.Connection, rng: random.Random, masters: dict, latest_prices: dict) -> dict:
    holdings, targets, fees, constraints = [], [], [], []
    stamp = iso_now()
    fee_ids = {}
    for idx, asset in enumerate(ASSET_CLASSES, 1):
        low_id, high_id = f"FEE-{idx:03d}-T1", f"FEE-{idx:03d}-T2"
        fee_ids[asset] = (low_id, high_id)
        fees.append((low_id, asset, "500.00", "100000.00", "FIXED", "0", "15.00", "2026-01-01", None, "ACTIVE"))
        fees.append((high_id, asset, "100000.01", "5000000.00", "HYBRID", "0.001", "10.00", "2026-01-01", None, "ACTIVE"))
    conn.executemany("INSERT INTO fee_schedule VALUES (?,?,?,?,?,?,?,?,?,?)", fees)
    price_lookup = {iid: val[0] for iid, val in latest_prices.items()}
    instrument_map = {r[0]: r for r in masters["instruments"]}
    investor_risk = {r[0]: r[3] for r in masters["investors"]}
    for p_idx, portfolio in enumerate(masters["portfolios"], 1):
        pid, investor_id = portfolio[0], portfolio[1]
        risk = investor_risk[investor_id]
        target = RISK_TARGETS[risk]
        for asset, weight in zip(ASSET_CLASSES, target):
            targets.append((f"TA-{p_idx:06d}-{ASSET_CLASSES.index(asset)+1:02d}", pid, asset, str(weight), "2026-01-01", None, stamp))
        total = Decimal(str(rng.randint(250000, 5000000)))
        raw_weights = [Decimal(str(w)) + Decimal(str(rng.uniform(-3, 3))) for w in target]
        if p_idx % 10 == 0:  # 10% high-drift portfolios; still valid weights
            raw_weights[0] += Decimal("10")
            raw_weights[1] -= Decimal("6")
        raw_total = sum(raw_weights)
        current_weights = [w * Decimal("100") / raw_total for w in raw_weights]
        as_of = max(v[1] for v in latest_prices.values()).isoformat()
        for slot, asset in enumerate(ASSET_CLASSES):
            candidates = masters["by_class"][asset]
            iid = candidates[(p_idx * 7 + slot * 3) % len(candidates)]
            price = price_lookup[iid]
            market_value = total * current_weights[slot] / Decimal("100")
            qty = market_value / price
            holding_id = f"HOLD-{pid}-{iid}"
            holdings.append((holding_id, pid, iid, quantity(qty), as_of, stamp))
        constraints.append((f"CON-{p_idx:06d}-MIN", pid, None, "MIN_TRADE_SIZE", "GTE", "500", "INR", "2026-01-01", None, "ACTIVE"))
        if p_idx % 20 == 0:
            constraints.append((f"CON-{p_idx:06d}-MAX", pid, None, "MAX_TRADE_SIZE", "LTE", "250000", "INR", "2026-01-01", None, "ACTIVE"))
    for i, inst in enumerate(masters["instruments"], 1):
        iid, _, _, asset, _, _, _, excluded = inst
        if excluded:
            constraints.append((f"CON-INS-{i:06d}", None, iid, "EXCLUDED_INSTRUMENT", "EQ", "1", "FLAG", "2026-01-01", None, "ACTIVE"))
        if i % 13 == 0:
            constraints.append((f"CON-LIQ-{i:06d}", None, iid, "MIN_LIQUIDITY", "GTE", "5000", "UNITS", "2026-01-01", None, "ACTIVE"))
    conn.executemany("INSERT INTO target_allocation VALUES (?,?,?,?,?,?,?)", targets)
    conn.executemany("INSERT INTO holding VALUES (?,?,?,?,?,?)", holdings)
    conn.executemany("INSERT INTO constraint_rule VALUES (?,?,?,?,?,?,?,?,?,?)", constraints)
    return {"holdings": holdings, "targets": targets, "fees": fees, "constraints": constraints}


def export_tables(conn: sqlite3.Connection) -> dict:
    csv_dir = ROOT / "data/generated/csv"
    json_dir = ROOT / "data/generated/json"
    csv_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in tables:
        cursor = conn.execute(f'SELECT * FROM "{table}" ORDER BY 1')
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        counts[table] = len(rows)
        with (csv_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        (json_dir / f"{table}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (ROOT / "data/generated/database/seed.sql").open("w", encoding="utf-8") as f:
        for line in conn.iterdump():
            f.write(line + "\n")
    return counts


def create_anomaly_fixtures() -> None:
    """Create isolated negative test inputs; expected labels live in a separate file."""
    anomaly_dir = ROOT / "data/anomalies"
    truth_dir = ROOT / "data/ground_truth"
    anomaly_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    cases = [
        {"case_id": "ANOM-001", "scenario": "portfolio_weight_total", "input": {"weights": {"EQUITY": 60, "DEBT": 30, "GOLD": 10, "CASH": 5, "OTHER": 0}}},
        {"case_id": "ANOM-002", "scenario": "sell_exceeds_holding", "input": {"available_quantity": "10", "proposed_sell_quantity": "12"}},
        {"case_id": "ANOM-003", "scenario": "excluded_instrument_recommended", "input": {"instrument_id": "INS-000017", "is_excluded": True, "recommended_side": "BUY"}},
        {"case_id": "ANOM-004", "scenario": "fee_omitted", "input": {"fee_schedule_required": True, "fee_schedule_id": None, "estimated_fee": None}},
        {"case_id": "ANOM-005", "scenario": "stale_price_unflagged", "input": {"price_age_days": 12, "is_stale": False, "max_price_age_days": 5}},
    ]
    truth = [
        {"case_id": "ANOM-001", "issue_type": "PORTFOLIO_WEIGHT_NOT_100", "expected_decision": "REJECT_INPUT", "rule_id": "VAL-PORTFOLIO-001"},
        {"case_id": "ANOM-002", "issue_type": "SELL_EXCEEDS_HOLDING", "expected_decision": "REJECT_TRADE", "rule_id": "POL-SELL-001"},
        {"case_id": "ANOM-003", "issue_type": "EXCLUDED_INSTRUMENT_RECOMMENDED", "expected_decision": "REJECT_TRADE", "rule_id": "POL-EXCLUDE-001"},
        {"case_id": "ANOM-004", "issue_type": "FEE_OMITTED", "expected_decision": "REVIEW_REQUIRED", "rule_id": "POL-FEE-001"},
        {"case_id": "ANOM-005", "issue_type": "STALE_PRICE_UNFLAGGED", "expected_decision": "REVIEW_REQUIRED", "rule_id": "VAL-PRICE-002"},
    ]
    (anomaly_dir / "anomaly_cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    with (truth_dir / "ground_truth.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(truth[0]))
        writer.writeheader()
        writer.writerows(truth)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=tuple(SCALE_CONFIG), default="starter")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    cfg = SCALE_CONFIG[args.scale]
    db_path = DEFAULT_DB_PATH
    # A generation run is an explicit full dataset reset. Recreate the DB file
    # rather than deleting append-only audit events through SQL.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()
    initialize_database(db_path)
    rng = random.Random(args.seed)
    with get_connection(db_path) as conn:
        conn.execute("PRAGMA defer_foreign_keys = ON")
        for table in ("trade", "rebalance_proposal", "entity_event", "constraint_rule", "target_allocation", "holding", "market_price", "fee_schedule", "instrument", "portfolio", "investor_profile"):
            conn.execute(f'DELETE FROM "{table}"')
        masters = create_master_data(conn, rng, cfg)
        latest_prices, dates = create_prices(conn, rng, masters["instruments"], cfg["trading_days"])
        dependent = create_dependent_data(conn, rng, masters, latest_prices)
    with get_connection(db_path) as conn:
        counts = export_tables(conn)
    create_anomaly_fixtures()
    manifest = {
        "project": "Portfolio Rebalancing Engine", "dataset_type": args.scale,
        "seed": args.seed, "generated_at": iso_now(), "generator": "scripts/generate_data.py",
        "parameters": cfg, "date_start": dates[0].isoformat(), "date_end": dates[-1].isoformat(),
        "row_counts": counts, "provenance": "Entirely synthetic; no external personal or financial data used.",
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"status": "GENERATED", "database": str(db_path), "row_counts": counts, "seed": args.seed}, indent=2))


if __name__ == "__main__":
    main()
