"""Periodic sweep: pending / verification_pending payments re-checked via TBC API."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.payment_flow import process_pay_id
from database.models import Payment, PaymentStatus

logger = logging.getLogger(__name__)


async def sweep_pending(session: AsyncSession) -> int:
    """Returns number of pay_ids processed (attempted)."""
    stmt = select(Payment.pay_id).where(
        Payment.status.in_((PaymentStatus.pending, PaymentStatus.verification_pending))
    )
    pay_ids = list((await session.execute(stmt)).scalars().all())
    n = 0
    for pid in pay_ids:
        try:
            await process_pay_id(session, pid)
            n += 1
        except Exception:
            logger.exception("Sweep failed for pay_id=%s", pid)
    return n
