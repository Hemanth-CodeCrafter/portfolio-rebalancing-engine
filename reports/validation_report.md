# Validation and execution report

Generated: 2026-11-10T00:00:00+05:30  
Seed: `20261022`  
Scale: `full`

## Dataset volumes

| Entity | Rows |
|---|---:|
| `constraint_rule` | 1,055 |
| `entity_event` | 0 |
| `fee_schedule` | 10 |
| `holding` | 5,000 |
| `instrument` | 50 |
| `investor_profile` | 1,000 |
| `market_price` | 12,482 |
| `portfolio` | 1,000 |
| `rebalance_proposal` | 0 |
| `target_allocation` | 5,000 |
| `trade` | 0 |

## Database schema

- Status: **PASS**
- Tables: 11
- Tables with PKs: 11
- Custom indexes: 8
- Lifecycle/audit triggers: 4
- FK violations: 0

## Data validation

- Status: **PASS**
- Checks passed: 27/27
- Explicitly stale price rows: 21
- Missing price observations: 18
- Negative scenarios detected: 5/5
- Ground-truth labels leaked into anomaly inputs: No

## Automated tests

- pytest: **13 passed** (last recorded run)
- Includes database integrity, enum/PK/FK checks, negative quantities, lifecycle transition guards, append-only audit history, portfolio reconciliation, proposal/simulation, fee arithmetic and API read endpoints.

## Reproducibility

- Status: **PASS**
- Fixed seed: `20261022`
- Generated files compared: 26
- Row counts identical: True
- Primary-key sequences identical: True
- Checksum mismatches: 0
- Both starter and full scales were regenerated twice using the same generator; see the corresponding console reports.

## API workflow evidence

- Exception-free workflow: **PASS**; all six tested API requests returned HTTP 200.
- Proposal: `RB-2026-000001`; trades: 5; related audit events: 18.
- TAD reduced from 5.2044 to 0.0153 percentage points after fees.
- Fees deducted from simulated cash: INR 75.00.
- Exception path: **PASS**; excluded instrument triggered `REVIEW_REQUIRED`; approval and simulation both correctly returned HTTP 409.

## Scope and caveats

All records are synthetic. No external dataset or personal information was used. The baseline DB is restored to a clean full dataset after API integration tests; the proposal/trade/event records created during those tests are captured in separate reports, not retained in the baseline DB. The demo API has no authentication layer and is not production financial software.
