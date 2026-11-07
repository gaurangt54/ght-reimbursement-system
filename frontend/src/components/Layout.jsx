import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { initials } from '../lib/format'
import { ROLES } from '../lib/routes'

const NAV = {
  [ROLES.EMPLOYEE]: [
    { to: '/claims', label: 'My claims', end: true },
    { to: '/claims/new', label: 'New claim' },
  ],
  [ROLES.APPROVER]: [
    { to: '/review', label: 'Pending review', end: true },
    { to: '/review/history', label: 'Reviewed claims' },
  ],
}

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <span className="brand">
            <span className="brand-mark" aria-hidden="true">₹</span>
            Reimbursements
          </span>
          <nav className="nav" aria-label="Main">
            {(NAV[user.role] ?? []).map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="user-chip">
            <span className="avatar" aria-hidden="true">{initials(user.name)}</span>
            <span className="user-meta">
              <strong>{user.name}</strong>
              <small>{user.role === ROLES.APPROVER ? 'Approver' : 'Employee'}</small>
            </span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </div>
  )
}