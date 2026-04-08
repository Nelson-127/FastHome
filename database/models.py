"""SQLAlchemy ORM models."""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class RequestStatus(str, enum.Enum):
    new = "new"
    waiting_payment = "waiting_payment"
    paid = "paid"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class PaymentProvider(str, enum.Enum):
    tbc = "tbc"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    verification_pending = "verification_pending"


class ListingSource(str, enum.Enum):
    ss_ge = "ss.ge"
    myhome_ge = "myhome.ge"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    requests: Mapped[list["Request"]] = relationship(back_populates="user")


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (Index("ix_requests_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    district: Mapped[str] = mapped_column(Text)
    budget: Mapped[float] = mapped_column(Numeric(12, 2))
    rooms: Mapped[str] = mapped_column(String(64))
    term: Mapped[str] = mapped_column(Text)
    move_in_date: Mapped[str] = mapped_column(Text)
    contact: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(32))
    status: Mapped[RequestStatus] = mapped_column(
        SAEnum(RequestStatus, name="request_status", native_enum=False),
        default=RequestStatus.new,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="requests")
    payments: Mapped[list["Payment"]] = relationship(back_populates="request")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    provider: Mapped[PaymentProvider] = mapped_column(
        SAEnum(PaymentProvider, name="payment_provider", native_enum=False),
        default=PaymentProvider.tbc,
    )
    pay_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    approval_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status", native_enum=False),
        default=PaymentStatus.pending,
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped["Request"] = relationship(back_populates="payments")


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_url", "url", unique=True),
       # Index("ix_listings_price", "price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[ListingSource] = mapped_column(
        SAEnum(ListingSource, name="listing_source", native_enum=False),
    )
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    district: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, index=True)
    rooms: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class SentListing(Base):
    __tablename__ = "sent_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    listing_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id"),
    )