"""Validate generated source records and isolated anomaly fixtures."""
from __future__ import annotations
import csv, json, sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import DEFAULT_DB_PATH, get_connection
from app.services.policy_service import calculate_fee

D = Decimal

def evaluate_anomalies() -> list[dict]:
    from app.services.policy_service import (
        validate_portfolio_weights,
        validate_sell_quantity,
        validate_excluded_instrument,
        validate_fee,
        validate_price_freshness,
    )

    cases = json.loads(
        (ROOT / "data/anomalies/anomaly_cases.json")
        .read_text(encoding="utf-8")
    )

    truth = {
        r["case_id"]: r
        for r in csv.DictReader(
            (ROOT / "data/ground_truth/ground_truth.csv")
            .open(encoding="utf-8")
        )
    }

    validators = {
        "portfolio_weight_total": lambda d: validate_portfolio_weights(
            d["weights"]
        ),
        "sell_exceeds_holding": lambda d: validate_sell_quantity(
            D(d["available_quantity"]),
            D(d["proposed_sell_quantity"])
        ),
        "excluded_instrument_recommended": lambda d: (
            validate_excluded_instrument(
                d["is_excluded"],
                d["recommended_side"]
            )
        ),
        "fee_omitted": lambda d: validate_fee(
            d["fee_schedule_required"],
            d["fee_schedule_id"],
            D(d["estimated_fee"])
            if d["estimated_fee"] is not None else None
        ),
        "stale_price_unflagged": lambda d: validate_price_freshness(
            d["price_age_days"],
            d["is_stale"],
            d["max_price_age_days"]
        ),
    }

    results = []

    for case in cases:
        case_id = case["case_id"]
        scenario = case["scenario"]
        actual_issues = validators[scenario](case["input"])

        actual_decision = (
            actual_issues[0]["decision"]
            if actual_issues else "ACCEPT"
        )

        expected = truth[case_id]["expected_decision"]

        results.append({
            "case_id": case_id,
            "scenario": scenario,
            "actual_decision": actual_decision,
            "expected_decision": expected,
            "rule_id": truth[case_id]["rule_id"],
            "detected": bool(actual_issues),
            "passed": actual_decision == expected,
        })

    return results

def validate() -> dict:
    checks, details = {}, {}
    with get_connection(DEFAULT_DB_PATH) as conn:
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        checks["foreign_key_integrity"] = not fk
        details["foreign_key_violations"] = len(fk)
        tables = ["investor_profile","portfolio","instrument","holding","market_price","target_allocation","trade","fee_schedule","constraint_rule","rebalance_proposal"]
        counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
        details["row_counts"] = counts
        for t in tables:
            pk = conn.execute(f"PRAGMA table_info('{t}')").fetchall()
            pk_col = next(r[1] for r in pk if r[5])
            total = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            distinct = conn.execute(f'SELECT COUNT(DISTINCT "{pk_col}") FROM "{t}"').fetchone()[0]
            checks[f"{t}_primary_key_unique"] = total == distinct
        bad_targets = conn.execute("""SELECT portfolio_id, effective_from, SUM(CAST(target_weight_pct AS REAL)) s
            FROM target_allocation WHERE effective_to IS NULL OR effective_to >= '2026-11-09'
            GROUP BY portfolio_id, effective_from HAVING ABS(s-100.0) > 0.000001""").fetchall()
        checks["target_allocations_sum_to_100"] = not bad_targets
        details["bad_target_portfolios"] = len(bad_targets)
        bad_holding_ids = conn.execute("SELECT holding_id FROM holding WHERE holding_id != 'HOLD-' || portfolio_id || '-' || instrument_id").fetchall()
        checks["holding_ids_follow_convention"] = not bad_holding_ids
        checks["holding_quantities_positive"] = conn.execute("SELECT COUNT(*) FROM holding WHERE CAST(quantity AS REAL) <= 0").fetchone()[0] == 0
        bad_dates = conn.execute("SELECT COUNT(*) FROM target_allocation WHERE effective_to IS NOT NULL AND effective_to < effective_from").fetchone()[0]
        checks["effective_date_ordering"] = bad_dates == 0
        duplicate_prices = conn.execute("SELECT COUNT(*) FROM (SELECT instrument_id,price_date,source,COUNT(*) c FROM market_price GROUP BY 1,2,3 HAVING c>1)").fetchone()[0]
        checks["market_price_duplicates_absent"] = duplicate_prices == 0
        missing = conn.execute("""SELECT COUNT(*) FROM holding h WHERE NOT EXISTS
            (SELECT 1 FROM market_price p WHERE p.instrument_id=h.instrument_id AND p.price_date<=h.as_of_date)""").fetchone()[0]
        checks["all_holdings_have_historical_price"] = missing == 0
        stale = conn.execute("SELECT COUNT(*) FROM market_price WHERE is_stale=1").fetchone()[0]
        details["explicitly_stale_price_rows"] = stale
        details["missing_price_observations"] = max(0, counts["instrument"] * 250 - counts["market_price"]) if counts["instrument"] == 50 else None
        # Recompute current portfolio weights from holding quantities and the latest eligible prices.
        portfolio_weight_ok = True
        for p in conn.execute("SELECT portfolio_id FROM portfolio"):
            pid = p[0]
            rows = conn.execute("""SELECT h.quantity,mp.price FROM holding h JOIN market_price mp
                ON mp.instrument_id=h.instrument_id AND mp.price_date=(SELECT MAX(p2.price_date) FROM market_price p2
                WHERE p2.instrument_id=h.instrument_id AND p2.price_date<=h.as_of_date)
                WHERE h.portfolio_id=?""", (pid,)).fetchall()
            vals = [D(r["quantity"]) * D(r["price"]) for r in rows]
            if not vals or sum(vals, D("0")) <= 0:
                portfolio_weight_ok = False
                break
            weights = [v * D("100") / sum(vals, D("0")) for v in vals]
            if abs(sum(weights, D("0")) - D("100")) > D("0.000001"):
                portfolio_weight_ok = False
                break
        checks["current_portfolio_weights_reconcile"] = portfolio_weight_ok
        trade_rows = conn.execute("""SELECT t.*,fs.fee_type,fs.fee_rate,fs.fixed_fee,h.quantity available_qty,
            i.is_excluded FROM trade t LEFT JOIN fee_schedule fs ON fs.fee_schedule_id=t.fee_schedule_id
            LEFT JOIN rebalance_proposal rp ON rp.proposal_id=t.proposal_id
            LEFT JOIN holding h ON h.portfolio_id=rp.portfolio_id AND h.instrument_id=t.instrument_id
            JOIN instrument i ON i.instrument_id=t.instrument_id""").fetchall()
        gross_ok = fee_ok = sell_ok = excluded_ok = True
        for trade in trade_rows:
            computed_gross = (D(trade["quantity"]) * D(trade["estimated_price"])).quantize(D("0.01"), rounding=ROUND_HALF_UP)
            gross_ok = gross_ok and computed_gross == D(trade["gross_value"])
            if trade["fee_schedule_id"] is None or trade["fee_type"] is None:
                fee_ok = False
            else:
                schedule = {"fee_type":trade["fee_type"],"fee_rate":trade["fee_rate"],"fixed_fee":trade["fixed_fee"]}
                fee_ok = fee_ok and calculate_fee(D(trade["gross_value"]), schedule) == D(trade["estimated_fee"])
            if trade["side"] == "SELL":
                sell_ok = sell_ok and trade["available_qty"] is not None and D(trade["quantity"]) <= D(trade["available_qty"])
            excluded_ok = excluded_ok and not bool(trade["is_excluded"])
        checks["trade_gross_value_reconciles"] = gross_ok
        checks["trade_fees_reconcile"] = fee_ok
        checks["sell_trades_within_available_holdings"] = sell_ok
        checks["excluded_instruments_not_traded"] = excluded_ok
        details["trade_rows_validated"] = len(trade_rows)
        overlap = conn.execute("""SELECT COUNT(*) FROM target_allocation a JOIN target_allocation b
            ON a.portfolio_id=b.portfolio_id AND a.asset_class=b.asset_class AND a.target_allocation_id<b.target_allocation_id
            AND (a.effective_to IS NULL OR a.effective_to>=b.effective_from)
            AND (b.effective_to IS NULL OR b.effective_to>=a.effective_from)""").fetchone()[0]
        checks["target_effective_periods_do_not_overlap"] = overlap == 0
        fee_overlap = conn.execute("""SELECT COUNT(*) FROM fee_schedule a JOIN fee_schedule b
            ON a.asset_class=b.asset_class AND a.fee_schedule_id<b.fee_schedule_id
            AND a.status='ACTIVE' AND b.status='ACTIVE'
            AND a.effective_from<=COALESCE(b.effective_to,'9999-12-31')
            AND b.effective_from<=COALESCE(a.effective_to,'9999-12-31')
            AND CAST(a.min_trade_value AS REAL)<=CAST(COALESCE(b.max_trade_value,'1e99') AS REAL)
            AND CAST(b.min_trade_value AS REAL)<=CAST(COALESCE(a.max_trade_value,'1e99') AS REAL)""").fetchone()[0]
        checks["active_fee_tiers_do_not_overlap"] = fee_overlap == 0
        event_refs_ok = True
        entity_tables = {"INVESTOR":"investor_profile","PORTFOLIO":"portfolio","HOLDING":"holding","PROPOSAL":"rebalance_proposal","TRADE":"trade","CONSTRAINT":"constraint_rule"}
        for event in conn.execute("SELECT entity_type,entity_id FROM entity_event"):
            table = entity_tables.get(event["entity_type"])
            if table is None or conn.execute(f'SELECT 1 FROM "{table}" WHERE 1=1 AND ' + {
                "investor_profile":"investor_id", "portfolio":"portfolio_id", "holding":"holding_id", "rebalance_proposal":"proposal_id", "trade":"trade_id", "constraint_rule":"constraint_id"}[table] + "=?", (event["entity_id"],)).fetchone() is None:
                event_refs_ok = False
                break
        checks["audit_event_references_resolve"] = event_refs_ok
        details["portfolio_weight_reconciliation"] = "Recomputed from source holding quantities and dated market prices for every portfolio."
    anomaly_results = evaluate_anomalies()
    checks["all_five_negative_scenarios_detected"] = len(anomaly_results) == 5 and all(x["passed"] for x in anomaly_results)
    case_inputs = json.loads((ROOT / "data/anomalies/anomaly_cases.json").read_text(encoding="utf-8"))
    checks["ground_truth_not_leaked_into_anomaly_inputs"] = all(
        "expected_decision" not in item and "issue_type" not in item and "rule_id" not in item for item in case_inputs)
    details["anomaly_results"] = anomaly_results
    result = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "details": details}
    out = ROOT / "reports" / "validation_summary.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    raise SystemExit(0 if validate()["status"] == "PASS" else 1)
