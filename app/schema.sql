PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS investor_profile (
    investor_id TEXT PRIMARY KEY CHECK (investor_id GLOB 'INV-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (instr(email, '@') > 1),
    risk_profile TEXT NOT NULL CHECK (risk_profile IN ('CONSERVATIVE','MODERATE','AGGRESSIVE')),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE IF NOT EXISTS portfolio (
    portfolio_id TEXT PRIMARY KEY,
    investor_id TEXT NOT NULL REFERENCES investor_profile(investor_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    portfolio_name TEXT NOT NULL CHECK (length(trim(portfolio_name)) > 0),
    base_currency TEXT NOT NULL DEFAULT 'INR' CHECK (length(base_currency) = 3),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE','CLOSED')),
    UNIQUE (investor_id, portfolio_id),
    CHECK (substr(portfolio_id, 1, length('PORT-' || investor_id || '-')) = 'PORT-' || investor_id || '-')
);

CREATE TABLE IF NOT EXISTS instrument (
    instrument_id TEXT PRIMARY KEY CHECK (instrument_id GLOB 'INS-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    symbol TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (length(trim(symbol)) > 0),
    instrument_name TEXT NOT NULL CHECK (length(trim(instrument_name)) > 0),
    asset_class TEXT NOT NULL CHECK (asset_class IN ('EQUITY','DEBT','GOLD','CASH','OTHER')),
    instrument_type TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (length(currency) = 3),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    is_excluded INTEGER NOT NULL DEFAULT 0 CHECK (is_excluded IN (0,1))
);

CREATE TABLE IF NOT EXISTS holding (
    holding_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL REFERENCES portfolio(portfolio_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    quantity TEXT NOT NULL CHECK (CAST(quantity AS REAL) >= 0),
    as_of_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (portfolio_id, instrument_id, as_of_date),
    CHECK (holding_id = 'HOLD-' || portfolio_id || '-' || instrument_id)
);

CREATE TABLE IF NOT EXISTS market_price (
    market_price_id TEXT PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    price_date TEXT NOT NULL,
    price TEXT NOT NULL CHECK (CAST(price AS REAL) > 0),
    currency TEXT NOT NULL CHECK (length(currency) = 3),
    source TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 0 CHECK (is_stale IN (0,1)),
    daily_volume TEXT CHECK (daily_volume IS NULL OR CAST(daily_volume AS REAL) >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (instrument_id, price_date, source)
);

CREATE TABLE IF NOT EXISTS target_allocation (
    target_allocation_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL REFERENCES portfolio(portfolio_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('EQUITY','DEBT','GOLD','CASH','OTHER')),
    target_weight_pct TEXT NOT NULL CHECK (CAST(target_weight_pct AS REAL) >= 0 AND CAST(target_weight_pct AS REAL) <= 100),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    created_at TEXT NOT NULL,
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    UNIQUE (portfolio_id, asset_class, effective_from)
);

CREATE TABLE IF NOT EXISTS fee_schedule (
    fee_schedule_id TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('EQUITY','DEBT','GOLD','CASH','OTHER')),
    min_trade_value TEXT NOT NULL CHECK (CAST(min_trade_value AS REAL) >= 0),
    max_trade_value TEXT CHECK (max_trade_value IS NULL OR CAST(max_trade_value AS REAL) >= CAST(min_trade_value AS REAL)),
    fee_type TEXT NOT NULL CHECK (fee_type IN ('FIXED','PERCENTAGE','HYBRID')),
    fee_rate TEXT NOT NULL DEFAULT '0' CHECK (CAST(fee_rate AS REAL) >= 0),
    fixed_fee TEXT NOT NULL DEFAULT '0' CHECK (CAST(fixed_fee AS REAL) >= 0),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE')),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    UNIQUE (asset_class, min_trade_value, effective_from)
);

CREATE TABLE IF NOT EXISTS constraint_rule (
    constraint_id TEXT PRIMARY KEY,
    portfolio_id TEXT REFERENCES portfolio(portfolio_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    instrument_id TEXT REFERENCES instrument(instrument_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    constraint_type TEXT NOT NULL CHECK (constraint_type IN ('MIN_TRADE_SIZE','MAX_TRADE_SIZE','MIN_LIQUIDITY','EXCLUDED_INSTRUMENT')),
    operator TEXT NOT NULL CHECK (operator IN ('GT','GTE','LT','LTE','EQ','NE')),
    threshold_value TEXT NOT NULL,
    threshold_unit TEXT NOT NULL CHECK (threshold_unit IN ('INR','PERCENT','UNITS','FLAG')),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE')),
    CHECK ((portfolio_id IS NOT NULL) <> (instrument_id IS NOT NULL)),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS rebalance_proposal (
    proposal_id TEXT PRIMARY KEY CHECK (proposal_id GLOB 'RB-2026-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    portfolio_id TEXT NOT NULL REFERENCES portfolio(portfolio_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    as_of_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'GENERATED' CHECK (status IN ('GENERATED','REVIEW_REQUIRED','APPROVED','REJECTED','SIMULATED')),
    pre_trade_value TEXT NOT NULL CHECK (CAST(pre_trade_value AS REAL) >= 0),
    post_trade_value TEXT CHECK (post_trade_value IS NULL OR CAST(post_trade_value AS REAL) >= 0),
    pre_trade_drift_pct TEXT NOT NULL,
    post_trade_drift_pct TEXT,
    exception_count INTEGER NOT NULL DEFAULT 0 CHECK (exception_count >= 0),
    decision_summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade (
    trade_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES rebalance_proposal(proposal_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    fee_schedule_id TEXT REFERENCES fee_schedule(fee_schedule_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity TEXT NOT NULL CHECK (CAST(quantity AS REAL) > 0),
    estimated_price TEXT NOT NULL CHECK (CAST(estimated_price AS REAL) > 0),
    gross_value TEXT NOT NULL CHECK (CAST(gross_value AS REAL) > 0),
    estimated_fee TEXT NOT NULL CHECK (CAST(estimated_fee AS REAL) >= 0),
    status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED','APPROVED','REJECTED','SIMULATED','EXECUTED')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_event (
    event_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('INVESTOR','PORTFOLIO','HOLDING','PROPOSAL','TRADE','CONSTRAINT')),
    entity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    event_timestamp TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_portfolio_investor ON portfolio(investor_id);
CREATE INDEX IF NOT EXISTS idx_holding_portfolio_date ON holding(portfolio_id, as_of_date);
CREATE INDEX IF NOT EXISTS idx_holding_instrument ON holding(instrument_id);
CREATE INDEX IF NOT EXISTS idx_price_instrument_date ON market_price(instrument_id, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_target_portfolio_dates ON target_allocation(portfolio_id, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_trade_proposal ON trade(proposal_id);
CREATE INDEX IF NOT EXISTS idx_proposal_portfolio_date ON rebalance_proposal(portfolio_id, as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_constraint_scope_dates ON constraint_rule(portfolio_id, instrument_id, effective_from, effective_to);

-- Enforce legal lifecycle transitions and append-only audit history.
CREATE TRIGGER IF NOT EXISTS trg_proposal_status_transition
BEFORE UPDATE OF status ON rebalance_proposal
WHEN OLD.status <> NEW.status AND NOT (
    (OLD.status = 'GENERATED' AND NEW.status IN ('APPROVED','REJECTED','SIMULATED')) OR
    (OLD.status = 'REVIEW_REQUIRED' AND NEW.status = 'REJECTED') OR
    (OLD.status = 'APPROVED' AND NEW.status = 'SIMULATED')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid rebalance proposal lifecycle transition');
END;

CREATE TRIGGER IF NOT EXISTS trg_trade_status_transition
BEFORE UPDATE OF status ON trade
WHEN OLD.status <> NEW.status AND NOT (
    (OLD.status = 'PROPOSED' AND NEW.status IN ('APPROVED','REJECTED','SIMULATED','EXECUTED')) OR
    (OLD.status = 'APPROVED' AND NEW.status IN ('REJECTED','SIMULATED','EXECUTED')) OR
    (OLD.status = 'SIMULATED' AND NEW.status = 'EXECUTED')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid trade lifecycle transition');
END;

CREATE TRIGGER IF NOT EXISTS trg_entity_event_no_update
BEFORE UPDATE ON entity_event
BEGIN
    SELECT RAISE(ABORT, 'entity_event is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_entity_event_no_delete
BEFORE DELETE ON entity_event
BEGIN
    SELECT RAISE(ABORT, 'entity_event is append-only');
END;
