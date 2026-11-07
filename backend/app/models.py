"""Database models.

Money is a Decimal in Python, stored as a rounded REAL in SQLite via the Money type.
`claim_events` is an append-only audit log: every create, edit or status change
writes one row in the same transaction as the change itself.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, TypeDecorator, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UTCDateTime(TypeDecorator):
    """SQLite drops timezone info; store UTC and always return aware datetimes."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class Money(TypeDecorator):
    """Decimal in Python, REAL in SQLite. Always returned as an exact 2-decimal Decimal."""

    impl = Float
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else float(Decimal(value).quantize(Decimal("0.01")))

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(str(round(value, 2))).quantize(Decimal("0.01"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Roles
EMPLOYEE = "employee"
APPROVER = "approver"

# Claim statuses
DRAFT = "DRAFT"
SUBMITTED = "SUBMITTED"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
PAID = "PAID"
STATUSES = (DRAFT, SUBMITTED, APPROVED, REJECTED, PAID)
# Statuses where a claim "occupies" its fingerprint (duplicate detection)
ACTIVE_STATUSES = (SUBMITTED, APPROVED, PAID)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    role: Mapped[str] = mapped_column(String(20))


class AuthSession(Base):
    """Mocked login: choosing a user issues an opaque bearer token."""

    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship()


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # What the employee fills in
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Money)  # what the employee claimed
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    expense_date: Mapped[date] = mapped_column(Date)
    receipt_ref: Mapped[str | None] = mapped_column(String(200))

    # Workflow state
    status: Mapped[str] = mapped_column(String(20), default=DRAFT, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic locking, bumped on every change
    fingerprint: Mapped[str] = mapped_column(String(300))     # currency|category|amount|date|title

    # Review and payment outcome (review fields are cleared when a rejected claim is
    # resubmitted; the full history stays in claim_events)
    approved_amount: Mapped[Decimal | None] = mapped_column(Money)  # what the approver approved
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    paid_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    payment_reference: Mapped[str | None] = mapped_column(String(64))

    # Bookkeeping
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resubmission_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # soft delete (drafts)

    employee: Mapped[User] = relationship(foreign_keys=[employee_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])
    events: Mapped[list["ClaimEvent"]] = relationship(
        back_populates="claim", order_by="ClaimEvent.id", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # DB-level duplicate guard: one live (submitted/approved/paid) claim per
        # employee per fingerprint. Holds even under concurrent submits.
        Index(
            "uq_claim_live_fingerprint",
            "employee_id",
            "fingerprint",
            unique=True,
            sqlite_where=text("status IN ('SUBMITTED','APPROVED','PAID') AND deleted_at IS NULL"),
        ),
    )


class ClaimEvent(Base):
    """Append-only audit trail: one row per create, edit or status change."""

    __tablename__ = "claim_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    claim: Mapped[Claim] = relationship(back_populates="events")
    user: Mapped[User] = relationship()