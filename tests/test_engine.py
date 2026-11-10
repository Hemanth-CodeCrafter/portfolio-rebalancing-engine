from __future__ import annotations
import shutil
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient
from app.database import DEFAULT_DB_PATH, get_connection
from app.main import app
from app.services.portfolio_service import analyze_portfolio
from app.services.rebalance_service import generate_proposal, simulate_proposal
from app.services.policy_service import calculate_fee

client = TestClient(app)

def test_portfolio_analysis_reconciles_weights():
    with get_connection() as conn:
        portfolio_id = conn.execute("SELECT portfolio_id FROM portfolio ORDER BY portfolio_id LIMIT 1").fetchone()[0]
    result = analyze_portfolio(portfolio_id)
    weights = sum(Decimal(x["current_weight_pct"]) for x in result["allocation"])
    assert abs(weights - Decimal("100")) < Decimal("0.0000001")
    assert Decimal(result["total_absolute_drift_pct_points"]) >= 0
    assert result["valuation_complete"] is True

def test_proposal_and_simulation_preserve_source_holdings(tmp_path: Path):
    db = tmp_path / "engine.db"
    shutil.copy2(DEFAULT_DB_PATH, db)
    with get_connection(db) as conn:
        portfolio_id = conn.execute("SELECT portfolio_id FROM portfolio WHERE portfolio_id='PORT-INV-000002-01'").fetchone()[0]
        before = [tuple(r) for r in conn.execute("SELECT holding_id,quantity FROM holding WHERE portfolio_id=? ORDER BY holding_id", (portfolio_id,))]
    proposal = generate_proposal(portfolio_id, db_path=db)
    assert proposal["proposal"]["status"] == "GENERATED"
    assert len(proposal["trades"]) > 0
    for trade in proposal["trades"]:
        assert Decimal(trade["gross_value"]) > 0
        assert Decimal(trade["estimated_fee"]) >= 0
        assert Decimal(trade["gross_value"]) == (Decimal(trade["quantity"]) * Decimal(trade["estimated_price"])).quantize(Decimal("0.01"))
        if trade["side"] == "SELL":
            with get_connection(db) as conn:
                available = conn.execute("SELECT quantity FROM holding WHERE portfolio_id=? AND instrument_id=?", (portfolio_id, trade["instrument_id"])).fetchone()[0]
            assert Decimal(trade["quantity"]) <= Decimal(available)
    result = simulate_proposal(proposal["proposal"]["proposal_id"], db_path=db)
    assert result["status"] == "SIMULATED"
    assert Decimal(result["fees_deducted"]) >= 0
    with get_connection(db) as conn:
        after = [tuple(r) for r in conn.execute("SELECT holding_id,quantity FROM holding WHERE portfolio_id=? ORDER BY holding_id", (portfolio_id,))]
        events = conn.execute("SELECT COUNT(*) FROM entity_event WHERE entity_id=?", (proposal["proposal"]["proposal_id"],)).fetchone()[0]
    assert before == after
    assert events >= 2

def test_fixed_fee_calculation():
    schedule = {"fee_type":"HYBRID", "fee_rate":"0.001", "fixed_fee":"10.00"}
    assert calculate_fee(Decimal("10000"), schedule) == Decimal("20.00")

def test_api_health_portfolio_list_and_analysis():
    assert client.get("/").status_code == 200
    listing = client.get("/portfolios?limit=2")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 2
    pid = listing.json()["items"][0]["portfolio_id"]
    analysis = client.get(f"/portfolios/{pid}/analysis")
    assert analysis.status_code == 200
    assert "total_absolute_drift_pct_points" in analysis.json()
