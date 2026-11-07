"""Settings and business-policy constants (overridable via environment variables)."""
import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'reimbursement.db'}")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "12"))

# ---- Currency ----
DEFAULT_CURRENCY = "INR"
# Allowed currencies -> number of decimal places in their minor unit.
# Only INR is enabled; add e.g. "USD": 2, "JPY": 0 to enable more.
CURRENCY_DECIMALS = {"INR": 2}

# ---- Business policy (major units of DEFAULT_CURRENCY) ----
MAX_CLAIM_AMOUNT = Decimal(os.getenv("MAX_CLAIM_AMOUNT", "100000.00"))            # cap per claim
RECEIPT_REQUIRED_ABOVE = Decimal(os.getenv("RECEIPT_REQUIRED_ABOVE", "1000.00"))  # receipt needed above this
MAX_EXPENSE_AGE_DAYS = int(os.getenv("MAX_EXPENSE_AGE_DAYS", "90"))               # no claims for older expenses