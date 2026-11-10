# Data dictionary

All IDs are immutable text primary keys. Financial quantities, prices, fees and percentages are decimal strings in SQLite and must be parsed as Python `Decimal`. Timestamps use ISO-8601; business dates use `YYYY-MM-DD`. Synthetic baseline currency is INR.

## InvestorProfile — `investor_profile`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| investor_id | TEXT | Yes | `INV-` + 6 digits | PK; immutable format |
| full_name | TEXT | Yes | Synthetic display name | Non-empty |
| email | TEXT | Yes | `example.test` synthetic address | Unique, case-insensitive; contains `@` |
| risk_profile | TEXT | Yes | CONSERVATIVE, MODERATE, AGGRESSIVE | Enum CHECK |
| created_at | TEXT | Yes | ISO-8601 | Non-empty |
| status | TEXT | Yes | ACTIVE, INACTIVE | Enum CHECK; default ACTIVE |

## Portfolio — `portfolio`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| portfolio_id | TEXT | Yes | `PORT-<investor-id>-01` | PK; investor prefix checked |
| investor_id | TEXT | Yes | InvestorProfile ID | FK; RESTRICT delete/update |
| portfolio_name | TEXT | Yes | Text | Non-empty |
| base_currency | TEXT | Yes | ISO-like 3-letter code; INR baseline | Length 3 |
| created_at | TEXT | Yes | ISO-8601 | Non-empty |
| status | TEXT | Yes | ACTIVE, INACTIVE, CLOSED | Enum CHECK |

## Instrument — `instrument`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| instrument_id | TEXT | Yes | `INS-` + 6 digits | PK |
| symbol | TEXT | Yes | Synthetic ticker | Unique, case-insensitive |
| instrument_name | TEXT | Yes | Text | Non-empty |
| asset_class | TEXT | Yes | EQUITY, DEBT, GOLD, CASH, OTHER | Enum CHECK |
| instrument_type | TEXT | Yes | ETF, DEPOSIT, etc. | Non-empty |
| currency | TEXT | Yes | 3-letter code | Length 3 |
| is_active | INTEGER | Yes | 0/1 | Boolean CHECK |
| is_excluded | INTEGER | Yes | 0/1 | Boolean CHECK |

## Holding — `holding`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| holding_id | TEXT | Yes | `HOLD-<portfolio-id>-<instrument-id>` | PK; exact canonical expression |
| portfolio_id | TEXT | Yes | Portfolio ID | FK |
| instrument_id | TEXT | Yes | Instrument ID | FK |
| quantity | TEXT | Yes | Instrument units | Decimal >= 0 |
| as_of_date | TEXT | Yes | YYYY-MM-DD | Snapshot date |
| created_at | TEXT | Yes | ISO-8601 | Non-empty |
| portfolio_id + instrument_id + as_of_date | — | — | — | Unique snapshot tuple |

The canonical holding ID has no date component; the implementation therefore treats one row per portfolio/instrument as the canonical position. `as_of_date` makes the represented valuation date explicit. Full multi-date position history would require an additional snapshot table.

## MarketPrice — `market_price`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| market_price_id | TEXT | Yes | `MP-` + 9 digits | PK |
| instrument_id | TEXT | Yes | Instrument ID | FK |
| price_date | TEXT | Yes | YYYY-MM-DD | Historical date |
| price | TEXT | Yes | Currency per unit | Decimal > 0 |
| currency | TEXT | Yes | 3-letter code | Length 3 |
| source | TEXT | Yes | SYNTHETIC_FIXED_SEED | Non-empty |
| is_stale | INTEGER | Yes | 0/1 | Boolean CHECK |
| daily_volume | TEXT | No | Instrument units/day | Decimal >= 0 or NULL |
| created_at | TEXT | Yes | ISO-8601 | Non-empty |
| instrument_id + price_date + source | — | — | — | Unique natural key |

## TargetAllocation — `target_allocation`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| target_allocation_id | TEXT | Yes | `TA-...` | PK |
| portfolio_id | TEXT | Yes | Portfolio ID | FK |
| asset_class | TEXT | Yes | Five asset classes | Enum CHECK |
| target_weight_pct | TEXT | Yes | Percent, 0–100 | Decimal range; per active portfolio/date sum must equal 100% (cross-row validator) |
| effective_from | TEXT | Yes | YYYY-MM-DD | Start inclusive |
| effective_to | TEXT | No | YYYY-MM-DD or NULL | End inclusive; >= start |
| created_at | TEXT | Yes | ISO-8601 | Non-empty |
| portfolio_id + asset_class + effective_from | — | — | — | Unique natural key |

## Trade — `trade`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| trade_id | TEXT | Yes | `TR-<proposal-seq>-<trade-seq>` | PK |
| proposal_id | TEXT | Yes | RebalanceProposal ID | FK |
| instrument_id | TEXT | Yes | Instrument ID | FK |
| fee_schedule_id | TEXT | No | FeeSchedule ID | Optional FK; NULL is an exception if fee required |
| side | TEXT | Yes | BUY, SELL | Enum CHECK |
| quantity | TEXT | Yes | Instrument units | Decimal > 0 |
| estimated_price | TEXT | Yes | Currency/unit | Decimal > 0 |
| gross_value | TEXT | Yes | Base currency | Decimal > 0; quantity × price reconciliation |
| estimated_fee | TEXT | Yes | Base currency | Decimal >= 0; fee schedule reconciliation |
| status | TEXT | Yes | PROPOSED, APPROVED, REJECTED, SIMULATED, EXECUTED | Enum CHECK |
| created_at | TEXT | Yes | ISO-8601 | Non-empty |

## FeeSchedule — `fee_schedule`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| fee_schedule_id | TEXT | Yes | `FEE-...` | PK |
| asset_class | TEXT | Yes | Five asset classes | Enum CHECK |
| min_trade_value | TEXT | Yes | Currency | Decimal >= 0 |
| max_trade_value | TEXT | No | Currency or NULL | >= minimum |
| fee_type | TEXT | Yes | FIXED, PERCENTAGE, HYBRID | Enum CHECK |
| fee_rate | TEXT | Yes | Decimal fraction | >= 0 |
| fixed_fee | TEXT | Yes | Currency | >= 0 |
| effective_from | TEXT | Yes | YYYY-MM-DD | Start inclusive |
| effective_to | TEXT | No | YYYY-MM-DD or NULL | >= start |
| status | TEXT | Yes | ACTIVE, INACTIVE | Enum CHECK |
| asset_class + min_trade_value + effective_from | — | — | — | Unique tier start per effective date |

## Constraint — `constraint_rule`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| constraint_id | TEXT | Yes | `CON-...` | PK |
| portfolio_id | TEXT | Conditional | Portfolio ID | Optional FK; mutually exclusive with instrument_id |
| instrument_id | TEXT | Conditional | Instrument ID | Optional FK; exactly one scope required |
| constraint_type | TEXT | Yes | MIN_TRADE_SIZE, MAX_TRADE_SIZE, MIN_LIQUIDITY, EXCLUDED_INSTRUMENT | Enum CHECK |
| operator | TEXT | Yes | GT, GTE, LT, LTE, EQ, NE | Enum CHECK |
| threshold_value | TEXT | Yes | Numeric text | Parsed as Decimal by policy service |
| threshold_unit | TEXT | Yes | INR, PERCENT, UNITS, FLAG | Enum CHECK |
| effective_from | TEXT | Yes | YYYY-MM-DD | Start inclusive |
| effective_to | TEXT | No | YYYY-MM-DD or NULL | >= start |
| status | TEXT | Yes | ACTIVE, INACTIVE | Enum CHECK |

## RebalanceProposal — `rebalance_proposal`

| Field | Type | Req. | Allowed / unit | Unique / validation |
|---|---|---:|---|---|
| proposal_id | TEXT | Yes | `RB-2026-` + 6 digits | PK |
| portfolio_id | TEXT | Yes | Portfolio ID | FK |
| as_of_date | TEXT | Yes | YYYY-MM-DD | Valuation date |
| status | TEXT | Yes | GENERATED, REVIEW_REQUIRED, APPROVED, REJECTED, SIMULATED | Enum CHECK |
| pre_trade_value | TEXT | Yes | Currency | Decimal >= 0 |
| post_trade_value | TEXT | No | Currency | Decimal >= 0 |
| pre_trade_drift_pct | TEXT | Yes | Percentage points | Total absolute drift |
| post_trade_drift_pct | TEXT | No | Percentage points | Recomputed after simulation |
| exception_count | INTEGER | Yes | Count | Integer >= 0 |
| decision_summary | TEXT | Yes | JSON text | Explainable decisions and exceptions |
| created_at | TEXT | Yes | ISO-8601 | Non-empty |

## Supporting EntityEvent — `entity_event`

`event_id` PK; `entity_type` enum; `entity_id` polymorphic reference; `event_type`; optional previous/new state; ISO timestamp; reason. It is append-only by service convention. A polymorphic `entity_id` cannot be protected by a single ordinary FK; service-level existence validation is required.
