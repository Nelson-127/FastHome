"""Request CRUD and user upsert."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Request as RentRequest
from database.models import RequestStatus, User


async def upsert_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    language: str,
    telegram_username: str | None,
) -> User:
    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user:
        user.language = language
        if telegram_username is not None:
            user.telegram_username = telegram_username
        await session.flush()
        return user

    user = User(
        telegram_id=telegram_id,
        language=language,
        telegram_username=telegram_username,
    )
    session.add(user)
    await session.flush()
    return user


async def create_request(
    session: AsyncSession,
    *,
    telegram_id: int,
    telegram_username: str | None,
    language: str,
    district: str,
    budget: float,
    rooms: str,
    term: str,
    move_in_date: str,
    contact: str,
    urgency: str,
) -> RentRequest:
    user = await upsert_user(
        session=session,
        telegram_id=telegram_id,
        language=language,
        telegram_username=telegram_username,
    )

    req = RentRequest(
        user_id=user.id,
        district=district,
        budget=Decimal(str(budget)),
        rooms=rooms,
        term=term,
        move_in_date=move_in_date,
        contact=contact,
        urgency=urgency,
        status=RequestStatus.waiting_payment,
    )

    session.add(req)
    await session.flush()
    await session.refresh(req)

    return req


async def get_request_by_id(session: AsyncSession, rid: int) -> RentRequest | None:
    stmt = select(RentRequest).where(RentRequest.id == rid)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_request_for_telegram(
    session: AsyncSession,
    rid: int,
    telegram_id: int,
) -> RentRequest | None:
    stmt = (
        select(RentRequest)
        .join(User, User.id == RentRequest.user_id)
        .where(
            RentRequest.id == rid,
            User.telegram_id == telegram_id,
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()