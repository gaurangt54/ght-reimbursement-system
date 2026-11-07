"""Admin commands. Run from backend/ with the virtualenv active:

    python -m app.cli reset-db                 # drop everything, recreate, re-seed demo data
    python -m app.cli create-user --name "Asha Iyer" --email asha@example.com --role approver

Approvers can only be created here or by the seed (there is no self-service sign-up).
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from app import config
from app.database import Base, SessionLocal, engine
from app.models import APPROVER, EMPLOYEE, User
from app.security import hash_password, password_problem
from app.seed import init_db
from app.services.auth import normalize_email


def reset_db() -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:  # tables from older versions that the models no longer know
        conn.exec_driver_sql("DROP TABLE IF EXISTS sessions")
    init_db()
    seeded = "with demo data" if config.SEED_DEMO_DATA else "empty (SEED_DEMO_DATA is off)"
    print(f"Database reset: {seeded}.")


def create_user(name: str, email: str, role: str, password: str | None) -> None:
    init_db()
    email = normalize_email(email)
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            sys.exit("Passwords do not match.")
    problem = password_problem(password)
    if problem:
        sys.exit(problem)
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            sys.exit(f"A user with email {email} already exists.")
        db.add(User(name=name.strip(), email=email, role=role, password_hash=hash_password(password)))
        db.commit()
    print(f"Created {role} {name} <{email}>.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reset-db", help="Drop all tables, recreate them and re-seed demo data.")
    p = sub.add_parser("create-user", help="Create an employee or approver.")
    p.add_argument("--name", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--role", choices=[EMPLOYEE, APPROVER], default=EMPLOYEE)
    p.add_argument("--password", help="Omit to be prompted (keeps it out of shell history).")
    args = parser.parse_args(argv)
    if args.command == "reset-db":
        reset_db()
    else:
        create_user(args.name, args.email, args.role, args.password)


if __name__ == "__main__":
    main()
