import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it.each([
    ['DRAFT', 'Draft', 'badge-neutral'],
    ['SUBMITTED', 'Submitted', 'badge-info'],
    ['APPROVED', 'Approved', 'badge-success'],
    ['REJECTED', 'Rejected', 'badge-danger'],
    ['PAID', 'Paid', 'badge-paid'],
  ])('shows %s as "%s" with the %s tone', (status, label, tone) => {
    render(<StatusBadge status={status} />)
    expect(screen.getByText(label)).toHaveClass('badge', tone)
  })

  it('falls back to the raw status in a neutral badge', () => {
    render(<StatusBadge status="ARCHIVED" />)
    expect(screen.getByText('ARCHIVED')).toHaveClass('badge-neutral')
  })
})
