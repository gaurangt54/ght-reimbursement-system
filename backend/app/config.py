"""Settings and business-policy constants (overridable via environment variables).

Values are read from the process environment, and from `backend/.env` if it exists
(see `.env.example`). Real environment variables win over the file.
"""
import logging
import os
import secrets
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

log = logging.getLogger("reimbursement")


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# "dev" (default), "test" or "prod". Anything other than "dev" requires a real JWT_SECRET.
APP_ENV = os.getenv("APP_ENV", "dev").strip().lower()

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'reimbursement.db'}")
CORS_ORIGINS = [o.strip() for o in
                os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
                if o.strip()]
# Demo users (with documented demo passwords) and demo claims are created on first run
# only when this is on.
SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", "true")

# ---- Authentication ----
MIN_JWT_SECRET_LENGTH = 32


def resolve_jwt_secret(app_env: str, secret: str | None) -> str:
    """Fail fast outside dev; in dev, fall back to a random per-process secret.

    A random dev secret means access tokens stop working when the server restarts. That is
    harmless: the frontend silently refreshes (refresh tokens live in the database).
    """
    secret = (secret or "").strip()
    if secret:
        if len(secret) < MIN_JWT_SECRET_LENGTH and app_env != "dev":
            raise RuntimeError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters.")
        return secret
    if app_env != "dev":
        raise RuntimeError(
            "JWT_SECRET is not set. Set it in the environment or backend/.env "
            "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )
    log.warning("JWT_SECRET is not set; using a random secret for this dev process.")
    return secrets.token_urlsafe(48)


JWT_SECRET = resolve_jwt_secret(APP_ENV, os.getenv("JWT_SECRET"))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
# A rotated refresh token presented again within this many seconds is treated as a benign race
# (two tabs, React StrictMode) rather than token theft.
REFRESH_REUSE_GRACE_SECONDS = int(os.getenv("REFRESH_REUSE_GRACE_SECONDS", "10"))
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"
COOKIE_SECURE = _bool("COOKIE_SECURE", "false")  # turn on whenever the site is served over HTTPS
# /refresh and /logout must carry this header (a simple CSRF guard; see DESIGN_DECISIONS.md).
CSRF_HEADER = "X-Requested-With"

# Passwords. bcrypt only looks at the first 72 bytes, so longer passwords are rejected
# instead of being silently truncated.
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
PASSWORD_MAX_BYTES = 72
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))  # tests lower this to stay fast

# Brute-force protection (in memory, per process).
LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))            # per email + IP
LOGIN_MAX_FAILURES_PER_IP = int(os.getenv("LOGIN_MAX_FAILURES_PER_IP", "20"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))      # failures counted over 15 min
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))    # then locked for 15 min

# Shared password for the seeded demo users (only when SEED_DEMO_DATA is on).
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Password@123")

# ---- Currency ----
DEFAULT_CURRENCY = "INR"
# Allowed currencies -> number of decimal places in their minor unit.
# Only INR is enabled; add e.g. "USD": 2, "JPY": 0 to enable more.
CURRENCY_DECIMALS = {"INR": 2}

# ---- Business policy (major units of DEFAULT_CURRENCY) ----
MAX_CLAIM_AMOUNT = Decimal(os.getenv("MAX_CLAIM_AMOUNT", "100000.00"))            # cap per claim
RECEIPT_REQUIRED_ABOVE = Decimal(os.getenv("RECEIPT_REQUIRED_ABOVE", "1000.00"))  # receipt needed above this
MAX_EXPENSE_AGE_DAYS = int(os.getenv("MAX_EXPENSE_AGE_DAYS", "90"))               # no claims for older expenses

CATEGORIES = ["Travel", "Meals", "Accommodation", "Office Supplies", "Software", "Training", "Other"]
