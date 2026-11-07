import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Field } from '../components/Field'
import { Spinner } from '../components/Spinner'
import { useAuth } from '../hooks/useAuth'
import { homePathFor } from '../lib/routes'

// Seeded demo accounts (backend SEED_DEMO_DATA). Shown only in development builds.
const DEMO_PASSWORD = 'Password@123'
const DEMO_ACCOUNTS = [
  { email: 'aarav@napho.test', label: 'Aarav · employee' },
  { email: 'priya@napho.test', label: 'Priya · employee' },
  { email: 'neha@napho.test', label: 'Neha · approver' },
  { email: 'vikram@napho.test', label: 'Vikram · approver' },
]

// Only same-app paths: never redirect to another site, or back to the login page.
function safeFrom(from) {
  if (typeof from !== 'string' || !from.startsWith('/') || from.startsWith('//')) return null
  return from.startsWith('/login') ? null : from
}

export function LoginPage() {
  const { user, status, login } = useAuth()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)

  if (status === 'loading') return <Spinner label="Checking your session…" />
  if (status === 'authenticated' && user) {
    // Back to the page they were trying to open, or their home screen.
    return <Navigate to={safeFrom(location.state?.from) ?? homePathFor(user)} replace />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const found = {}
    if (!email.trim()) found.email = 'Enter your email.'
    if (!password) found.password = 'Enter your password.'
    setErrors(found)
    setFormError('')
    if (Object.keys(found).length > 0) return

    setBusy(true)
    try {
      await login(email.trim(), password) // on success the <Navigate> above takes over
    } catch (err) {
      setFormError(err.message)
      setPassword('')
      setBusy(false)
    }
  }

  function fillDemo(account) {
    setEmail(account.email)
    setPassword(DEMO_PASSWORD)
    setErrors({})
    setFormError('')
  }

  return (
    <div className="login-page">
      <div className="login-card card">
        <div className="login-head">
          <span className="brand-mark brand-mark-lg" aria-hidden="true">₹</span>
          <h1>Reimbursement Management</h1>
          <p className="muted">Sign in to continue.</p>
        </div>

        <form className="login-form" noValidate onSubmit={handleSubmit}>
          {formError && (
            <div className="alert alert-error" role="alert">
              <p>{formError}</p>
            </div>
          )}

          <Field label="Email" name="email" error={errors.email}>
            <input
              id="email"
              type="email"
              className="input"
              autoComplete="username"
              autoFocus
              value={email}
              disabled={busy}
              aria-invalid={errors.email ? true : undefined}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>

          <Field label="Password" name="password" error={errors.password}>
            <input
              id="password"
              type="password"
              className="input"
              autoComplete="current-password"
              value={password}
              disabled={busy}
              aria-invalid={errors.password ? true : undefined}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {import.meta.env.DEV && (
          <div className="demo-hint">
            <p className="muted small">
              Demo accounts (dev only). Password for all: <code>{DEMO_PASSWORD}</code>
            </p>
            <div className="demo-accounts">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={busy}
                  onClick={() => fillDemo(account)}
                >
                  {account.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
