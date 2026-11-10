# Business rules and calculation assumptions

## Valuation and allocation

1. Select the latest market price with `price_date <= as_of_date` for each holding.
2. Holding market value = `quantity × selected price`.
3. Portfolio value = sum of priced holding market values. A holding with no historical price blocks proposal generation; the engine does not invent a price.
4. Current asset-class weight = `asset-class market value / portfolio value × 100`.
5. Drift = `current weight − target weight` in percentage points.
6. Total Absolute Drift (TAD) = sum of absolute asset-class drifts.
7. Target allocation rows effective on the valuation date must total exactly 100% within a small decimal tolerance.

## Price quality

- A price is stale if its source `is_stale` flag is true or it is more than five calendar days old on the valuation date.
- Stale prices are disclosed as exceptions and trades on the affected instrument are blocked.
- Missing prices are not forward-filled; if a holding has no historical price, proposal generation is blocked.

## Proposal logic

For each asset class, target value less current value determines the direction and notional amount. Positive difference implies BUY; negative difference implies SELL. Quantity is rounded to 4 decimal places. A SELL is capped at the available holding quantity. No recommendation is produced for excluded or inactive instruments.

## Policy constraints

- Apply only ACTIVE rules effective on the proposal date.
- A constraint row has exactly one scope: portfolio OR instrument.
- Enforce minimum/maximum trade size and minimum daily volume when configured.
- Select an effective ACTIVE FeeSchedule for the asset class whose minimum/maximum trade-value band contains the rounded gross trade value. Missing fee tier means no trade is emitted and an exception is recorded. The synthetic baseline has two non-overlapping tiers per asset class.
- Fee formulas: FIXED = fixed fee; PERCENTAGE = gross × fee rate; HYBRID = fixed fee + gross × fee rate. Round fees to INR 0.01.
- `daily_volume` is instrument units/day. Liquidity checks compare this with a `UNITS` threshold.
- A proposal with any exception is REVIEW_REQUIRED and cannot be simulated or approved automatically. Reviewer approval is allowed only for exception-free GENERATED proposals.

## Simulation

- Apply proposed trades to an in-memory copy of source holding quantities.
- Deduct total estimated fees from the cash asset-class position; if cash cannot cover fees, simulation fails.
- Recalculate post-trade values, weights and TAD from simulated quantities and dated prices.
- Original Holding rows are not modified. Proposal/trade status changes are recorded in `entity_event`.

## Synthetic baseline assumptions

- Base currency is INR; all synthetic instruments are INR-denominated. FX conversion is out of scope.
- Prices are synthetic random walks generated with fixed seed 20261022; they are not market observations.
- Risk target allocations: Conservative 30/45/10/10/5, Moderate 50/25/10/10/5, Aggressive 70/10/10/5/5 across EQUITY/DEBT/GOLD/CASH/OTHER.
- 10% of portfolios receive a larger but valid allocation drift. No investment return or investor behavior is inferred from real persons.
- This is an educational simulation, not investment advice or an execution system.
