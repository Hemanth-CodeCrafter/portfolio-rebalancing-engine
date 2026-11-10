# Portfolio Rebalancing Engine

A deterministic, policy-constrained portfolio rebalancing prototype. It analyses current holdings against target allocations, calculates allocation drift, generates buy/sell proposals, applies trading and fee policies, and simulates post-trade outcomes.

> **Disclaimer:** This project uses synthetic data and simplified assumptions. It is an educational demonstration, not investment advice, a brokerage connection, or a production trade-execution system.

## 1. Project Overview

The Portfolio Rebalancing Engine demonstrates an end-to-end portfolio rebalancing workflow.

The application:

- Analyses portfolio holdings using dated market prices.
- Calculates current portfolio value and asset-class allocation.
- Compares current allocation with target allocation.
- Calculates allocation drift and Total Absolute Drift (TAD).
- Generates deterministic buy and sell recommendations.
- Applies trading constraints and transaction fee calculations.
- Identifies missing prices, stale prices and policy exceptions.
- Creates rebalancing proposals with lifecycle information.
- Supports proposal review, approval and rejection.
- Simulates post-trade allocation and estimated fees.
- Records relevant proposal and trade state changes as audit events.

The application uses synthetic financial data and is intended for educational and demonstration purposes.

## 2. Key Features

### Portfolio Analysis

- Calculates holding market value using quantity and dated market price.
- Calculates total portfolio value.
- Calculates current asset-class allocation percentages.
- Compares current allocation against target allocation.
- Calculates allocation drift in percentage points.
- Calculates Total Absolute Drift (TAD).

### Rebalancing Recommendations

- Generates BUY and SELL candidates based on target-versus-current allocation.
- Checks available holding quantities before proposing sells.
- Avoids trading excluded or inactive instruments.
- Applies configured trade-size and liquidity constraints.
- Generates proposal summaries containing decisions and exceptions.

### Policy and Fee Management

- Supports minimum trade-size constraints.
- Supports maximum trade-size constraints.
- Supports minimum liquidity requirements.
- Supports excluded-instrument rules.
- Uses effective-dated fee schedules.
- Calculates FIXED, PERCENTAGE and HYBRID transaction fees.
- Uses Python `Decimal` for financial calculations.

### Exception Handling

The engine identifies conditions such as:

- Invalid portfolio allocation totals.
- Sell quantities exceeding available holdings.
- Excluded instruments being selected for trading.
- Missing required fee schedules.
- Missing or stale market prices.
- Liquidity and trade-size policy violations.

Proposals with exceptions are marked `REVIEW_REQUIRED`.

### Proposal Lifecycle and Audit History

The application supports:

- Proposal generation.
- Proposal review.
- Proposal approval.
- Proposal rejection.
- Trade status changes.
- Proposal and trade event history.

An append-only `entity_event` table records relevant state transitions.

### Post-Trade Simulation

- Applies proposed trades to an in-memory copy of portfolio positions.
- Calculates estimated transaction fees.
- Deducts estimated fees from the cash position.
- Recalculates post-trade allocation.
- Measures remaining allocation drift.
- Preserves original source holding records.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| API framework | FastAPI |
| Database | SQLite |
| Financial calculations | Python Decimal |
| Data validation | Python validation scripts |
| Automated testing | pytest |
| API documentation | Swagger UI / OpenAPI |
| Data formats | CSV, JSON and SQL |

## 4. Data Model

The database contains ten business entities plus an audit-event entity.

| Entity | Purpose |
|---|---|
| InvestorProfile | Synthetic investor details and risk profile |
| Portfolio | Investor portfolio information |
| Instrument | Instrument and asset-class information |
| Holding | Instrument quantities held in a portfolio |
| MarketPrice | Dated market-price observations |
| TargetAllocation | Effective-dated target allocation |
| Trade | Proposed trade information |
| FeeSchedule | Transaction fee rules |
| Constraint | Trading and policy constraints |
| RebalanceProposal | Rebalancing proposal and lifecycle status |
| EntityEvent | Audit history of relevant state changes |

Primary keys, foreign keys, unique constraints, effective dates and lifecycle rules are defined in the database design.

Financial values are stored as decimal text and processed using Python `Decimal`.

See:

- [Database Design](docs/database_design.md)
- [Data Dictionary](docs/data_dictionary.md)
- [ER Diagram](docs/er_diagram.md)

## 5. Synthetic Dataset

The project uses deterministic synthetic data generated with a fixed random seed.

**Default random seed:** `20261022`

### Full dataset

| Dataset | Records |
|---|---:|
| Investor profiles | 1,000 |
| Portfolios | 1,000 |
| Instruments | 50 |
| Holdings | 5,000 |
| Market-price observations | 12,482 |
| Target allocations | 5,000 |
| Fee schedules | 10 |
| Constraint rules | 1,055 |
| Rebalance proposals in baseline | 0 |
| Trades in baseline | 0 |
| Audit events in baseline | 0 |

The full generator is configured for 250 trading days. Some price observations are deliberately missing, so the exported market-price row count is lower than the theoretical maximum.

The full dataset contains:

- 21 explicitly stale price rows.
- 18 missing price observations.
- Five asset classes: EQUITY, DEBT, GOLD, CASH and OTHER.
- Synthetic investor risk profiles and target allocations.
- Effective-dated policy constraints and fee schedules.

All records are synthetic. No external personal or financial dataset is used.

See [manifest.json](manifest.json) and [source_manifest.json](source_manifest.json) for dataset metadata and provenance.

### Dataset scales

| Scale | Portfolios | Instruments | Trading days |
|---|---:|---:|---:|
| Starter | 10 | 10 | 30 |
| Full | 1,000 | 50 | 250 |

Both scales use the same generator and default seed.

## 6. Negative Scenarios and Ground Truth

Five deliberate negative scenarios are included to test validation and policy handling.

| Scenario | Expected decision |
|---|---|
| Portfolio weights do not total 100% | `REJECT_INPUT` |
| Sell quantity exceeds available holding | `REJECT_TRADE` |
| Excluded instrument is recommended | `REJECT_TRADE` |
| Required fee information is missing | `REVIEW_REQUIRED` |
| Stale price is not flagged | `REVIEW_REQUIRED` |

The anomaly inputs are maintained separately from expected decisions.

- Anomaly inputs: `data/anomalies/anomaly_cases.json`
- Expected labels: `data/ground_truth/ground_truth.csv`

The validation script evaluates the scenarios against the expected decisions and checks that ground-truth labels are not included in the anomaly inputs.

## 7. Project Structure

```text
portfolio-rebalancing-engine/
│
├── app/
│   ├── main.py
│   ├── database.py
│   └── services/
│       ├── policy_service.py
│       ├── portfolio_service.py
│       └── rebalance_service.py
│
├── data/
│   ├── generated/
│   │   ├── database/
│   │   ├── csv/
│   │   └── json/
│   ├── anomalies/
│   └── ground_truth/
│
├── docs/
│   ├── architecture.md
│   ├── business_rules.md
│   ├── database_design.md
│   ├── data_dictionary.md
│   ├── er_diagram.md
│   └── demo_walkthrough.md
│
├── reports/
│
├── scripts/
│   ├── generate_data.py
│   ├── export_data.py
│   ├── validate_schema.py
│   ├── validate_data.py
│   └── verify_reproducibility.py
│
├── tests/
│   ├── test_database.py
│   ├── test_engine.py
│   └── test_negative_scenarios.py
│
├── README.md
├── manifest.json
├── source_manifest.json
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

## 8. Installation and Setup

### Prerequisites

- Python 3.10 or later
- Git
- pip

### Step 1: Clone the repository

```bash
git clone https://github.com/Hemanth-CodeCrafter/portfolio-rebalancing-engine.git
cd portfolio-rebalancing-engine
```

### Step 2: Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### Step 3: Install dependencies

```bash
python -m pip install -r requirements.txt
```

## 9. Running the Application

Start the FastAPI application from the project root:

```bash
uvicorn app.main:app --reload
```

The application will be available at:

| Resource | URL |
|---|---|
| API root | http://127.0.0.1:8000/ |
| Swagger UI | http://127.0.0.1:8000/docs |
| OpenAPI schema | http://127.0.0.1:8000/openapi.json |

Swagger UI can be used to inspect and execute the available API endpoints.

## 10. API Workflow

The main workflow is:

1. Retrieve available portfolios.
2. Retrieve portfolio details and holdings.
3. Analyse current allocation and allocation drift.
4. Generate a rebalancing proposal.
5. Inspect proposal details and recommended trades.
6. Review, approve or reject the proposal.
7. Simulate proposed trades.
8. Inspect post-trade allocation and audit events.

### Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API health/root response |
| GET | `/portfolios` | List portfolios |
| GET | `/portfolios/{portfolio_id}` | Retrieve portfolio details |
| GET | `/portfolios/{portfolio_id}/analysis` | Analyse portfolio allocation |
| POST | `/portfolios/{portfolio_id}/rebalance` | Generate a rebalancing proposal |
| GET | `/proposals/{proposal_id}` | Retrieve proposal details |
| GET | `/proposals/{proposal_id}/trades` | Retrieve proposal trades |
| POST | `/proposals/{proposal_id}/approve` | Approve an eligible proposal |
| POST | `/proposals/{proposal_id}/reject` | Reject a proposal |
| POST | `/proposals/{proposal_id}/simulate` | Simulate proposed trades |
| GET | `/proposals/{proposal_id}/events` | Retrieve proposal-related events |
| GET | `/events` | Retrieve audit events |
| GET | `/trades` | Retrieve trades |

See [docs/demo_walkthrough.md](docs/demo_walkthrough.md) for a step-by-step demonstration.

## 11. Data Generation and Validation

Run the following commands from the repository root.

**Important:** The data generator rebuilds the local SQLite baseline database and overwrites generated exports and manifests. Back up any generated data you need before running it.

### Generate the full dataset

```bash
python -m scripts.generate_data --scale full --seed 20261022
```

### Generate the starter dataset

```bash
python -m scripts.generate_data --scale starter --seed 20261022
```

### Validate the database schema

```bash
python -m scripts.validate_schema
```

### Validate generated data

```bash
python -m scripts.validate_data
```

### Run automated tests

```bash
pytest -v
```

### Verify reproducibility

```bash
python -m scripts.verify_reproducibility --scale starter
```

```bash
python -m scripts.verify_reproducibility --scale full
```

The reproducibility script compares generated file checksums, row counts and primary-key sequences.

The scripts write validation and reproducibility results into the `reports/` directory.

## 12. Validation Results

The committed validation artifacts report the following results.

### Database schema validation

- Status: **PASS**
- Database tables: 11
- Tables with primary keys: 11
- Custom indexes: 8
- Lifecycle and audit triggers: 4
- Foreign-key violations: 0

### Data validation

- Status: **PASS**
- Validation checks: 27/27
- Invalid target-allocation portfolios: 0
- Explicitly stale price rows: 21
- Missing price observations: 18
- Negative scenarios detected: 5/5
- Ground-truth leakage into anomaly inputs: None

### Automated testing

- Tests passed: **18**
- Test failures: 0
- One non-blocking Starlette/httpx deprecation warning was reported.

### Full-scale reproducibility

- Status: **PASS**
- Generated files compared: 26
- Checksum mismatches: 0
- Row counts matched: Yes
- Primary-key sequences matched: Yes

Detailed results are available in:

- `reports/schema_validation.json`
- `reports/validation_summary.json`
- `reports/pytest_results.txt`
- `reports/reproducibility_report.json`

### API workflow demonstration

The recorded successful API workflow demonstrates:

- Portfolio analysis.
- Proposal generation.
- Five proposed trades.
- Proposal approval.
- Post-trade simulation.
- Audit-event creation.

For the demonstration portfolio, TAD decreased from approximately 5.2044 to 0.0153 percentage points after simulation, with INR 75.00 in estimated fees deducted.

A separate exception-path demonstration confirms that an excluded instrument results in `REVIEW_REQUIRED` and that approval and simulation requests are blocked with HTTP 409.

See:

- `reports/api_workflow_report.json`
- `reports/exception_path_report.json`

The baseline database is intentionally kept clean; the demonstration proposals and trades are documented in separate reports rather than retained in the baseline tables.

## 13. Actors and Access Boundaries

The intended business workflow has four conceptual actors:

| Actor | Responsibility |
|---|---|
| Customer / Account Holder | Portfolio ownership, investment profile and target preferences |
| Operations Analyst | Portfolio analysis and proposal generation |
| Risk / Compliance Reviewer | Exception review and proposal approval or rejection |
| System Administrator | Database, application and dataset management |

**Implementation limitation:** The current API does not implement authentication or role-based access control. These actors describe the intended business workflow; they are not enforced application roles.

## 14. Important Design Decisions and Limitations

- Portfolio valuation uses the latest eligible market price on or before the requested valuation date.
- Missing historical prices are not invented or forward-filled.
- Stale prices are identified and affected trades are blocked.
- Financial calculations use Python `Decimal`.
- Sell quantities cannot exceed available holding quantities.
- Applicable constraints and fee schedules are selected using their effective dates.
- Simulation uses an in-memory copy of positions and does not overwrite original Holding records.
- Audit events are protected against update and deletion by database triggers.
- The current `Holding` key represents one canonical portfolio/instrument position rather than a full multi-date position-history table.
- The current rebalancing implementation selects one holding per asset class when sizing trades. The generated baseline has one holding per asset class in each portfolio. Additional instrument-selection logic is needed to support multiple holdings within the same asset class generally.
- The simulation service currently permits proposals in `GENERATED` as well as `APPROVED` status. Approval is supported by the API, but is not yet a mandatory simulation gate.
- The API has no authentication or role-based authorization.
- INR is the baseline currency; FX conversion is out of scope.
- Synthetic prices are not live market observations.

## 15. Future Improvements

Potential improvements include:

- Multi-instrument allocation and trade selection within each asset class.
- Mandatory approval enforcement before simulation.
- Authentication and role-based access controls.
- Additional instrument types and asset classes.
- More advanced liquidity and execution-cost modelling.
- Additional portfolio risk and performance metrics.
- A dedicated frontend for analysis and proposal review.
- Expanded integration and performance testing.

## 16. Disclaimer

This project uses synthetic financial data and simplified trading assumptions.

It is intended for educational, development and demonstration purposes only. It does not constitute investment advice, a recommendation to buy or sell securities, or a production-ready trading system.

---

## Project Summary

The Portfolio Rebalancing Engine demonstrates how portfolio valuation, allocation analysis, policy-constrained trade recommendations, fee calculations, exception handling, proposal lifecycle management, auditability and post-trade simulation can be combined into an end-to-end software workflow.

The implementation emphasizes deterministic data generation, data integrity, documented business rules, validation and traceability.
