"""Create tables and (optionally) demo users and claims on first run."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import Base, SessionLocal, engine
from app.models import APPROVER, EMPLOYEE, User
from app.schemas import ApproveIn, ClaimIn, PayIn, RejectIn
from app.services import claims as svc

USERS = [
    ("Aarav Sharma", "aarav@napho.test", EMPLOYEE),
    ("Priya Nair", "priya@napho.test", EMPLOYEE),
    ("Rohan Mehta", "rohan@napho.test", EMPLOYEE),
    ("Neha Kapoor", "neha@napho.test", APPROVER),
    ("Vikram Rao", "vikram@napho.test", APPROVER),
]


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is None:
            db.add_all(User(name=n, email=e, role=r) for n, e, r in USERS)
            db.commit()
            if config.SEED_DEMO_DATA:
                _seed_demo_claims(db)


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