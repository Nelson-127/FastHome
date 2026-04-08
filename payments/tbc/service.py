"""TBC payment verification: API is source of truth; webhook is only a trigger."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from payments.tbc.client import TBCClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedTbcPayment:
    status: str
    amount_total: Decimal | None
    merchant_payment_id: str | None
    currency: str | None
    raw: dict[str, Any]


def _decimal_amount(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def parse_tbc_payload(payload: dict[str, Any]) -> ParsedTbcPayment:
    """Normalize TBC payment JSON (field names may vary slightly by API version)."""
    status = str(payload.get("status") or payload.get("paymentStatus") or "").strip()
    merchant_payment_id = payload.get("merchantPaymentId")
    if merchant_payment_id is not None:
        merchant_payment_id = str(merchant_payment_id).strip()

    amount_block = payload.get("amount") or {}
    if isinstance(amount_block, dict):
        total = amount_block.get("total") or amount_block.get("Total")
        currency = amount_block.get("currency") or amount_block.get("Currency")
    else:
        total = payload.get("totalAmount") or payload.get("amountTotal")
        currency = payload.get("currency")

    amt = _decimal_amount(total)
    cur = str(currency).strip() if currency else None

    return ParsedTbcPayment(
        status=status,
        amount_total=amt,
        merchant_payment_id=merchant_payment_id or None,
        currency=cur,
        raw=payload,
    )


def amounts_equal(a: Decimal, b: Decimal, *, tol: Decimal = Decimal("0.01")) -> bool:
    return abs(a - b) <= tol


async def fetch_payment_with_retries(
    client: TBCClient,
    pay_id: str,
    *,
    max_attempts: int = 5,
    base_delay_sec: float = 0.5,
) -> dict[str, Any]:
    """Fetch payment from TBC with exponential backoff on transport/API errors."""
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await client.get_payment(pay_id)
        except Exception as e:
            last_err = e
            delay = base_delay_sec * (2 ** (attempt - 1))
            logger.warning("TBC get_payment failed attempt %s/%s: %s", attempt, max_attempts, e)
            if attempt < max_attempts:
                await asyncio.sleep(delay)
    assert last_err is not None
    raise last_err


def validate_success(
    parsed: ParsedTbcPayment,
    *,
    expected_amount_gel: Decimal,
    expected_request_id: int,
) -> tuple[bool, str]:
    """
    Returns (ok, reason). Does not trust webhook body — use payload from get_payment only.
    merchantPaymentId must match our request id (string).
    """
    if (parsed.status or "").strip().lower() != "succeeded":
        return False, f"status_not_succeeded:{parsed.status}"

    if parsed.amount_total is None:
        return False, "missing_amount"

    if not amounts_equal(parsed.amount_total, expected_amount_gel):
        return False, f"amount_mismatch:got={parsed.amount_total} expected={expected_amount_gel}"

    if str(expected_request_id) != (parsed.merchant_payment_id or ""):
        return False, f"merchant_id_mismatch:got={parsed.merchant_payment_id!r}"

    if parsed.currency and parsed.currency.upper() != "GEL":
        return False, f"currency_mismatch:{parsed.currency}"

    return True, "ok"
