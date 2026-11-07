import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/api'
import { useAuth } from '../hooks/useAuth'
import { AuthProvider } from './AuthProvider'
import { ToastProvider } from './ToastProvider'

vi.mock('../api/api', () => ({ api: { refresh: vi.fn(), login: vi.fn(), logout: vi.fn() } }))

const NEHA = { id: 4, name: 'Neha Kapoor', role: 'approver' }
const AARAV = { id: 1, name: 'Aarav Sharma', role: 'employee' }
const session = (user) => ({ access_token: `token-${user.id}`, user })

function WhoAmI() {
  const { user, status } = useAuth()
  return <p data-testid="who">{status === 'authenticated' ? user.name : status}</p>
}

let otherTab
beforeEach(() => {
  otherTab = new BroadcastChannel('reimbursement-auth')
  vi.mocked(api.refresh).mockReset()
})
afterEach(() => otherTab.close())

async function renderSignedInAs(user) {
  vi.mocked(api.refresh).mockResolvedValueOnce(session(user))
  render(
    <ToastProvider>
      <AuthProvider>
        <WhoAmI />
      </AuthProvider>
    </ToastProvider>,
  )
  expect(await screen.findByText(user.name)).toBeInTheDocument()
}

describe('AuthProvider cross-tab sync', () => {
  it('switches to the user who signed in from another tab', async () => {
    await renderSignedInAs(NEHA)
    vi.mocked(api.refresh).mockResolvedValueOnce(session(AARAV))
    act(() => otherTab.postMessage({ type: 'login', userId: AARAV.id }))
    expect(await screen.findByText('Aarav Sharma')).toBeInTheDocument()
    expect(screen.getByText(/now signed in as Aarav Sharma \(from another tab\)/)).toBeInTheDocument()
  })

  it('ignores a sign-in by the same user', async () => {
    await renderSignedInAs(NEHA)
    act(() => otherTab.postMessage({ type: 'login', userId: NEHA.id }))
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(api.refresh).toHaveBeenCalledTimes(1) // only the restore on start
  })

  it('signs out when another tab signs out', async () => {
    await renderSignedInAs(NEHA)
    act(() => otherTab.postMessage({ type: 'logout' }))
    expect(await screen.findByText('anonymous')).toBeInTheDocument()
    expect(screen.getByText('You signed out in another tab.')).toBeInTheDocument()
  })
})
