import { describe, expect, it } from 'vitest'
import { errorMessage } from './errors'
import { formatDate, formatMoney } from './format'

describe('formatMoney', () => {
  it('formats INR with Indian digit grouping and 2 decimals', () => {
    expect(formatMoney('8000')).toBe('₹8,000.00')
    expect(formatMoney('1234567.5')).toBe('₹12,34,567.50')
    expect(formatMoney(0)).toBe('₹0.00')
  })

  it('shows a dash for missing values', () => {
    expect(formatMoney(null)).toBe('-')
    expect(formatMoney(undefined)).toBe('-')
    expect(formatMoney('')).toBe('-')
  })

  it('supports other currencies', () => {
    expect(formatMoney('1000', 'USD')).toContain('1,000.00')
    expect(formatMoney('1000', 'USD')).not.toContain('₹')
  })
})

describe('formatDate', () => {
  it('formats a calendar date without shifting it across time zones', () => {
    expect(formatDate('2026-11-08')).toBe('8 Nov 2026')
    expect(formatDate('2026-01-01')).toBe('1 Jan 2026')
  })

  it('shows a dash for missing values', () => {
    expect(formatDate(null)).toBe('-')
    expect(formatDate('')).toBe('-')
  })
})

describe('errorMessage', () => {
  it('prefers the per-field messages over the generic one', () => {
    const err = { message: 'Please fix the highlighted fields.', fields: { amount: 'Too big.', title: 'Too short.' } }
    expect(errorMessage(err)).toBe('Too big. Too short.')
  })

  it('falls back to the message, then to a default', () => {
    expect(errorMessage({ message: 'Claim not found.', fields: {} })).toBe('Claim not found.')
    expect(errorMessage(null)).toBe('Something went wrong. Please try again.')
    expect(errorMessage(undefined)).toBe('Something went wrong. Please try again.')
  })
})
