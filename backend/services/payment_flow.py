"""Orchestration: confirm TBC payment using API truth + DB updates + notifications."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import get_settings
from database.models import Payment, PaymentStatus, Request as RentRequest, RequestStatus
from payments.tbc.client import TBCClient
from payments.tbc.service import ParsedTbcPayment, fetch_payment_with_retries, parse_tbc_payload, validate_success

from backend.services.notify_service import notify_admins, notify_payment_success_for_user

logger = logging.getLogger(__name__)

MAX_VARIANTS = 5


def urgency_hours(urgency: str) -> int:
    return 24 if "urgent" in (urgency or "").lower() else 48


async def process_pay_id(session: AsyncSession, pay_id: str) -> dict[str, str]:
    if not get_settings().tbc_enabled:
        logger.info("TBC disabled: skip verification for pay_id=%s", pay_id)
        return {"status": "tbc_disabled"}
    stmt = (
        select(Payment)
        .options(selectinload(Payment.request).selectinload(RentRequest.user))
        .where(Payment.pay_id == pay_id)
    )
    payment = (await session.execute(stmt)).scalar_one_or_none()
    if not payment:
        logger.warning("Unknown pay_id=%s", pay_id)
        return {"status": "ignored"}

    if payment.status == PaymentStatus.paid:
        return {"status": "already_paid"}

    req = payment.request
    if not req:
        return {"status": "error"}

    user = req.user
    expected_amount = Decimal(str(payment.amount))
    client = TBCClient()

    try:
        remote = await fetch_payment_with_retries(client, pay_id)
    except Exception:
        logger.exception("TBC fetch failed pay_id=%s", pay_id)
        payment.status = PaymentStatus.verification_pending
        await session.commit()
        return {"status": "verification_pending"}

    parsed: ParsedTbcPayment = parse_tbc_payload(remote)
    st = (parsed.status or "").strip()
    st_l = st.lower()
    if st_l != "succeeded":
        if st_l in ("failed", "cancelled", "declined", "rejected"):
            payment.status = PaymentStatus.failed
            await session.commit()
            logger.info("Payment terminal non-success pay_id=%s status=%s", pay_id, st)
            return {"status": "failed_remote"}
        logger.info("Payment not completed yet pay_id=%s status=%s", pay_id, st or "(empty)")
        return {"status": "still_pending"}

    ok, reason = validate_success(
        parsed,
        expected_amount_gel=expected_amount,
        expected_request_id=req.id,
    )
    if not ok:
        logger.error("Verify failed pay_id=%s reason=%s", pay_id, reason)
        return {"status": "rejected", "reason": reason}

    payment.status = PaymentStatus.paid
    req.status = RequestStatus.paid
    await session.commit()

    if user:
        await notify_payment_success_for_user(
            user,
            req.id,
            max_variants=MAX_VARIANTS,
            hours=urgency_hours(req.urgency),
        )
    await notify_admins(
        f"✅ <b>Оплата подтверждена (TBC)</b>\nЗаявка #{req.id} оплачена автоматически.",
    )

    return {"status": "ok"}
