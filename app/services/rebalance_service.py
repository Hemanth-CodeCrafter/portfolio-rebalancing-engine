
"""Rule-based proposal generation and immutable-holding post-trade simulation."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.database import DEFAULT_DB_PATH, get_connection
from app.services.portfolio_service import analyze_portfolio, _latest_price
from app.services.policy_service import (
    calculate_fee,
    policy_for_instrument,
    quantize_money,
    quantize_qty,
)

D = Decimal
ZERO = D("0")
HUNDRED = D("100")


def _event(
    conn,
    entity_type: str,
    entity_id: str,
    event_type: str,
    old: str | None,
    new: str | None,
    reason: str,
) -> None:
    n = conn.execute(
        "SELECT COUNT(*) FROM entity_event"
    ).fetchone()[0] + 1

    conn.execute(
        "INSERT INTO entity_event VALUES (?,?,?,?,?,?,?,?)",
        (
            f"EVT-{n:09d}",
            entity_type,
            entity_id,
            event_type,
            old,
            new,
            "2026-11-10T00:00:00+05:30",
            reason,
        ),
    )


def generate_proposal(
    portfolio_id: str,
    as_of_date: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    analysis = analyze_portfolio(
        portfolio_id,
        as_of_date,
        db_path,
    )

    if not analysis["valuation_complete"]:
        raise ValueError(
            "Proposal blocked: at least one holding has no historical market price"
        )

    exceptions = list(analysis["exceptions"])
    proposed = []

    with get_connection(db_path) as conn:
        existing = conn.execute(
            """
            SELECT proposal_id
            FROM rebalance_proposal
            ORDER BY proposal_id DESC
            LIMIT 1
            """
        ).fetchone()

        seq = (
            int(existing[0].split("-")[-1]) + 1
            if existing
            else 1
        )

        proposal_id = f"RB-2026-{seq:06d}"

        positions = {
            h["asset_class"]: h
            for h in analysis["holdings"]
        }

        total_value = D(analysis["portfolio_value"])

        for allocation in analysis["allocation"]:
            asset = allocation["asset_class"]
            drift = D(allocation["drift_pct"])

            delta_value = -drift * total_value / HUNDRED

            if abs(delta_value) < D("0.01"):
                continue

            side = "BUY" if delta_value > ZERO else "SELL"

            position = positions.get(asset)

            if position is None:
                exceptions.append({
                    "code": "NO_POSITION_IN_ASSET_CLASS",
                    "asset_class": asset,
                    "message": "No instrument position available for this asset class",
                })
                continue

            iid = position["instrument_id"]

            if position["is_excluded"]:
                exceptions.append({
                    "code": "EXCLUDED_INSTRUMENT",
                    "instrument_id": iid,
                    "message": "No trade proposed because instrument is excluded",
                })
                continue

            if not position["is_active"]:
                exceptions.append({
                    "code": "INACTIVE_INSTRUMENT",
                    "instrument_id": iid,
                    "message": "No trade proposed because instrument is inactive",
                })
                continue

            if position["price_age_days"] > 5:
                exceptions.append({
                    "code": "STALE_PRICE_TRADE_BLOCKED",
                    "instrument_id": iid,
                    "message": "No trade proposed using a price older than five days",
                })
                continue

            price = D(position["price"])
            gross = abs(delta_value)
            qty = quantize_qty(gross / price)

            if qty <= ZERO:
                continue

            if side == "SELL" and qty > D(position["quantity"]):
                qty = quantize_qty(D(position["quantity"]))

            gross = quantize_money(qty * price)

            schedule = conn.execute(
                """
                SELECT *
                FROM fee_schedule
                WHERE asset_class = ?
                  AND status = 'ACTIVE'
                  AND effective_from <= ?
                  AND (effective_to IS NULL OR effective_to >= ?)
                  AND CAST(min_trade_value AS REAL) <= ?
                  AND (
                      max_trade_value IS NULL
                      OR CAST(max_trade_value AS REAL) >= ?
                  )
                ORDER BY CAST(min_trade_value AS REAL) DESC
                LIMIT 1
                """,
                (
                    asset,
                    analysis["as_of_date"],
                    analysis["as_of_date"],
                    str(gross),
                    str(gross),
                ),
            ).fetchone()

            if schedule is None:
                exceptions.append({
                    "code": "MISSING_FEE_SCHEDULE",
                    "instrument_id": iid,
                    "message": "Required fee schedule is unavailable",
                })
                continue

            min_value = D(schedule["min_trade_value"])

            if gross < min_value:
                exceptions.append({
                    "code": "BELOW_MIN_TRADE",
                    "instrument_id": iid,
                    "message": (
                        f"Trade {gross} is below fee schedule minimum {min_value}"
                    ),
                })
                continue

            price_row = _latest_price(
                conn,
                iid,
                analysis["as_of_date"],
            )

            volume = (
                D(price_row["daily_volume"])
                if price_row and price_row["daily_volume"] is not None
                else None
            )

            policy_issues = policy_for_instrument(
                conn,
                portfolio_id,
                iid,
                asset,
                gross,
                volume,
                analysis["as_of_date"],
            )

            if policy_issues:
                exceptions.extend(policy_issues)
                continue

            fee = calculate_fee(gross, schedule)

            proposed.append({
                "instrument_id": iid,
                "side": side,
                "quantity": str(qty),
                "estimated_price": str(price),
                "gross_value": str(quantize_money(gross)),
                "estimated_fee": str(fee),
                "fee_schedule_id": schedule["fee_schedule_id"],
            })

        status = (
            "REVIEW_REQUIRED"
            if exceptions
            else "GENERATED"
        )

        summary = {
            "decision": (
                "REVIEW_REQUIRED"
                if exceptions
                else "PROPOSAL_GENERATED"
            ),
            "trade_count": len(proposed),
            "exceptions": exceptions,
            "method": (
                "Asset-class target value less current value; "
                "no discretionary override"
            ),
        }

        conn.execute(
            "INSERT INTO rebalance_proposal VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                proposal_id,
                portfolio_id,
                analysis["as_of_date"],
                status,
                analysis["portfolio_value"],
                None,
                analysis["total_absolute_drift_pct_points"],
                None,
                len(exceptions),
                json.dumps(summary, sort_keys=True),
                "2026-11-10T00:00:00+05:30",
            ),
        )

        _event(
            conn,
            "PROPOSAL",
            proposal_id,
            "CREATED",
            None,
            status,
            "Deterministic allocation drift and policy evaluation",
        )

        for index, trade in enumerate(proposed, 1):
            trade_id = f"TR-{seq:06d}-{index:03d}"

            conn.execute(
                "INSERT INTO trade VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    trade_id,
                    proposal_id,
                    trade["instrument_id"],
                    trade["fee_schedule_id"],
                    trade["side"],
                    trade["quantity"],
                    trade["estimated_price"],
                    trade["gross_value"],
                    trade["estimated_fee"],
                    "PROPOSED",
                    "2026-11-10T00:00:00+05:30",
                ),
            )

            _event(
                conn,
                "TRADE",
                trade_id,
                "CREATED",
                None,
                "PROPOSED",
                "Trade passed deterministic policy checks",
            )

    return get_proposal(proposal_id, db_path)


def get_proposal(
    proposal_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    with get_connection(db_path) as conn:
        proposal = conn.execute(
            """
            SELECT *
            FROM rebalance_proposal
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()

        if proposal is None:
            raise ValueError(
                f"Proposal not found: {proposal_id}"
            )

        trades = conn.execute(
            """
            SELECT *
            FROM trade
            WHERE proposal_id = ?
            ORDER BY trade_id
            """,
            (proposal_id,),
        ).fetchall()

        return {
            "proposal": dict(proposal),
            "trades": [dict(trade) for trade in trades],
        }


def simulate_proposal(
    proposal_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    with get_connection(db_path) as conn:
        proposal = conn.execute(
            """
            SELECT *
            FROM rebalance_proposal
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()

        if proposal is None:
            raise ValueError(
                f"Proposal not found: {proposal_id}"
            )

        # Simulation is permitted only after reviewer approval.
        if proposal["status"] != "APPROVED":
            raise ValueError(
                "Only APPROVED proposals can be simulated"
            )

        trades = conn.execute(
            """
            SELECT *
            FROM trade
            WHERE proposal_id = ?
            ORDER BY trade_id
            """,
            (proposal_id,),
        ).fetchall()

        positions = conn.execute(
            """
            SELECT h.*, i.asset_class
            FROM holding h
            JOIN instrument i
                ON i.instrument_id = h.instrument_id
            WHERE h.portfolio_id = ?
              AND h.as_of_date <= ?
            """,
            (
                proposal["portfolio_id"],
                proposal["as_of_date"],
            ),
        ).fetchall()

        quantities = {
            row["instrument_id"]: D(row["quantity"])
            for row in positions
        }

        prices = {}
        asset_by_id = {}

        for row in positions:
            price = _latest_price(
                conn,
                row["instrument_id"],
                proposal["as_of_date"],
            )

            if price is None:
                raise ValueError(
                    "Missing price during simulation for "
                    f"{row['instrument_id']}"
                )

            prices[row["instrument_id"]] = D(price["price"])
            asset_by_id[row["instrument_id"]] = row["asset_class"]

        total_fees = ZERO

        for trade in trades:
            iid = trade["instrument_id"]
            qty = D(trade["quantity"])

            if trade["side"] == "SELL":
                if qty > quantities.get(iid, ZERO):
                    raise ValueError(
                        f"Sell exceeds available holding for {iid}"
                    )

                quantities[iid] = (
                    quantities.get(iid, ZERO) - qty
                )

            else:
                quantities[iid] = (
                    quantities.get(iid, ZERO) + qty
                )

            total_fees += D(trade["estimated_fee"])

        values = defaultdict(lambda: ZERO)

        cash_ids = [
            iid
            for iid, asset in asset_by_id.items()
            if asset == "CASH"
        ]

        cash_value = sum(
            (
                quantities[iid] * prices[iid]
                for iid in cash_ids
            ),
            ZERO,
        )

        if total_fees > cash_value:
            raise ValueError(
                "Simulation blocked: available cash position "
                "cannot cover estimated fees"
            )

        # Deduct fees from the cash position without
        # rewriting source holdings.
        if cash_ids and total_fees:
            cash_iid = cash_ids[0]
            quantities[cash_iid] -= (
                total_fees / prices[cash_iid]
            )

        for iid, qty in quantities.items():
            values[asset_by_id[iid]] += qty * prices[iid]

        post_value = sum(values.values(), ZERO)

        if post_value <= ZERO:
            raise ValueError(
                "Post-trade portfolio value is not positive"
            )

        targets = conn.execute(
            """
            SELECT asset_class, target_weight_pct
            FROM target_allocation
            WHERE portfolio_id = ?
              AND effective_from <= ?
              AND (
                  effective_to IS NULL
                  OR effective_to >= ?
              )
            """,
            (
                proposal["portfolio_id"],
                proposal["as_of_date"],
                proposal["as_of_date"],
            ),
        ).fetchall()

        target_map = {
            row["asset_class"]: D(row["target_weight_pct"])
            for row in targets
        }

        if sum(target_map.values(), ZERO) != HUNDRED:
            raise ValueError(
                "Target allocations do not total 100%"
            )

        post_tad = ZERO

        for asset in set(target_map) | set(values):
            post_tad += abs(
                values[asset] * HUNDRED / post_value
                - target_map.get(asset, ZERO)
            )

        old = proposal["status"]

        conn.execute(
            """
            UPDATE rebalance_proposal
            SET status = 'SIMULATED',
                post_trade_value = ?,
                post_trade_drift_pct = ?
            WHERE proposal_id = ?
            """,
            (
                str(quantize_money(post_value)),
                str(post_tad),
                proposal_id,
            ),
        )

        _event(
            conn,
            "PROPOSAL",
            proposal_id,
            "STATUS_CHANGED",
            old,
            "SIMULATED",
            "Post-trade simulation completed",
        )

        for trade in trades:
            conn.execute(
                """
                UPDATE trade
                SET status = 'SIMULATED'
                WHERE trade_id = ?
                """,
                (trade["trade_id"],),
            )

            _event(
                conn,
                "TRADE",
                trade["trade_id"],
                "STATUS_CHANGED",
                trade["status"],
                "SIMULATED",
                "Included in post-trade simulation",
            )

        return {
            "proposal_id": proposal_id,
            "status": "SIMULATED",
            "pre_trade_value": proposal["pre_trade_value"],
            "post_trade_value": str(
                quantize_money(post_value)
            ),
            "fees_deducted": str(
                quantize_money(total_fees)
            ),
            "pre_trade_total_absolute_drift_pct_points": (
                proposal["pre_trade_drift_pct"]
            ),
            "post_trade_total_absolute_drift_pct_points": (
                str(post_tad)
            ),
            "drift_improvement_pct_points": (
                str(D(proposal["pre_trade_drift_pct"]) - post_tad)
            ),
            "post_trade_allocation": {
                key: str(value * HUNDRED / post_value)
                for key, value in sorted(values.items())
            },
        }
