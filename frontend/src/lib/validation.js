// Client-side checks that mirror the backend rules, purely for instant feedback.
// The server still enforces everything (and is the source of truth).
import { formatMoney, todayIso } from './format'

const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/

function daysBetween(isoFrom, isoTo) {
  const [fy, fm, fd] = isoFrom.split('-').map(Number)
  const [ty, tm, td] = isoTo.split('-').map(Number)
  return Math.round((new Date(ty, tm - 1, td) - new Date(fy, fm - 1, fd)) / 86400000)
}

export function validateClaim(values, meta, { forSubmit = false } = {}) {
  const errors = {}

  const title = values.title.trim()
  if (title.length < 3) errors.title = 'Title must be at least 3 characters.'
  else if (title.length > 120) errors.title = 'Title can be at most 120 characters.'

  if (!values.category) errors.category = 'Choose a category.'

  const amountText = values.amount.trim()
  if (!amountText) {
    errors.amount = 'Enter the amount.'
  } else if (!AMOUNT_PATTERN.test(amountText)) {
    errors.amount = 'Enter a valid amount with at most 2 decimal places.'
  } else {
    const amount = Number(amountText)
    if (amount <= 0) errors.amount = 'Amount must be greater than zero.'
    else if (amount > Number(meta.max_claim_amount)) {
      errors.amount = `Amount cannot exceed ${formatMoney(meta.max_claim_amount)} per claim.`
    } else if (forSubmit && amount > Number(meta.receipt_required_above) && !values.receipt_ref.trim()) {
      errors.receipt_ref = `A receipt reference is required for claims above ${formatMoney(meta.receipt_required_above)}.`
    }
  }

  if (!values.expense_date) {
    errors.expense_date = 'Choose the expense date.'
  } else if (values.expense_date > todayIso()) {
    errors.expense_date = 'Expense date cannot be in the future.'
  } else if (daysBetween(values.expense_date, todayIso()) > meta.max_expense_age_days) {
    errors.expense_date = `Expenses older than ${meta.max_expense_age_days} days cannot be claimed.`
  }

  if (values.description.length > 1000) errors.description = 'Description can be at most 1000 characters.'
  return errors
}