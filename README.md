# Portfolio Rebalancing Engine

A policy-constrained portfolio rebalancing system that compares an investor's current portfolio allocation against target allocation and generates trade recommendations while considering investment constraints, transaction fees, data quality and risk policies.

## 1. Project Overview

The Portfolio Rebalancing Engine is a Python-based application designed to demonstrate an end-to-end portfolio rebalancing workflow.

The system analyses portfolio holdings, calculates current asset allocation and allocation drift, compares the results with the investor's target allocation, and generates rebalancing proposals.

Before a proposal can be approved or simulated, the system evaluates relevant business rules, including:

- Minimum and maximum trade sizes
- Excluded instruments
- Liquidity constraints
- Transaction fees
- Missing and stale market prices
- Available holding quantities

The application also maintains proposal lifecycle information and audit events so that important state changes can be traced.

This project uses synthetic financial data and is intended for educational and demonstration purposes. It is not intended to provide real-world investment advice.

## 2. Project Objectives

The main objectives of this project are to:

- Compare current portfolio holdings with target asset allocation.
- Calculate portfolio value, allocation weights and allocation drift.
- Generate policy-constrained buy and sell recommendations.
- Apply transaction fee calculations and trading constraints.
- Identify missing data, stale prices and policy exceptions.
- Generate, review and approve rebalancing proposals.
- Simulate post-trade portfolio allocation.
- Preserve proposal history and record relevant state changes.
- Validate data integrity, business rules and reproducibility.

## 3. Key Features

### Portfolio Analysis
- Calculates portfolio value using holdings and dated market prices.
- Computes current allocation by asset class.
- Compares current allocation against target allocation.
- Calculates allocation drift and identifies deviations.

### Rebalancing Recommendations
- Identifies instruments that may need to be bought or sold.
- Generates trade recommendations based on allocation drift.
- Checks available holding quantities before proposing sell trades.
- Applies configured trading constraints.

### Policy and Fee Management
- Supports minimum trade size rules.
- Supports maximum trade size rules.
- Supports minimum liquidity requirements.
- Prevents recommendations involving excluded instruments.
- Calculates estimated transaction fees using fee schedules.

### Exception Handling
- Detects missing and stale market prices.
- Identifies policy violations.
- Flags proposals that require additional review.
- Prevents approval or simulation when proposal conditions are not satisfied.

### Proposal Lifecycle and Audit History
- Creates rebalancing proposals with deterministic identifiers.
- Supports proposal review, approval and rejection.
- Records relevant state changes as audit events.
- Preserves historical records rather than silently overwriting them.

### Post-Trade Simulation
- Simulates the effect of proposed trades.
- Calculates estimated transaction fees.
- Recomputes post-trade portfolio allocation.
- Measures the remaining allocation drift and improvement.

## 4. Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| API framework | FastAPI |
| Database | SQLite |
| Data validation | Python validation logic |
| Testing | pytest |
| API documentation | Swagger UI / OpenAPI |
| Data formats | CSV, JSON and SQL seed data |

## 5. Data Model

The application uses related master, dependent and transaction entities.

### Core entities

| Entity | Purpose |
|---|---|
| InvestorProfile | Stores synthetic investor profiles and risk information |
| Portfolio | Represents an investor's portfolio |
| Instrument | Stores instrument and asset-class information |
| Holding | Stores instrument quantities held in a portfolio |
| MarketPrice | Stores dated instrument market prices |
| TargetAllocation | Stores the target allocation for a portfolio |
| Trade | Stores proposed trade information |
| FeeSchedule | Defines transaction fee rules |
| Constraint | Stores applicable trading and policy constraints |
| RebalanceProposal | Represents a generated rebalancing proposal |

The database also includes an audit-event entity for recording relevant state changes.

Primary keys, foreign keys, relationships, effective dates and lifecycle rules are defined as part of the database design.

## 6. Synthetic Dataset

The project uses deterministic synthetic data generated with a fixed random seed.

### Full dataset coverage

| Dataset | Records |
|---|---:|
| Investor profiles | 1,000 |
| Portfolios | 1,000 |
| Distinct instruments | 50 |
| Holdings | 5,000 |
| Market-price records | 12,482 |
| Target allocations | 5,000 |
| Fee schedules | 10 |
| Constraint rules | 1,055 |

The market-price dataset covers 250 trading days.

The generated data includes meaningful variation and scenarios involving missing prices, stale prices, high allocation drift, liquidity constraints and different fee tiers.

**Random seed:** `20261022`

The same data-generation logic supports starter and full dataset scales.

### Deterministic ID conventions

The project follows the specified identifier conventions:

- Investor: `INV-000001`
- Portfolio: `PORT-<investor-id>-01`
- Instrument: `INS-000001`
- Holding: `HOLD-<portfolio-id>-<instrument-id>`
- Rebalance proposal: `RB-2026-000001`

Identifiers are designed to remain consistent across related records and exported datasets.

## 7. Negative Scenarios and Ground Truth

Five deliberate edge cases are included to evaluate the system's ability to detect invalid inputs and policy exceptions.

| Scenario | Expected decision |
|---|---|
| Portfolio weights do not sum to 100% | REJECT_INPUT |
| Proposed sell quantity exceeds available holding | REJECT_TRADE |
| Excluded instrument is recommended | REJECT_TRADE |
| Required transaction fee is missing | REVIEW_REQUIRED |
| Stale price is used without being flagged | REVIEW_REQUIRED |

Known anomaly labels and expected decisions are maintained separately in the ground-truth dataset.

This separation helps prevent expected outcomes from leaking into the input data used for validation.

## 8. Project Structure

The main project structure is organised as follows:

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
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

## 9. Installation and Setup

### Prerequisites

- Python 3.10 or later
- Git
- pip

### Step 1: Clone the repository

```bash
git clone <your-github-repository-url>
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
pip install -r requirements.txt
```

## 10. Running the Application

Start the FastAPI application from the project root:

```bash
uvicorn app.main:app --reload
```

The application will be available at:

- API root: http://127.0.0.1:8000/
- Swagger documentation: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

Swagger UI can be used to execute and inspect the available API endpoints.

## 11. API Workflow

The main API workflow follows these steps:

1. Retrieve available portfolios.
2. Retrieve portfolio details and holdings.
3. Analyse current allocation and allocation drift.
4. Generate a rebalancing proposal.
5. Inspect proposal details and recommended trades.
6. Approve or reject the proposal, subject to policy checks.
7. Simulate the proposed trades.
8. Inspect audit events and proposal history.

### Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API health/root response |
| GET | `/portfolios` | List portfolios |
| GET | `/portfolios/{portfolio_id}` | Retrieve portfolio details |
| GET | `/portfolios/{portfolio_id}/analysis` | Analyse portfolio allocation |
| POST | `/portfolios/{portfolio_id}/rebalance` | Generate a rebalance proposal |
| GET | `/proposals/{proposal_id}` | Retrieve proposal details |
| GET | `/proposals/{proposal_id}/trades` | Retrieve proposal trades |
| POST | `/proposals/{proposal_id}/approve` | Approve a proposal |
| POST | `/proposals/{proposal_id}/reject` | Reject a proposal |
| POST | `/proposals/{proposal_id}/simulate` | Simulate proposed trades |
| GET | `/proposals/{proposal_id}/events` | Retrieve proposal events |
| GET | `/events` | Retrieve audit events |
| GET | `/trades` | Retrieve trade records |

### Example: Generate a rebalancing proposal

The rebalance endpoint expects an ISO-format date in its JSON request body.

```json
{
  "as_of_date": "YYYY-MM-DD"
}
```

Use a date supported by the available market-price data.

The generated proposal ID can then be used to retrieve proposal details, inspect trades, approve or reject the proposal, and run the simulation.

## 12. Data Generation and Validation

The project includes scripts for generating, exporting and validating synthetic datasets.

The following commands are used for validation:

### Database schema validation

```bash
python -m scripts.validate_schema
```

Checks expected tables, primary keys, foreign-key integrity, indexes and lifecycle/audit triggers.

### Data validation

```bash
python -m scripts.validate_data
```

Checks identifiers, relationships, allocation totals, arithmetic reconciliation, fee calculations, trade constraints and negative scenarios.

### Automated tests

```bash
pytest -v
```

### Reproducibility verification

```bash
python -m scripts.verify_reproducibility --scale starter
```

```bash
python -m scripts.verify_reproducibility --scale full
```

These commands compare generated outputs using the fixed seed and check whether row counts and file contents remain consistent.

For data-generation and export options, refer to the corresponding scripts and their available command-line arguments.

## 13. Validation Results

The project was tested using automated tests, schema validation, data validation, negative-scenario checks and reproducibility verification.

The latest recorded results include:

- 18 automated tests passed.
- 11 database tables validated.
- 8 database indexes verified.
- 4 lifecycle and audit triggers verified.
- Zero foreign-key violations.
- Five negative scenarios evaluated against expected decisions.
- 10 trade records validated.
- Portfolio weights recomputed from source holdings and dated market prices.
- Starter dataset reproducibility passed.
- Full dataset reproducibility passed.
- Fixed random seed: `20261022`.

A Starlette/httpx deprecation warning was observed during testing. It did not cause any test failures.

Validation outputs and supporting reports are maintained in the `reports/` directory.

## 14. Business Rules and Important Design Decisions

The engine follows documented policy rules when evaluating rebalancing recommendations.

Examples include:

- A sell recommendation must not exceed the available holding quantity.
- Excluded instruments must not be recommended for trading.
- Trade sizes must comply with configured minimum and maximum limits.
- Liquidity requirements must be considered.
- Required transaction fees must be available and calculated.
- Missing or stale market prices must be identified.
- Proposals with unresolved exceptions require review rather than unrestricted approval.

Post-trade allocation is recalculated from the simulated holdings and applicable market prices rather than being independently generated.

The simulation is intended to evaluate the proposed outcome and does not directly overwrite the original source holdings.

Further details are available in `docs/business_rules.md` and `docs/architecture.md`.

## 15. Limitations and Future Improvements

This is an educational prototype built using synthetic data.

Possible future improvements include:

- Support for additional instrument types and asset classes.
- More advanced liquidity and execution-cost modelling.
- Enhanced risk and portfolio performance metrics.
- Additional API authentication and role-based access controls.
- A dedicated frontend for portfolio analysis and proposal review.
- More extensive integration and performance testing.

## 16. Disclaimer

This project uses synthetic financial data and simplified trading assumptions.

It is intended for educational, development and demonstration purposes only. It does not constitute investment advice, a recommendation to buy or sell securities, or a production-ready trading system.

---

## Project Summary

The Portfolio Rebalancing Engine demonstrates how portfolio allocation analysis, policy-based trade recommendations, fee calculations, exception handling, proposal lifecycle management, auditability and post-trade simulation can be combined into one end-to-end workflow.

The implementation focuses on data consistency, deterministic generation, documented business rules, validation and traceability.