import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { homePathFor } from '../lib/routes'
import { Spinner } from './Spinner'

// Wrap routes that need a logged-in user. Pass `roles` to restrict by role.
// While the session is being restored on app start it shows a spinner instead of
// flashing the login page.
export function ProtectedRoute({ roles }) {
  const { user, status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Spinner label="Checking your session…" />
  if (!user) {
    const from = `${location.pathname}${location.search}`
    return <Navigate to="/login" replace state={{ from }} />
  }
  if (roles && !roles.includes(user.role)) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}
