"""Create tables and (when SEED_DEMO_DATA is on) demo users and claims on first run.

Demo users all share the documented demo password (config.DEMO_PASSWORD, default
"Password@123"). With SEED_DEMO_DATA off nobody is created: add users with the CLI
(`python -m app.cli create-user`).
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app import config
from app.database import Base, SessionLocal, engine
from app.models import APPROVER, EMPLOYEE, User
from app.schemas import ApproveIn, ClaimIn, PayIn, RejectIn
from app.security import hash_password
from app.services import claims as svc

DEMO_USERS = [
    ("Aarav Sharma", "aarav@napho.test", EMPLOYEE),
    ("Priya Nair", "priya@napho.test", EMPLOYEE),
    ("Rohan Mehta", "rohan@napho.test", EMPLOYEE),
    ("Neha Kapoor", "neha@napho.test", APPROVER),
    ("Vikram Rao", "vikram@napho.test", APPROVER),
]


def check_schema() -> None:
    """There are no migrations, so refuse to start on a database from an older version."""
    insp = inspect(engine)
    if insp.has_table("users"):
        columns = {c["name"] for c in insp.get_columns("users")}
        if "password_hash" not in columns or not insp.has_table("refresh_tokens"):
            raise RuntimeError(
                "The database was created by an older version of this app (no password columns). "
                "Run `python -m app.cli reset-db` in backend/ to recreate it."
            )


def init_db() -> None:
    check_schema()
    Base.metadata.create_all(engine)
    if not config.SEED_DEMO_DATA:
        return
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is None:
            create_demo_users(db)
            _seed_demo_claims(db)


def create_demo_users(db: Session, password: str | None = None) -> list[User]:
    # One hash shared by all demo users: hashing is deliberately slow.
    password_hash = hash_password(password or config.DEMO_PASSWORD)
    users = [User(name=n, email=e, role=r, password_hash=password_hash) for n, e, r in DEMO_USERS]
    db.add_all(users)
    db.commit()
    return users


def _claim(title, category, amount, days_ago, receipt="INV-0001", description=None) -> ClaimIn:
    return ClaimIn(title=title, category=category, amount=Decimal(amount), description=description,
                   expense_date=date.today() - timedelta(days=days_ago), receipt_ref=receipt)


def _seed_demo_claims(db: Session) -> None:
    by_name = {u.name: u for u in db.scalars(select(User))}
    aarav, priya = by_name["Aarav Sharma"], by_name["Priya Nair"]
    neha = by_name["Neha Kapoor"]

    svc.create_claim(db, aarav, _claim("Conference travel (draft)", "Travel", "4200", 3, receipt=None))

    c = svc.create_claim(db, aarav, _claim("Client lunch", "Meals", "8000", 5, "INV-2041",
                                           "Lunch with the Acme team"))
    svc.submit_claim(db, aarav, c.id)

    c = svc.create_claim(db, aarav, _claim("Design software licence", "Software", "2499", 12, "N/A"))
    svc.submit_claim(db, aarav, c.id)
    svc.reject_claim(db, neha, c.id, RejectIn(comment="Please provide the actual invoice number."))

    c = svc.create_claim(db, priya, _claim("Hotel - Bengaluru offsite", "Accommodation", "12000", 20, "HTL-889"))
    svc.submit_claim(db, priya, c.id)
    svc.approve_claim(db, neha, c.id, ApproveIn(approved_amount=Decimal("10500"),
                                                comment="Minibar charges not reimbursable."))

    c = svc.create_claim(db, priya, _claim("Airport taxi", "Travel", "950", 30, receipt=None))
    svc.submit_claim(db, priya, c.id)
    svc.approve_claim(db, neha, c.id, ApproveIn())
    svc.pay_claim(db, neha, c.id, PayIn(payment_reference="UTR-778812"))

    c = svc.create_claim(db, priya, _claim("Online course", "Training", "15000", 2, "UDM-3321"))
    svc.submit_claim(db, priya, c.id)