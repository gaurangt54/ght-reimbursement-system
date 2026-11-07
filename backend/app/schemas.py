"""Request bodies. Pydantic validates shape and basic ranges here;
business rules (dates, limits, receipts) live in services/rules.py."""
from datetime import date
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