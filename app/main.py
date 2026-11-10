"""FastAPI entry point for the Portfolio Rebalancing Engine."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.database import DEFAULT_DB_PATH, get_connection
from app.services.portfolio_service import analyze_portfolio
from app.services.rebalance_service import generate_proposal, get_proposal, simulate_proposal, _event

app = FastAPI(title="Portfolio Rebalancing Engine", version="1.0.0",
              description="Deterministic, policy-constrained portfolio analysis and rebalancing simulation. Educational simulation only.")

class RebalanceRequest(BaseModel):
    as_of_date: str | None = None

class DecisionRequest(BaseModel):
    reason: str = "Reviewed by authorized risk/compliance reviewer"

@app.get("/")
def root():
    return {"service":"Portfolio Rebalancing Engine", "status":"running", "docs":"/docs", "disclaimer":"Educational simulation; not financial advice."}

@app.get("/portfolios")
def list_portfolios(limit: int = 100, offset: int = 0):
    if limit < 1 or limit > 1000 or offset < 0:
        raise HTTPException(400, "limit must be 1..1000 and offset must be non-negative")
    with get_connection() as conn:
        rows = conn.execute("""SELECT p.portfolio_id,p.investor_id,p.portfolio_name,p.base_currency,p.status,
            i.risk_profile FROM portfolio p JOIN investor_profile i ON i.investor_id=p.investor_id
            ORDER BY p.portfolio_id LIMIT ? OFFSET ?""", (limit, offset)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM portfolio").fetchone()[0]
    return {"total":total,"limit":limit,"offset":offset,"items":[dict(r) for r in rows]}

@app.get("/portfolios/{portfolio_id}")
def portfolio_detail(portfolio_id: str):
    with get_connection() as conn:
        row = conn.execute("""SELECT p.*,i.full_name,i.risk_profile,i.status investor_status FROM portfolio p
            JOIN investor_profile i ON i.investor_id=p.investor_id WHERE p.portfolio_id=?""", (portfolio_id,)).fetchone()
    if row is None: raise HTTPException(404, "Portfolio not found")
    return dict(row)

@app.get("/portfolios/{portfolio_id}/analysis")
def portfolio_analysis(portfolio_id: str, as_of_date: str | None = None):
    try: return analyze_portfolio(portfolio_id, as_of_date)
    except ValueError as exc: raise HTTPException(404 if "not found" in str(exc).lower() else 422, str(exc))

@app.post("/portfolios/{portfolio_id}/rebalance")
def create_rebalance(portfolio_id: str, request: RebalanceRequest | None = None):
    try: return generate_proposal(portfolio_id, request.as_of_date if request else None)
    except ValueError as exc: raise HTTPException(422, str(exc))

@app.get("/proposals/{proposal_id}")
def proposal_detail(proposal_id: str):
    try: return get_proposal(proposal_id)
    except ValueError as exc: raise HTTPException(404, str(exc))

@app.get("/proposals/{proposal_id}/trades")
def proposal_trades(proposal_id: str):
    try: return get_proposal(proposal_id)["trades"]
    except ValueError as exc: raise HTTPException(404, str(exc))

@app.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, request: DecisionRequest):
    with get_connection() as conn:
        row = conn.execute("SELECT status,exception_count FROM rebalance_proposal WHERE proposal_id=?", (proposal_id,)).fetchone()
        if row is None: raise HTTPException(404, "Proposal not found")
        if row["status"] != "GENERATED" or row["exception_count"] != 0:
            raise HTTPException(409, "Only exception-free GENERATED proposals can be approved")
        conn.execute("UPDATE rebalance_proposal SET status='APPROVED' WHERE proposal_id=?", (proposal_id,))
        _event(conn, "PROPOSAL", proposal_id, "STATUS_CHANGED", row["status"], "APPROVED", request.reason)
        trades = conn.execute("SELECT trade_id,status FROM trade WHERE proposal_id=?", (proposal_id,)).fetchall()
        for trade in trades:
            conn.execute("UPDATE trade SET status='APPROVED' WHERE trade_id=?", (trade["trade_id"],))
            _event(conn, "TRADE", trade["trade_id"], "STATUS_CHANGED", trade["status"], "APPROVED", request.reason)
    return get_proposal(proposal_id)

@app.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, request: DecisionRequest):
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM rebalance_proposal WHERE proposal_id=?", (proposal_id,)).fetchone()
        if row is None: raise HTTPException(404, "Proposal not found")
        if row["status"] not in ("GENERATED","REVIEW_REQUIRED"):
            raise HTTPException(409, f"Cannot reject proposal in state {row['status']}")
        conn.execute("UPDATE rebalance_proposal SET status='REJECTED' WHERE proposal_id=?", (proposal_id,))
        _event(conn, "PROPOSAL", proposal_id, "STATUS_CHANGED", row["status"], "REJECTED", request.reason)
        trades = conn.execute("SELECT trade_id,status FROM trade WHERE proposal_id=?", (proposal_id,)).fetchall()
        for trade in trades:
            conn.execute("UPDATE trade SET status='REJECTED' WHERE trade_id=?", (trade["trade_id"],))
            _event(conn, "TRADE", trade["trade_id"], "STATUS_CHANGED", trade["status"], "REJECTED", request.reason)
    return get_proposal(proposal_id)

@app.post("/proposals/{proposal_id}/simulate")
def simulate(proposal_id: str):
    try: return simulate_proposal(proposal_id)
    except ValueError as exc: raise HTTPException(409, str(exc))

@app.get("/proposals/{proposal_id}/events")
def proposal_events(proposal_id: str):
    with get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM rebalance_proposal WHERE proposal_id=?", (proposal_id,)).fetchone()
        if not exists: raise HTTPException(404, "Proposal not found")
        rows = conn.execute("""SELECT * FROM entity_event WHERE entity_id=?
            OR entity_id IN (SELECT trade_id FROM trade WHERE proposal_id=?)
            ORDER BY event_timestamp,event_id""", (proposal_id, proposal_id)).fetchall()
    return [dict(r) for r in rows]
