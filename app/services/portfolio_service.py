"""Portfolio valuation and allocation drift calculations using Decimal."""
from __future__ import annotations
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from app.database import DEFAULT_DB_PATH, get_connection

D = Decimal
ZERO = D("0")
HUNDRED = D("100")


def _latest_price(conn, instrument_id: str, as_of_date: str):
    return conn.execute("""SELECT * FROM market_price WHERE instrument_id=? AND price_date<=?
        ORDER BY price_date DESC, market_price_id DESC LIMIT 1""", (instrument_id, as_of_date)).fetchone()


def analyze_portfolio(portfolio_id: str, as_of_date: str | None = None, db_path: Path = DEFAULT_DB_PATH) -> dict:
    with get_connection(db_path) as conn:
        portfolio = conn.execute("SELECT * FROM portfolio WHERE portfolio_id=?", (portfolio_id,)).fetchone()
        if portfolio is None:
            raise ValueError(f"Portfolio not found: {portfolio_id}")
        if as_of_date is None:
            row = conn.execute("SELECT MAX(as_of_date) FROM holding WHERE portfolio_id=?", (portfolio_id,)).fetchone()
            as_of_date = row[0]
        if not as_of_date:
            raise ValueError("Portfolio has no holdings to analyze")
        holdings = conn.execute("""SELECT h.*, i.symbol, i.asset_class, i.is_excluded, i.is_active
            FROM holding h JOIN instrument i ON i.instrument_id=h.instrument_id
            WHERE h.portfolio_id=? AND h.as_of_date<=? ORDER BY h.instrument_id""", (portfolio_id, as_of_date)).fetchall()
        targets = conn.execute("""SELECT asset_class, target_weight_pct FROM target_allocation
            WHERE portfolio_id=? AND effective_from<=? AND (effective_to IS NULL OR effective_to>=?)""",
            (portfolio_id, as_of_date, as_of_date)).fetchall()
        target_by_class = {r["asset_class"]: D(r["target_weight_pct"]) for r in targets}
        target_total = sum(target_by_class.values(), ZERO)
        if abs(target_total - HUNDRED) > D("0.000001"):
            raise ValueError(f"Target allocation must total 100%; found {target_total}")
        current_by_class = defaultdict(lambda: ZERO)
        position_rows, exceptions = [], []
        total = ZERO
        for h in holdings:
            price = _latest_price(conn, h["instrument_id"], as_of_date)
            if price is None:
                exceptions.append({"code":"MISSING_PRICE", "instrument_id":h["instrument_id"], "message":"No market price on or before valuation date"})
                continue
            age = (date.fromisoformat(as_of_date) - date.fromisoformat(price["price_date"])).days
            stale = bool(price["is_stale"]) or age > 5
            if stale:
                exceptions.append({"code":"STALE_PRICE", "instrument_id":h["instrument_id"], "price_date":price["price_date"], "age_days":age, "message":"Price is explicitly stale or older than five calendar days"})
            qty = D(h["quantity"])
            unit_price = D(price["price"])
            value = qty * unit_price
            total += value
            current_by_class[h["asset_class"]] += value
            position_rows.append({"holding_id":h["holding_id"], "instrument_id":h["instrument_id"], "symbol":h["symbol"],
                "asset_class":h["asset_class"], "quantity":str(qty), "price":str(unit_price), "price_date":price["price_date"],
                "price_age_days":age, "market_value":str(value), "is_excluded":bool(h["is_excluded"]), "is_active":bool(h["is_active"])})
        if total <= ZERO:
            raise ValueError("Portfolio has no positively valued holdings")
        allocation = []
        tad = ZERO
        for asset in sorted(set(target_by_class) | set(current_by_class)):
            current_weight = current_by_class[asset] * HUNDRED / total
            target_weight = target_by_class.get(asset, ZERO)
            drift = current_weight - target_weight
            tad += abs(drift)
            allocation.append({"asset_class":asset, "market_value":str(current_by_class[asset]),
                "current_weight_pct":str(current_weight), "target_weight_pct":str(target_weight), "drift_pct":str(drift)})
        return {"portfolio_id":portfolio_id, "as_of_date":as_of_date, "base_currency":portfolio["base_currency"],
            "portfolio_value":str(total), "total_absolute_drift_pct_points":str(tad), "allocation":allocation,
            "holdings":position_rows, "exceptions":exceptions, "valuation_complete":not any(e["code"]=="MISSING_PRICE" for e in exceptions)}
