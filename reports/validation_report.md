
# Validation and Execution Report

- **Project:** Portfolio Rebalancing Engine
- **Generated:** 2026-11-10
- **Random seed:** `20261022`
- **Dataset scale:** Full

## 1. Dataset Volumes

The full synthetic dataset contains the following records.

| Entity | Records |
|---|---:|
| Investor profiles | 1,000 |
| Portfolios | 1,000 |
| Instruments | 50 |
| Holdings | 5,000 |
| Market prices | 12,482 |
| Target allocations | 5,000 |
| Fee schedules | 10 |
| Constraint rules | 1,055 |
| Rebalance proposals | 0 |
| Trades | 0 |
| Audit events | 0 |

The full generator is configured for 250 trading days.

All records are synthetic and generated using seed `20261022`.

The baseline database is intentionally maintained without proposal, trade or audit-event records. API demonstration records are maintained separately in the workflow reports.

## 2. Database Schema Validation

**Status: PASS**

| Validation | Result |
|---|---:|
| Expected database tables | 11 |
| Tables with primary keys | 11 |
| Custom indexes | 8 |
| Lifecycle and audit triggers | 4 |
| Foreign-key violations | 0 |
| Foreign-key enforcement | Enabled |

All expected tables have primary keys.

The application database connection enables foreign-key enforcement.

Lifecycle triggers protect proposal and trade status transitions. Separate audit triggers prevent updates and deletions from the `entity_event` table.

Detailed evidence: `reports/schema_validation.json`.

## 3. Data Validation

**Status: PASS**

**Checks passed: 27/27**

| Validation area | Result |
|---|---|
| Primary-key uniqueness | PASS |
| Foreign-key integrity | PASS |
| Target allocations total 100% | PASS |
| Holding identifier conventions | PASS |
| Positive holding quantities | PASS |
| Effective-date ordering | PASS |
| Duplicate market-price observations | PASS |
| Historical prices for holdings | PASS |
| Portfolio-weight reconciliation | PASS |
| Trade arithmetic and fee checks | PASS |
| Sell quantities within available holdings | PASS |
| Excluded instruments not traded | PASS |
| Effective target periods do not overlap | PASS |
| Active fee tiers do not overlap | PASS |
| Audit-event references resolve | PASS |
| Five negative scenarios detected | PASS |
| Ground-truth separation | PASS |

### Price-quality observations

- Explicitly stale market-price rows: 21
- Missing market-price observations: 18
- Invalid target-allocation portfolios: 0

### Trade-validation scope

The clean full baseline contains zero trade records. Consequently, trade-level arithmetic and fee checks have no baseline rows to evaluate.

Non-empty proposal and trade calculations are exercised by the automated engine tests and documented API workflow demonstration.

The validation script maintains the separation between anomaly inputs and expected ground-truth decisions.

Detailed evidence: `reports/validation_summary.json`.

## 4. Automated Testing

**Status: PASS**

| Metric | Result |
|---|---:|
| Tests collected | 18 |
| Tests passed | 18 |
| Tests failed | 0 |

Test coverage includes:

- Database structure and primary-key constraints.
- Foreign-key enforcement.
- Invalid enum and negative quantity rejection.
- Duplicate-key and constraint-scope validation.
- Proposal lifecycle transition rules.
- Append-only audit-event behavior.
- Portfolio allocation reconciliation.
- Proposal generation and trade calculations.
- Sell quantity limits.
- Approval-before-simulation enforcement.
- Post-trade simulation.
- Preservation of original holding records.
- Fee calculations.
- API health and portfolio analysis endpoints.

**Warning:** One non-blocking Starlette/httpx deprecation warning was reported by the installed test dependencies. It did not cause test failures.

Detailed evidence: `reports/pytest_results.txt`.

## 5. Reproducibility Verification

Both dataset scales were checked using the fixed seed `20261022`.

### Starter dataset

**Status: PASS**

- Generated files compared: 26
- Checksum mismatches: 0
- Row counts matched: Yes
- Primary-key sequences matched: Yes

### Full dataset

**Status: PASS**

- Generated files compared: 26
- Checksum mismatches: 0
- Row counts matched: Yes
- Primary-key sequences matched: Yes

The reproducibility verification compares generated file checksums, exported row counts and primary-key sequences across repeated generation runs.

Evidence:

- `reports/reproducibility_starter_console.txt`
- `reports/reproducibility_full_console.txt`
- `reports/reproducibility_report.json`

## 6. API Workflow Demonstration

A separate API demonstration was conducted using the full synthetic dataset.

**Status: PASS**

The successful workflow demonstrated:

1. Portfolio analysis.
2. Rebalance proposal generation.
3. Trade recommendation retrieval.
4. Proposal approval.
5. Post-trade simulation.
6. Audit-event retrieval.

### Recorded demonstration results

| Metric | Result |
|---|---:|
| Demonstration portfolio | `PORT-INV-000002-01` |
| Proposal ID | `RB-2026-000001` |
| Proposed trades | 5 |
| Related audit events | 18 |
| Estimated fees deducted | INR 75.00 |
| Pre-trade TAD | 5.2044 percentage points |
| Post-trade TAD | 0.0153 percentage points |

The simulation reduced allocation drift while preserving the original source holdings.

Detailed evidence: `reports/api_workflow_report.json`.

## 7. Exception-Handling Demonstration

A separate exception-path workflow was conducted using a portfolio containing an excluded instrument.

**Status: PASS**

| Check | Result |
|---|---|
| Excluded instrument detected | Yes |
| Proposal status | `REVIEW_REQUIRED` |
| Approval blocked | HTTP 409 |
| Simulation blocked | HTTP 409 |

The system prevented approval and simulation when the proposal contained an unresolved policy exception.

Detailed evidence: `reports/exception_path_report.json`.

## 8. Design and Implementation Boundaries

The implementation uses synthetic financial data and simplified trading assumptions.

Important boundaries include:

- The current rebalance service selects one holding per asset class when sizing trades.
- The generated baseline uses one holding per asset class per portfolio.
- The simulation service requires an approved proposal.
- API approval is a workflow operation; authentication and role-based access control are not implemented.
- The current Holding identifier represents a canonical portfolio/instrument position rather than full multi-date position history.
- INR is the baseline currency; foreign-exchange conversion is outside the current scope.
- Synthetic prices are not live market observations.
- The application is an educational prototype, not a production trading or execution system.

## 9. Conclusion

The project demonstrates a deterministic portfolio rebalancing workflow supported by relational database integrity, effective-dated policies, transaction fee calculations, data-quality checks, negative-scenario validation, proposal lifecycle management, audit history and post-trade simulation.

The full synthetic dataset, schema validation, data validation, automated tests and starter/full reproducibility checks provide supporting evidence for the implementation.

All reported results refer to the synthetic demonstration environment and should not be interpreted as real-world investment performance or trading results.
