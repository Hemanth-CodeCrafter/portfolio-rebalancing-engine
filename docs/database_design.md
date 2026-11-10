# Database design — Phase 2

SQLite is the system of record. The schema contains the ten required business entities plus `entity_event` for append-only state-transition history. Foreign-key enforcement is enabled on every application connection.

## Relationships and cardinality

- InvestorProfile 1:N Portfolio.
- Portfolio 1:N Holding; Instrument 1:N Holding. Holding is the associative entity for the Portfolio–Instrument N:M relationship.
- Instrument 1:N MarketPrice.
- Portfolio 1:N TargetAllocation (effective-dated rows).
- Portfolio 1:N RebalanceProposal.
- RebalanceProposal 1:N Trade; Instrument 1:N Trade.
- FeeSchedule 1:N Trade; Trade's fee schedule is optional for exception detection.
- Portfolio 0:N Constraint and Instrument 0:N Constraint. A constraint row must reference exactly one scope.
- EntityEvent is a polymorphic audit log; entity_id is intentionally not an FK because it refers to several entity tables. Application validation must verify the referenced entity exists.

## Key and history decisions

IDs follow the specified prefixes. `holding_id` is exactly `HOLD-<portfolio-id>-<instrument-id>`. Consequently, the same portfolio/instrument pair cannot have multiple historical Holding rows under this key. The table represents the current/as-of snapshot for that pair; `as_of_date` records its valuation date. If full multi-date holding snapshots are required, add a separate `holding_snapshot` history table keyed by snapshot ID while retaining this canonical Holding ID as the stable position identity. Do not change the required ID silently.

MarketPrice is historical and unique by instrument, date and source. TargetAllocation, FeeSchedule and Constraint are effective-dated; overlapping active periods must be checked by the validation/business layer. Trade and proposal statuses are constrained enums. State changes should be appended to `entity_event`, not treated as a substitute for current state.

## Financial storage

Financial quantities and rates are stored as decimal text to avoid SQLite binary floating-point storage. Application calculations must parse and compute them with Python `Decimal`. `daily_volume` is retained because MIN_LIQUIDITY constraints require a measure of market liquidity; it is expressed in instrument units and may be NULL when unavailable.

## Integrity boundaries

SQLite enforces row-level checks, PKs, unique keys and FKs. Cross-row rules—such as target weights totaling 100%, non-overlapping effective periods, fee reconciliation and lifecycle transitions—are validated by application scripts because ordinary SQLite CHECK constraints cannot aggregate across rows.
