"""Pydantic schemas for housing requests."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class RequestStatusApi(str, Enum):
    new = "new"
    waiting_payment = "waiting_payment"
    paid = "paid"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class RequestCreate(BaseModel):
    telegram_id: int = Field(..., ge=1)
    telegram_username: str | None = Field(default=None, max_length=255)
    language: str = Field(default="ru", min_length=2, max_length=8)
    district: str = Field(..., min_length=1, max_length=2000)
    budget: float = Field(..., ge=1, le=1_000_000)
    rooms: str = Field(..., min_length=1, max_length=64)
    term: str = Field(..., min_length=1, max_length=2000)
    move_in_date: str = Field(..., min_length=1, max_length=500)
    contact: str = Field(..., min_length=3, max_length=2000)
    urgency: str = Field(..., min_length=1, max_length=32)

    @field_validator("language")
    @classmethod
    def lang_lower(cls, v: str) -> str:
        return v.lower()


class RequestOut(BaseModel):
    id: int
    user_id: int
    district: str
    budget: float
    rooms: str
    term: str
    move_in_date: str
    contact: str
    urgency: str
    status: RequestStatusApi
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("budget", mode="before")
    @classmethod
    def _budget_float(cls, v: object) -> float:
        return float(v)  # Decimal from DB

    @field_validator("status", mode="before")
    @classmethod
    def _status_api(cls, v: object) -> RequestStatusApi:
        if isinstance(v, RequestStatusApi):
            return v
        val = getattr(v, "value", v)
        return RequestStatusApi(str(val))


class PaymentCreateBody(BaseModel):
    request_id: int = Field(..., ge=1)
    telegram_id: int = Field(..., ge=1)


class PaymentCreateResponse(BaseModel):
    pay_id: str
    approval_url: str
    amount_gel: float


class AdminRequestPatch(BaseModel):
    status: RequestStatusApi | None = None


class AdminRequestOut(RequestOut):
    telegram_id: int | None = None

    model_config = {"from_attributes": True}
