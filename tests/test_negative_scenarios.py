from decimal import Decimal

from app.services.policy_service import (
    validate_portfolio_weights,
    validate_sell_quantity,
    validate_excluded_instrument,
    validate_fee,
    validate_price_freshness,
)


def test_anom_001_portfolio_weights_not_100():
    result = validate_portfolio_weights({
        "EQUITY": 60,
        "DEBT": 30,
        "GOLD": 10,
        "CASH": 5,
        "OTHER": 0,
    })

    assert result[0]["code"] == "PORTFOLIO_WEIGHT_NOT_100"
    assert result[0]["decision"] == "REJECT_INPUT"


def test_anom_002_sell_exceeds_holding():
    result = validate_sell_quantity(
        available_quantity=Decimal("10"),
        proposed_sell_quantity=Decimal("12"),
    )

    assert result[0]["code"] == "SELL_EXCEEDS_HOLDING"
    assert result[0]["decision"] == "REJECT_TRADE"


def test_anom_003_excluded_instrument_recommended():
    result = validate_excluded_instrument(
        is_excluded=True,
        recommended_side="BUY",
    )

    assert result[0]["code"] == "EXCLUDED_INSTRUMENT_RECOMMENDED"
    assert result[0]["decision"] == "REJECT_TRADE"


def test_anom_004_required_fee_omitted():
    result = validate_fee(
        fee_schedule_required=True,
        fee_schedule_id=None,
        estimated_fee=None,
    )

    assert result[0]["code"] == "FEE_OMITTED"
    assert result[0]["decision"] == "REVIEW_REQUIRED"


def test_anom_005_stale_price_not_flagged():
    result = validate_price_freshness(
        price_age_days=12,
        is_stale=False,
        max_price_age_days=5,
    )

    assert result[0]["code"] == "STALE_PRICE_UNFLAGGED"
    assert result[0]["decision"] == "REVIEW_REQUIRED"