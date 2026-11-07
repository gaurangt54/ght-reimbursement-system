import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { validateApproval, validateClaim, validateRejection } from './validation'

const META = { max_claim_amount: '100000.00', receipt_required_above: '1000.00', max_expense_age_days: 90 }

const claim = (overrides = {}) => ({
  title: 'Client lunch',
  category: 'Meals',
  amount: '800.00',
  expense_date: '2026-11-01',
  receipt_ref: '',
  description: '',
  ...overrides,
})

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 10, 8, 12, 0, 0)) // 8 Nov 2026, local time
})
afterEach(() => vi.useRealTimers())

describe('validateClaim', () => {
  it('accepts a valid claim', () => {
    expect(validateClaim(claim(), META)).toEqual({})
  })

  it('requires a title of 3-120 characters (after trimming)', () => {
    expect(validateClaim(claim({ title: '  ab  ' }), META).title).toMatch(/at least 3/)
    expect(validateClaim(claim({ title: 'x'.repeat(121) }), META).title).toMatch(/at most 120/)
  })

  it('requires a category', () => {
    expect(validateClaim(claim({ category: '' }), META).category).toBe('Choose a category.')
  })

  it.each([
    ['', 'Enter the amount.'],
    ['abc', /valid amount/],
    ['10.123', /at most 2 decimal/],
    ['-5', /valid amount/],
    ['0', /greater than zero/],
    ['100000.01', /cannot exceed/],
  ])('rejects amount %j', (amount, message) => {
    expect(validateClaim(claim({ amount }), META).amount).toMatch(message)
  })

  it('only requires a receipt above the threshold, and only when submitting', () => {
    const big = claim({ amount: '1000.01' })
    expect(validateClaim(big, META)).toEqual({}) // saving a draft is fine
    expect(validateClaim(big, META, { forSubmit: true }).receipt_ref).toMatch(/receipt reference is required/)
    expect(validateClaim(claim({ amount: '1000.00' }), META, { forSubmit: true })).toEqual({})
    expect(validateClaim({ ...big, receipt_ref: 'INV-1' }, META, { forSubmit: true })).toEqual({})
  })

  it('rejects future dates and dates older than the policy window', () => {
    expect(validateClaim(claim({ expense_date: '' }), META).expense_date).toBe('Choose the expense date.')
    expect(validateClaim(claim({ expense_date: '2026-11-09' }), META).expense_date).toMatch(/future/)
    expect(validateClaim(claim({ expense_date: '2026-08-10' }), META)).toEqual({}) // exactly 90 days
    expect(validateClaim(claim({ expense_date: '2026-08-09' }), META).expense_date).toMatch(/older than 90/)
  })

  it('limits the description length', () => {
    expect(validateClaim(claim({ description: 'x'.repeat(1001) }), META).description).toMatch(/1000/)
  })
})

describe('validateApproval', () => {
  const reviewed = { amount: '8000.00', currency: 'INR' }

  it('accepts a full approval without a comment', () => {
    expect(validateApproval({ amount: '8000.00', comment: '' }, reviewed)).toEqual({})
  })

  it('requires a comment for a partial approval', () => {
    expect(validateApproval({ amount: '6500', comment: '  ' }, reviewed).comment).toMatch(/comment explaining/)
    expect(validateApproval({ amount: '6500', comment: 'Minibar not covered' }, reviewed)).toEqual({})
  })

  it.each([
    ['', /Enter the amount/],
    ['6,500', /valid amount/],
    ['0', /greater than zero/],
    ['8000.01', /cannot exceed the claimed amount/],
  ])('rejects approved amount %j', (amount, message) => {
    expect(validateApproval({ amount, comment: 'x' }, reviewed).approved_amount).toMatch(message)
  })
})

describe('validateRejection', () => {
  it('requires a reason of at least 3 characters', () => {
    expect(validateRejection({ comment: ' no ' }).comment).toMatch(/at least 3/)
    expect(validateRejection({ comment: 'Wrong invoice' })).toEqual({})
  })
})
