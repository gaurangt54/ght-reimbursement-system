import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ClaimsTable } from './ClaimsTable'

const base = {
  id: 7,
  title: 'Hotel - Bengaluru offsite',
  category: 'Accommodation',
  employee: { id: 2, name: 'Priya Nair' },
  reviewer: null,
  expense_date: '2026-10-20',
  amount: '12000.00',
  currency: 'INR',
  approved_amount: null,
  is_partial: false,
  status: 'SUBMITTED',
  resubmission_count: 0,
  updated_at: '2026-11-08T05:00:00Z',
  submitted_at: '2026-11-07T05:00:00Z',
}

function renderTable(claims, props = {}) {
  return render(
    <MemoryRouter>
      <ClaimsTable claims={claims} {...props} />
    </MemoryRouter>,
  )
}

const headers = () => screen.getAllByRole('columnheader').map((th) => th.textContent)

describe('ClaimsTable', () => {
  it('links each claim title to its detail page', () => {
    renderTable([base])
    expect(screen.getByRole('link', { name: base.title })).toHaveAttribute('href', '/claims/7')
    expect(screen.getByText('Submitted')).toBeInTheDocument()
  })

  it('shows a Partial badge and the approved amount for a partial approval', () => {
    renderTable([{ ...base, status: 'APPROVED', approved_amount: '10500.00', is_partial: true }])
    expect(screen.getByText('Partial')).toHaveClass('badge-warn')
    expect(screen.getByText('Approved ₹10,500.00')).toHaveClass('amount-partial')
  })

  it('shows no Partial badge for a full approval', () => {
    renderTable([{ ...base, status: 'APPROVED', approved_amount: '12000.00', is_partial: false }])
    expect(screen.queryByText('Partial')).not.toBeInTheDocument()
    expect(screen.getByText('Approved ₹12,000.00')).not.toHaveClass('amount-partial')
  })

  it('hides the optional columns by default', () => {
    renderTable([base])
    expect(headers()).toEqual(['#', 'Claim', 'Expense date', 'Amount', 'Status', 'Updated'])
    expect(screen.queryByText('Priya Nair')).not.toBeInTheDocument()
  })

  it('adds employee, reviewer, time and action columns when asked', () => {
    renderTable([{ ...base, reviewer: { id: 4, name: 'Neha Kapoor' } }, { ...base, id: 8 }], {
      showEmployee: true,
      showReviewer: true,
      timeColumn: 'submitted_at',
      actionLabel: 'Review',
    })
    expect(headers()).toEqual(['#', 'Claim', 'Employee', 'Expense date', 'Amount', 'Status', 'Reviewer', 'Submitted', ''])
    const [, first, second] = screen.getAllByRole('row')
    expect(within(first).getByText('Priya Nair')).toBeInTheDocument()
    expect(within(first).getByText('Neha Kapoor')).toBeInTheDocument()
    expect(within(second).getByText('-')).toBeInTheDocument() // no reviewer yet
    expect(within(second).getByRole('link', { name: 'Review' })).toHaveAttribute('href', '/claims/8')
  })

  it('notes how many times a claim was resubmitted', () => {
    renderTable([{ ...base, resubmission_count: 2 }])
    expect(screen.getByText('Resubmitted ×2')).toBeInTheDocument()
  })
})
