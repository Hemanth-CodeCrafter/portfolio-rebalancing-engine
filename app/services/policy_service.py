
"""Deterministic trade policy, validation, and fee calculations."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

D = Decimal

CENT = D("0.01")
QTY = D("0.0001")
ZERO = D("0")


def quantize_money(value: Decimal) -> Decimal:
    """Round a monetary value to two decimal places."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def quantize_qty(value: Decimal) -> Decimal:
    """Round a trade quantity to four decimal places."""
    return value.quantize(QTY, rounding=ROUND_HALF_UP)


def calculate_fee(gross: Decimal, schedule: Any) -> Decimal:
    """Calculate a fee using FIXED, PERCENTAGE, or HYBRID pricing."""
    fee_type = schedule["fee_type"]
    rate = D(schedule["fee_rate"])
    fixed = D(schedule["fixed_fee"])

    if gross < ZERO:
        raise ValueError("Gross trade value cannot be negative")

    if fee_type == "FIXED":
        fee = fixed
    elif fee_type == "PERCENTAGE":
        fee = gross * rate
    elif fee_type == "HYBRID":
        fee = fixed + gross * rate
    else:
        raise ValueError(f"Unsupported fee type: {fee_type}")

    if fee < ZERO:
        raise ValueError("Calculated fee cannot be negative")

    return quantize_money(fee)


def _compare_operator(
    actual: Decimal,
    operator: str,
    threshold: Decimal,
) -> bool:
    """Evaluate a stored constraint operator."""

    comparisons = {
        "GT": actual > threshold,
        "GTE": actual >= threshold,
        "LT": actual < threshold,
        "LTE": actual <= threshold,
        "EQ": actual == threshold,
        "NE": actual != threshold,
    }

    if operator not in comparisons:
        raise ValueError(f"Unsupported constraint operator: {operator}")

    return comparisons[operator]


def policy_for_instrument(
    conn,
    portfolio_id: str,
    instrument_id: str,
    asset_class: str,
    gross: Decimal,
    daily_volume: Decimal | None,
    as_of_date: str,
) -> list[dict]:
    """
    Evaluate active, effective portfolio/instrument constraints.

    Constraint operators are interpreted from the database.
    A policy violation is returned as an issue; the proposal
    generator is responsible for blocking the affected trade.
    """

    issues = []

    rules = conn.execute(
        """
        SELECT *
        FROM constraint_rule
        WHERE status = 'ACTIVE'
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to >= ?)
          AND (portfolio_id = ? OR instrument_id = ?)
        """,
        (
            as_of_date,
            as_of_date,
            portfolio_id,
            instrument_id,
        ),
    ).fetchall()

    for rule in rules:
        constraint_type = rule["constraint_type"]
        operator = rule["operator"]
        threshold = D(rule["threshold_value"])
        threshold_unit = rule["threshold_unit"]

        try:
            if constraint_type == "EXCLUDED_INSTRUMENT":
                if threshold_unit != "FLAG":
                    raise ValueError(
                        "EXCLUDED_INSTRUMENT requires FLAG threshold unit"
                    )

                actual = D("1")

                violated = _compare_operator(
                    actual,
                    operator,
                    threshold,
                )

                if violated:
                    issues.append({
                        "code": "EXCLUDED_INSTRUMENT",
                        "constraint_id": rule["constraint_id"],
                        "message": (
                            "Instrument is excluded by active policy"
                        ),
                    })

            elif constraint_type == "MIN_TRADE_SIZE":
                if threshold_unit != "INR":
                    raise ValueError(
                        "MIN_TRADE_SIZE requires INR threshold unit"
                    )

                violated = not _compare_operator(
                    gross,
                    operator,
                    threshold,
                )

                if violated:
                    issues.append({
                        "code": "BELOW_MIN_TRADE",
                        "constraint_id": rule["constraint_id"],
                        "message": (
                            f"Trade value {gross} does not satisfy "
                            f"{operator} {threshold}"
                        ),
                    })

            elif constraint_type == "MAX_TRADE_SIZE":
                if threshold_unit != "INR":
                    raise ValueError(
                        "MAX_TRADE_SIZE requires INR threshold unit"
                    )

                violated = not _compare_operator(
                    gross,
                    operator,
                    threshold,
                )

                if violated:
                    issues.append({
                        "code": "ABOVE_MAX_TRADE",
                        "constraint_id": rule["constraint_id"],
                        "message": (
                            f"Trade value {gross} does not satisfy "
                            f"{operator} {threshold}"
                        ),
                    })

            elif constraint_type == "MIN_LIQUIDITY":
                if threshold_unit != "UNITS":
                    raise ValueError(
                        "MIN_LIQUIDITY requires UNITS threshold unit"
                    )

                if daily_volume is None:
                    issues.append({
                        "code": "LOW_LIQUIDITY",
                        "constraint_id": rule["constraint_id"],
                        "message": "Instrument daily volume is unavailable",
                    })
                else:
                    violated = not _compare_operator(
                        daily_volume,
                        operator,
                        threshold,
                    )

                    if violated:
                        issues.append({
                            "code": "LOW_LIQUIDITY",
                            "constraint_id": rule["constraint_id"],
                            "message": (
                                f"Daily volume {daily_volume} does not "
                                f"satisfy {operator} {threshold}"
                            ),
                        })

            else:
                issues.append({
                    "code": "UNKNOWN_CONSTRAINT_TYPE",
                    "constraint_id": rule["constraint_id"],
                    "message": (
                        f"Unsupported constraint type: {constraint_type}"
                    ),
                })

        except ValueError as exc:
            issues.append({
                "code": "INVALID_CONSTRAINT_CONFIGURATION",
                "constraint_id": rule["constraint_id"],
                "message": str(exc),
            })

    return issues


# ---------------------------------------------------------------------
# Negative-scenario validation functions
# ---------------------------------------------------------------------


def validate_portfolio_weights(weights: dict) -> list[dict]:
    """Validate that portfolio allocation weights total 100%."""

    try:
        values = [D(value) for value in weights.values()]
    except Exception as exc:
        return [{
            "code": "INVALID_PORTFOLIO_WEIGHTS",
            "decision": "REJECT_INPUT",
            "message": f"Portfolio weights must be numeric: {exc}",
        }]

    if any(not value.is_finite() for value in values):
        return [{
            "code": "INVALID_PORTFOLIO_WEIGHTS",
            "decision": "REJECT_INPUT",
            "message": "Portfolio weights must be finite numbers",
        }]

    if any(value < ZERO or value > D("100") for value in values):
        return [{
            "code": "INVALID_PORTFOLIO_WEIGHTS",
            "decision": "REJECT_INPUT",
            "message": "Each portfolio weight must be between 0 and 100",
        }]

    total = sum(values, ZERO)

    if abs(total - D("100")) > D("0.000001"):
        return [{
            "code": "PORTFOLIO_WEIGHT_NOT_100",
            "decision": "REJECT_INPUT",
            "message": (
                f"Portfolio weights must total 100%; found {total}"
            ),
        }]

    return []


def validate_sell_quantity(
    available_quantity: Decimal,
    proposed_sell_quantity: Decimal,
) -> list[dict]:
    """Reject non-positive sells and sells exceeding available holdings."""

    if (
        not available_quantity.is_finite()
        or not proposed_sell_quantity.is_finite()
    ):
        return [{
            "code": "INVALID_SELL_QUANTITY",
            "decision": "REJECT_TRADE",
            "message": "Sell quantities must be finite numbers",
        }]

    if available_quantity < ZERO or proposed_sell_quantity <= ZERO:
        return [{
            "code": "INVALID_SELL_QUANTITY",
            "decision": "REJECT_TRADE",
            "message": "Sell quantity must be positive",
        }]

    if proposed_sell_quantity > available_quantity:
        return [{
            "code": "SELL_EXCEEDS_HOLDING",
            "decision": "REJECT_TRADE",
            "message": (
                "Proposed sell quantity exceeds available holding"
            ),
        }]

    return []


def validate_excluded_instrument(
    is_excluded: bool,
    recommended_side: str,
) -> list[dict]:
    """Reject a BUY or SELL recommendation for an excluded instrument."""

    side = recommended_side.upper()

    if is_excluded and side in ("BUY", "SELL"):
        return [{
            "code": "EXCLUDED_INSTRUMENT_RECOMMENDED",
            "decision": "REJECT_TRADE",
            "message": "Trading is prohibited for this instrument",
        }]

    return []


def validate_fee(
    fee_schedule_required: bool,
    fee_schedule_id: str | None,
    estimated_fee: Decimal | None,
) -> list[dict]:
    """Flag a missing fee schedule or missing estimated fee."""

    if fee_schedule_required and (
        not fee_schedule_id
        or estimated_fee is None
    ):
        return [{
            "code": "FEE_OMITTED",
            "decision": "REVIEW_REQUIRED",
            "message": (
                "Required fee schedule or estimated fee is missing"
            ),
        }]

    if estimated_fee is not None:
        if not estimated_fee.is_finite() or estimated_fee < ZERO:
            return [{
                "code": "INVALID_ESTIMATED_FEE",
                "decision": "REVIEW_REQUIRED",
                "message": "Estimated fee must be finite and non-negative",
            }]

    return []


def validate_price_freshness(
    price_age_days: int,
    is_stale: bool,
    max_price_age_days: int = 5,
) -> list[dict]:
    """Require stale prices to be explicitly flagged."""

    if price_age_days < 0:
        return [{
            "code": "INVALID_PRICE_AGE",
            "decision": "REVIEW_REQUIRED",
            "message": "Price age cannot be negative",
        }]

    if max_price_age_days < 0:
        raise ValueError("Maximum price age cannot be negative")

    if price_age_days > max_price_age_days and not is_stale:
        return [{
            "code": "STALE_PRICE_UNFLAGGED",
            "decision": "REVIEW_REQUIRED",
            "message": (
                "Price exceeds permitted age but is not flagged stale"
            ),
        }]

    return []