# Five-minute hackathon demo

Run from PowerShell after activating the virtual environment and starting Uvicorn.

```powershell
uvicorn app.main:app --reload
```

Use the deterministic full-dataset example portfolio `PORT-INV-000002-01`.

```powershell
# 1. Inspect current valuation, weights, drift and TAD.
$analysis = Invoke-RestMethod http://127.0.0.1:8000/portfolios/PORT-INV-000002-01/analysis
$analysis.allocation | Format-Table
$analysis.total_absolute_drift_pct_points

# 2. Generate a proposal and inspect the trades.
$proposal = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/portfolios/PORT-INV-000002-01/rebalance -ContentType 'application/json' -Body '{}'
$proposal.proposal | Format-List
$proposal.trades | Format-Table
$id = $proposal.proposal.proposal_id

# 3. Record reviewer approval and simulate.
$body = @{ reason = 'Reviewed for hackathon demonstration' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/proposals/$id/approve" -ContentType 'application/json' -Body $body
$simulation = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/proposals/$id/simulate"
$simulation | Format-List

# 4. Show proposal and trade event history.
Invoke-RestMethod "http://127.0.0.1:8000/proposals/$id/events" | Format-Table
```

Expected behavior for the seeded sample: five proposed trades; simulation deducts fees from cash; post-trade TAD is materially lower than pre-trade TAD. Exact outputs are recorded in `reports/api_workflow_report.json`.

To demonstrate the exception path, use `PORT-INV-000001-01`. It holds an excluded instrument. Its proposal is `REVIEW_REQUIRED`; the API blocks approval and simulation with HTTP 409. See `reports/exception_path_report.json`.

The demo API has no authentication. Explain that reviewer approval is a workflow gate in this educational prototype, not a production identity/access-management implementation.
