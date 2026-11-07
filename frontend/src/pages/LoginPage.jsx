import { useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/api'
import { Spinner } from '../components/Spinner'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { initials } from '../lib/format'
import { ROLES, homePathFor } from '../lib/routes'

export function LoginPage() {
  const { user, status, login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [users, setUsers] = useState([])
  const [loadState, setLoadState] = useState('loading') // loading | ready | error
  const [loadError, setLoadError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .listUsers()
      .then((list) => {
        if (cancelled) return
        setUsers(list)
        setLoadState('ready')
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err.message)
        setLoadState('error')
      })
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  if (status === 'authenticated' && user) return <Navigate to={homePathFor(user)} replace />

  function retry() {
    setLoadState('loading')
    setReloadKey((k) => k + 1)
  }

  async function handleLogin(chosen) {
    setBusyId(chosen.id)
    try {
      const loggedIn = await login(chosen.id)
      navigate(location.state?.from ?? homePathFor(loggedIn), { replace: true })
    } catch (err) {
      toast.error(err.message)
      setBusyId(null)
    }
  }

  const groups = [
    { role: ROLES.EMPLOYEE, title: 'Employees', hint: 'Create and submit expense claims' },
    { role: ROLES.APPROVER, title: 'Approvers', hint: 'Review, approve or reject claims, mark as paid' },
  ]

  return (
    <div className="login-page">
      <div className="login-card card">
        <div className="login-head">
          <span className="brand-mark brand-mark-lg" aria-hidden="true">₹</span>
          <h1>Reimbursement Management</h1>
          <p className="muted">Demo login: pick a user to continue. There are no passwords.</p>
        </div>

        {loadState === 'loading' && <Spinner label="Loading users…" />}

        {loadState === 'error' && (
          <div className="alert alert-error" role="alert">
            <p>{loadError}</p>
            <button type="button" className="btn btn-secondary btn-sm" onClick={retry}>
              Try again
            </button>
          </div>
        )}

        {loadState === 'ready' &&
          groups.map((group) => (
            <section key={group.role} className="login-group">
              <h2>{group.title}</h2>
              <p className="muted small">{group.hint}</p>
              <ul className="user-list">
                {users
                  .filter((u) => u.role === group.role)
                  .map((u) => (
                    <li key={u.id}>
                      <button
                        type="button"
                        className="user-option"
                        disabled={busyId !== null}
                        onClick={() => handleLogin(u)}
                      >
                        <span className="avatar" aria-hidden="true">{initials(u.name)}</span>
                        <span className="user-option-text">
                          <strong>{u.name}</strong>
                          <small>{u.email}</small>
                        </span>
                        {busyId === u.id && <span className="spinner spinner-sm" aria-label="Signing in" />}
                      </button>
                    </li>
                  ))}
              </ul>
            </section>
          ))}
      </div>
    </div>
  )
}