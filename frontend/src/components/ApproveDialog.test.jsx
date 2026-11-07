import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/api'
import { ApiError } from '../api/client'
import { ApproveDialog } from './ReviewDialogs'

vi.mock('../api/api', () => ({ api: { approveClaim: vi.fn() } }))

const claim = {
  id: 2,
  title: 'Client lunch',
  category: 'Meals',
  amount: '8000.00',
  currency: 'INR',
  version: 3,
  employee: { id: 1, name: 'Aarav Sharma' },
}

function setup() {
  const props = { onClose: vi.fn(), onDone: vi.fn(), onConflict: vi.fn() }
  render(<ApproveDialog claim={claim} {...props} />)
  return { user: userEvent.setup(), amount: screen.getByLabelText(/Amount to approve/), ...props }
}

beforeEach(() => {
  vi.mocked(api.approveClaim).mockReset() // braces matter: a function returned from beforeEach runs as teardown
})

describe('ApproveDialog', () => {
  it('starts as a full approval with an optional comment', () => {
    setup()
    expect(screen.getByLabelText(/Amount to approve/)).toHaveValue('8000.00')
    expect(screen.getByLabelText('Comment (optional)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve in full' })).toBeInTheDocument()
    expect(screen.queryByText(/Partial approval/)).not.toBeInTheDocument()
  })

  it('warns live as the amount is lowered, and makes the comment required', async () => {
    const { user, amount } = setup()
    await user.clear(amount)
    await user.type(amount, '6500')
    expect(screen.getByText(/Partial approval/)).toHaveTextContent('₹1,500.00 of this claim will not be reimbursed')
    expect(screen.getByLabelText('Comment *')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve partially' })).toBeInTheDocument()

    await user.clear(amount)
    await user.type(amount, '8000')
    expect(screen.queryByText(/Partial approval/)).not.toBeInTheDocument()
  })

  it('blocks a partial approval without a comment', async () => {
    const { user, amount } = setup()
    await user.clear(amount)
    await user.type(amount, '6500')
    await user.click(screen.getByRole('button', { name: 'Approve partially' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/comment explaining the reduction is required/)
    expect(api.approveClaim).not.toHaveBeenCalled()
  })

  it('sends the reduced amount, the comment and the version it saw', async () => {
    const updated = { ...claim, status: 'APPROVED' }
    vi.mocked(api.approveClaim).mockResolvedValue(updated)
    const { user, amount, onDone } = setup()
    await user.clear(amount)
    await user.type(amount, '6500')
    await user.type(screen.getByLabelText('Comment *'), 'Alcohol is not reimbursable')
    await user.click(screen.getByRole('button', { name: 'Approve partially' }))
    expect(api.approveClaim).toHaveBeenCalledWith(2, {
      approvedAmount: '6500',
      comment: 'Alcohol is not reimbursable',
      version: 3,
    })
    expect(onDone).toHaveBeenCalledWith(updated)
  })

  it('leaves the amount out for a full approval', async () => {
    vi.mocked(api.approveClaim).mockResolvedValue(claim)
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Approve in full' }))
    expect(api.approveClaim).toHaveBeenCalledWith(2, { approvedAmount: undefined, comment: undefined, version: 3 })
  })

  it('refuses more than the claimed amount', async () => {
    const { user, amount } = setup()
    await user.clear(amount)
    await user.type(amount, '9000')
    await user.click(screen.getByRole('button', { name: 'Approve in full' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/cannot exceed the claimed amount/)
    expect(api.approveClaim).not.toHaveBeenCalled()
  })

  it('reports a conflict when someone else acted first', async () => {
    const conflict = new ApiError({ status: 409, code: 'STALE_VERSION', message: 'This claim was changed by someone else.' })
    vi.mocked(api.approveClaim).mockImplementation(async () => {
      throw conflict
    })
    const { user, onConflict, onDone } = setup()
    await user.click(screen.getByRole('button', { name: 'Approve in full' }))
    expect(onConflict).toHaveBeenCalledWith('This claim was changed by someone else.')
    expect(onDone).not.toHaveBeenCalled()
  })
})
