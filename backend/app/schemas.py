"""Request bodies. Pydantic validates shape and basic ranges here;
business rules (dates, limits, receipts) live in services/rules.py."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import config


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


def _blank_to_none(v):
    return v or None


class ClaimIn(_Base):
    """Used for both create and edit."""

    title: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    category: str
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    expense_date: date
    receipt_ref: str | None = Field(default=None, max_length=200)
    expected_version: int | None = None  # edits: reject if someone changed the claim meanwhile

    _clean = field_validator("description", "receipt_ref")(_blank_to_none)

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in config.CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(config.CATEGORIES)}")
        return v


class ActionIn(_Base):
    """Body for submit / withdraw / delete. `expected_version` is optional."""

    expected_version: int | None = None


class ApproveIn(ActionIn):
    approved_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    comment: str | None = Field(default=None, max_length=500)

    _clean = field_validator("comment")(_blank_to_none)


class RejectIn(ActionIn):
    comment: str = Field(min_length=3, max_length=500)


class PayIn(ActionIn):
    payment_reference: str | None = Field(default=None, max_length=64)

    _clean = field_validator("payment_reference")(_blank_to_none)


# ======================= Response bodies =======================

class UserOut(BaseModel):
    id: int
    name: str
    email: str | None = None
    role: str | None = None


class LoginIn(_Base):
    # Deliberately loose: a malformed email gets the same "incorrect email or password"
    # answer as a wrong one. Strict length caps just stop absurdly large bodies.
    email: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):  # no whitespace stripping: spaces are part of a password
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    """The refresh token is never in the body; it is only sent as an HttpOnly cookie."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut


class EventOut(BaseModel):
    id: int
    action: str
    from_status: str | None
    to_status: str | None
    comment: str | None
    details: dict | None
    created_at: datetime
    user: UserOut


class ClaimOut(BaseModel):
    id: int
    employee: UserOut
    title: str
    description: str | None
    category: str
    amount: Decimal
    currency: str
    expense_date: date
    receipt_ref: str | None
    status: str
    version: int
    approved_amount: Decimal | None
    is_partial: bool
    reviewer: UserOut | None
    review_comment: str | None
    reviewed_at: datetime | None
    paid_at: datetime | None
    payment_reference: str | None
    submitted_at: datetime | None
    resubmission_count: int
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[str]  # what the *current user* may do right now


class ClaimDetailOut(ClaimOut):
    events: list[EventOut]


class ClaimListOut(BaseModel):
    items: list[ClaimOut]
    total: int
    page: int
    page_size: int


class SummaryOut(BaseModel):
    currency: str
    counts: dict[str, int]
    total_claimed: Decimal
    pending_amount: Decimal    # waiting for approval
    approved_amount: Decimal   # approved (incl. paid)
    paid_amount: Decimal