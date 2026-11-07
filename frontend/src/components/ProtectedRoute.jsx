import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { homePathFor } from '../lib/routes'
import { Spinner } from './Spinner'

// Wrap routes that need a logged-in user. Pass `roles` to restrict by role.
export function ProtectedRoute({ roles }) {
  const { user, status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Spinner label="Checking your session…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}