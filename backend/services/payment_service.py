"""Create TBC payment rows and invoke TBC client."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from database.models import Payment, PaymentProvider, PaymentStatus, Request as RentRequest, User
from payments.tbc.client import TBCClient

logger = logging.getLogger(__name__)


def _amount_for_urgency(urgency: str, settings) -> float:
    u = (urgency or "").lower()
    return float(settings.price_urgent_gel) if "urgent" in u else float(settings.price_normal_gel)


async def create_tbc_payment_for_request(
    session: AsyncSession,
    *,
    request_id: int,
    telegram_id: int,
) -> tuple[str, str, float]:
    """Returns (pay_id, approval_url, amount_gel)."""
    settings = get_settings()
    if not settings.tbc_enabled:
        raise ValueError("tbc_disabled")
    if not (
        settings.tbc_callback_url
        and settings.tbc_apikey
        and settings.tbc_client_id
        and settings.tbc_client_secret
    ):
        raise ValueError("tbc_not_configured")
    stmt = (
        select(RentRequest)
        .join(User, User.id == RentRequest.user_id)
        .where(RentRequest.id == request_id, User.telegram_id == telegram_id)
    )
    req = (await session.execute(stmt)).scalar_one_or_none()
    if not req:
        raise ValueError("request_not_found_or_forbidden")

    amount = _amount_for_urgency(req.urgency, settings)

    existing = await session.execute(
        select(Payment).where(Payment.request_id == request_id, Payment.status == PaymentStatus.pending)
    )
    pending = existing.scalar_one_or_none()
    if pending and pending.approval_url:
        logger.info("Reusing pending payment request_id=%s pay_id=%s", request_id, pending.pay_id)
        return pending.pay_id, pending.approval_url, float(pending.amount)
    if pending:
        logger.warning("Stale pending without approval_url request_id=%s", request_id)
        raise ValueError("payment_already_pending")

    client = TBCClient()
    merchant_id = str(req.id)
    desc = f"FastHome request #{req.id}"[:30]
    pay_id, approval_url = await client.create_payment(
        amount_gel=amount,
        return_url=settings.tbc_return_url,
        callback_url=settings.tbc_callback_url,
        description=desc,
        merchant_payment_id=merchant_id,
        language="EN",
        expiration_minutes=30,
    )

    pay = Payment(
        request_id=req.id,
        provider=PaymentProvider.tbc,
        pay_id=pay_id,
        approval_url=approval_url,
        status=PaymentStatus.pending,
        amount=Decimal(str(amount)),
    )
    session.add(pay)
    await session.commit()

    logger.info("Created TBC payment request_id=%s pay_id=%s amount=%s", req.id, pay_id, amount)
    return pay_id, approval_url, amount
