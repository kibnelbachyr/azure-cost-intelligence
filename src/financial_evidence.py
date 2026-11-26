"""Pure, credential-free helpers for bounded monetary evidence."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any


def currency_code(value: Any) -> str | None:
    # Syntax only; no currency registry or exchange-rate assumption.
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z]{3}", value.strip()):
        return value.strip().upper()
    return None


def amount_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        number = Decimal(str(value))
        # Bound inputs to representable, realistic magnitudes for JSON floats.
        if not number.is_finite() or abs(number) > Decimal("1e15"):
            return None
        return number
    except (InvalidOperation, ValueError, OverflowError):
        return None


def monthly_evidence(amount: Any, currency: Any) -> tuple[float | None, str | None]:
    number = amount_decimal(amount)
    code = currency_code(currency)
    if number is None or number < 0 or code is None:
        return None, None
    return float(number), code


def provider_savings(amount: Any, currency: Any) -> dict[str, Any]:
    """Advisor generic savingsAmount does not establish a monthly period."""
    number = amount_decimal(amount)
    code = currency_code(currency)
    return {
        "amount": float(number) if number is not None and number >= 0 else None,
        "currency": code,
        "period": "unknown",
        "source": "Azure Advisor extended_properties.savingsAmount",
    }


def validated_cost_rows(rows: list[dict[str, Any]]) -> tuple[Decimal | None, str | None, list[Decimal]]:
    """Reject ambiguous or mixed-currency actual-cost rows; never invent USD."""
    if not rows:
        return None, None, []
    codes = [currency_code(row.get("Currency")) for row in rows]
    if None in codes or len(set(codes)) != 1:
        raise ValueError("Cost rows require a single explicit currency.")
    amounts = [amount_decimal(row.get("Cost")) for row in rows]
    if any(number is None for number in amounts):
        raise ValueError("Cost rows contain missing or invalid monetary values.")
    # Negative actual costs (e.g. credits) are valid.
    total = sum(amounts, Decimal(0))
    if not math.isfinite(float(total)):
        raise ValueError("Cost total is not representable.")
    return total, codes[0], amounts


def savings_evidence_summary(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    """Count evidence, not savings: opportunities can overlap."""
    counts: dict[str, int] = {}
    unknown = 0
    for row in recommendations:
        amount, code = monthly_evidence(row.get("estimated_monthly_savings"), row.get("savings_currency"))
        if amount is None:
            unknown += 1
        else:
            counts[code] = counts.get(code, 0) + 1
    return {
        "known_monthly_estimate_count_by_currency": dict(sorted(counts.items())),
        "unknown_monthly_estimate_count": unknown,
        "aggregate_monthly_savings": None,
        "aggregation_reason": "Potential overlap, currency differences and unverified realization; no additive total.",
    }
