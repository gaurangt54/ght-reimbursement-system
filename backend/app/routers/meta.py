from fastapi import APIRouter

from app import config

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta")
def meta():
    """Config the frontend needs for form hints (the server still enforces everything)."""
    return {
        "categories": config.CATEGORIES,
        "currency": config.DEFAULT_CURRENCY,
        "max_claim_amount": str(config.MAX_CLAIM_AMOUNT),
        "receipt_required_above": str(config.RECEIPT_REQUIRED_ABOVE),
        "max_expense_age_days": config.MAX_EXPENSE_AGE_DAYS,
    }