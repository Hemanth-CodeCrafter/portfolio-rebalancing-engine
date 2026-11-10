# Portfolio Rebalancing Engine

A deterministic, policy-aware portfolio rebalancing engine built with Python, FastAPI, and SQLite. The project generates a reproducible investment dataset, measures portfolio drift against target allocations, evaluates policy constraints, creates rebalance proposals, enforces an approval gate before simulation, and records trades and entity-level events for traceability.

> **Project status:** Hackathon prototype. The engine and its dataset are designed for demonstration, validation, and controlled testing. The application is not a production investment platform and does not provide investment advice or execute orders with a broker.

## Contents

- [Overview](#overview)
- [What the system does](#what-the-system-does)
- [Proposal and simulation lifecycle](#proposal-and-simulation-lifecycle)
- [Data model](#data-model)
- [Generated dataset](#generated-dataset)
- [Technology](#technology)
- [Repository layout](#repository-layout)
- [Setup](#setup)
- [Generate the dataset](#generate-the-dataset)
- [Run validations and tests](#run-validations-and-tests)
- [Run the API](#run-the-api)
- [API workflow](#api-workflow)
- [Reproducibility](#reproducibility)
- [Validation results](#validation-results)
- [Known limitations and security boundaries](#known-limitations-and-security-boundaries)
- [Documentation and reports](#documentation-and-reports)

## Overview

A portfolio can move away from its intended allocation as asset prices change or holdings are updated. The engine compares current portfolio weights with configured target weights, calculates allocation drift, evaluates configured constraints, and produces a proposal describing potential rebalancing actions.

The system separates proposal generation, approval, and simulation. A generated proposal must reach `APPROVED` before it can be simulated. Proposals marked `REVIEW_REQUIRED` cannot be approved or simulated through the current workflow. Simulation records its outcomes in the application database; it is not a live brokerage execution process.

The project emphasizes:

- Reproducible synthetic data with a fixed seed.
- Explicit portfolio, instrument, holding, target, fee, and constraint records.
- Policy-aware proposal generation and exception handling.
- An approval gate before simulation.
- Post-simulation portfolio and trade visibility.
- Entity-event history for traceability.
- Schema, data, workflow, negative-scenario, and reproducibility checks.

## What the system does

1. **Loads portfolio data.** Reads investors, portfolios, instruments, holdings, prices, targets, fee schedules, and constraints from SQLite.
2. **Analyzes allocation drift.** Compares current allocation with the configured target allocation and identifies differences.
3. **Evaluates policy.** Applies the configured constraints and produces exceptions or review-required outcomes where applicable.
4. **Creates a proposal.** Stores a rebalance proposal and its proposed actions rather than immediately changing the portfolio.
5. **Requires approval.** A proposal must be in `APPROVED` status before simulation is accepted.
6. **Simulates the proposal.** Calculates simulated trade effects and records the resulting state in the database.
7. **Exposes traceability.** Read endpoints expose trades and entity events, and the database retains lifecycle and audit information.

The engine works on the project's synthetic dataset. It does not connect to a custodian, exchange, broker, live market-data provider, or payment system.

## Proposal and simulation lifecycle

The intended proposal workflow is:

```text
GENERATED ──approval──> APPROVED ──simulation──> SIMULATED
     │
     └──policy exception / review outcome──> REVIEW_REQUIRED
```

- `GENERATED`: a proposal has been created but has not passed the approval gate.
- `APPROVED`: the proposal has been approved and is eligible for simulation.
- `REVIEW_REQUIRED`: the proposal requires review and cannot be approved or simulated through the current workflow.
- `SIMULATED`: the proposal has completed simulation.

**Approval is mandatory before simulation.** The simulation service accepts only proposals whose status is `APPROVED`; attempting to simulate a `GENERATED` or `REVIEW_REQUIRED` proposal is rejected. Database lifecycle triggers also enforce the supported proposal and trade status transitions.

The current application does not implement authenticated user identities or role-based authorization. Therefore, the approval state transition is enforced, but the application does not prove that the person invoking the approval endpoint is an authorized risk or compliance reviewer. See [Known limitations and security boundaries](#known-limitations-and-security-boundaries).

## Data model

The database contains the following 11 tables:

| Table | Purpose |
|---|---|
| `investor_profile` | Investor-level profile information. |
| `portfolio` | Portfolio/account records associated with investors. |
| `instrument` | Tradable instrument reference data. |
| `holding` | Current portfolio positions. |
| `market_price` | Synthetic historical market prices. |
| `target_allocation` | Target weights used for allocation comparison. |
| `fee_schedule` | Fee parameters used by the simulation logic. |
| `constraint` | Portfolio and policy constraints used during evaluation. |
| `rebalance_proposal` | Proposal records and their lifecycle status. |
| `trade` | Simulated trade records associated with proposals. |
| `entity_event` | Entity-level lifecycle and audit events. |

Primary keys, foreign keys, indexes, and lifecycle/audit triggers are defined in [`app/schema.sql`](app/schema.sql). The schema validator checks table and key structure, index/trigger presence, and foreign-key integrity.

## Generated dataset

The full baseline is generated with seed `20261022`. The verified clean baseline contains:

| Dataset | Rows |
|---|---:|
| Investor profiles | 1,000 |
| Portfolios | 1,000 |
| Instruments | 50 |
| Holdings | 5,000 |
| Market prices | 12,482 |
| Target allocations | 5,000 |
| Fee schedules | 10 |
| Constraints | 1,055 |
| Rebalance proposals | 0 |
| Trades | 0 |
| Entity events | 0 |

The clean baseline intentionally starts without proposals, trades, or entity events. Those records are created by exercising application workflows. Consequently, trade-level checks over the clean baseline do not demonstrate a populated trade history; trade behavior is exercised separately by the engine integration tests.

Generated data and exports are stored under `data/generated/`. The SQLite database used by the application is `data/generated/database/portfolio_rebalancing.db`; the SQL seed/export file is `data/generated/database/seed.sql`.

## Technology

- **Python** — application and data-generation logic.
- **FastAPI** — HTTP API.
- **SQLite** — relational persistence for the prototype.
- **pytest** — automated tests.

Install dependencies from [`requirements.txt`](requirements.txt).

## Repository layout

```text
.
├── app/
│   ├── main.py                  # FastAPI routes
│   ├── schema.sql               # SQLite schema, constraints, and triggers
│   └── services/                # Portfolio, policy, and rebalance services
├── data/
│   └── generated/
│       └── database/            # Generated SQLite database and SQL export
├── docs/                        # Architecture, rules, data dictionary, ERD, demo guide
├── reports/                     # Validation and reproducibility evidence
├── scripts/                     # Generation and validation commands
├── tests/                       # Automated tests
└── requirements.txt
```

## Setup

The following commands use Windows PowerShell from the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell prevents virtual-environment activation because of the current execution policy, use an approved local execution-policy setting or run the environment's Python executable directly. Do not change a machine-wide policy just for this project.

## Generate the dataset

To generate the full baseline with the project's fixed seed:

```powershell
python -m scripts.generate_data --scale full --seed 20261022
```

The generation command writes the database and generated exports under `data/generated/`. It replaces generated baseline data, so run it when you intentionally want to regenerate the dataset. Do not run it while relying on locally created proposal, trade, or event records that you need to preserve.

The generator also supports the starter scale:

```powershell
python -m scripts.generate_data --scale starter --seed 20261022
```

## Run validations and tests

Run these from the repository root:

```powershell
python -m scripts.validate_schema
python -m scripts.validate_data
pytest -v
```

The schema validation checks the expected tables, primary keys, indexes, triggers, and foreign-key integrity. The data validation checks the generated dataset's structural and business invariants, including the configured negative scenarios.

The latest verified local test run completed with **18 passed**. A non-failing Starlette/httpx deprecation warning was reported by the test environment; it did not affect the test result.

## Run the API

Start the development server from the repository root:

```powershell
uvicorn app.main:app --reload
```

Then open:

- API base URL: `http://127.0.0.1:8000`
- Interactive Swagger documentation: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Use the interactive API documentation to inspect the current request parameters, response models, and available operations. The API operates on the configured SQLite database; make sure the intended generated database exists before starting workflow demonstrations.

## API workflow

The application exposes portfolio analysis and rebalance workflow operations, together with read-only trade and event queries. The main workflow is:

1. Retrieve a portfolio and inspect its current analysis.
2. Generate a rebalance proposal.
3. Inspect the proposal and any policy exceptions.
4. Approve an eligible proposal.
5. Simulate the approved proposal.
6. Query the resulting trades and entity events.

The read endpoints include:

| Endpoint | Purpose |
|---|---|
| `GET /trades` | Read trade records; supports proposal/portfolio filtering and pagination. |
| `GET /events` | Read entity-event records; supports entity filtering and pagination. |

Both endpoints return a paginated response containing `total`, `limit`, `offset`, and `items`. On the clean baseline, they correctly return zero records because no workflow has yet created trades or events.

For the exact paths and request/response schemas of all portfolio and rebalance operations, use `/docs` or `/openapi.json`. The interactive documentation is the source of truth for the running application version.

## Reproducibility

The dataset generator uses a fixed seed so the same scale and seed can be checked for deterministic output. Run both reproducibility checks with:

```powershell
python -m scripts.verify_reproducibility --scale starter
python -m scripts.verify_reproducibility --scale full
```

The verified checks compared 26 generated files for each scale and reported no checksum mismatches, with matching row counts and primary-key sequences.

Use the same generator version, scale, and seed when comparing outputs. A change to generator logic or generated-data definitions may legitimately change checksums and should be reviewed as a dataset change rather than treated as a reproducibility pass.

## Validation results

The latest completed local verification reported:

| Check | Result |
|---|---|
| Schema validation | Passed: 11 tables, primary keys present, 8 indexes, 4 triggers, no foreign-key violations. |
| Data validation | Passed: 27 of 27 checks. |
| Negative scenarios | Passed: 5 of 5 configured scenarios. |
| Automated tests | Passed: 18 tests. |
| Starter reproducibility | Passed: 26 generated files compared; no checksum mismatches. |
| Full reproducibility | Passed: 26 generated files compared; no checksum mismatches. |

These results describe the verified project run. Re-run the commands in [Run validations and tests](#run-validations-and-tests) after making code, schema, or data-generator changes.

## Known limitations and security boundaries

This prototype intentionally has a limited scope. The following items should be considered before using it beyond a controlled demonstration:

- **No authentication or RBAC:** actor roles are documented as conceptual access boundaries. The application does not authenticate users or enforce reviewer/admin permissions on endpoints.
- **Approval identity is not verified:** the proposal status gate is enforced, but the system does not establish that an authenticated, authorized reviewer performed the approval.
- **No live execution:** simulated trades are database records, not broker orders or actual market transactions.
- **Synthetic prices and data:** generated records are for repeatable testing and demonstration, not real investment decisions.
- **Single holding per asset class in the current rebalance mapping:** the rebalance service maps analyzed holdings by asset class. Multiple instruments in the same asset class can overwrite one another in that mapping. The verified baseline has one holding per asset class for the relevant portfolio workflow; broader multi-instrument handling requires a dedicated model and tests.
- **Canonical current holding representation:** the holding key represents the current position rather than a full history of dated position snapshots.
- **SQLite prototype storage:** concurrency, operational resilience, backup, migration, and deployment controls are not designed as production-grade infrastructure.
- **No personalized investment advice:** outputs are mechanical results of the configured targets, data, fees, and constraints. They should not be treated as a recommendation to buy or sell securities.

Do not expose the development API to an untrusted network. Add authentication, authorization, secret management, deployment hardening, operational monitoring, and appropriate legal/compliance review before any real-world use.

## Documentation and reports

Additional project documentation is available in `docs/`, including architecture, business rules, database design, data dictionary, ER diagram, and a demo walkthrough. Generated validation and reproducibility evidence is stored in `reports/`.

Useful starting points:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/business_rules.md`](docs/business_rules.md)
- [`docs/database_design.md`](docs/database_design.md)
- [`docs/data_dictionary.md`](docs/data_dictionary.md)
- [`docs/er_diagram.md`](docs/er_diagram.md)
- [`docs/demo_walkthrough.md`](docs/demo_walkthrough.md)
- [`reports/validation_report.md`](reports/validation_report.md)

---

**Disclaimer:** This repository is an educational/hackathon prototype. It is not financial, legal, tax, or investment advice, and it must not be used to execute real trades.
