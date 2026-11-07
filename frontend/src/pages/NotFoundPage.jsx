import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { homePathFor } from '../lib/routes'

export function NotFoundPage() {
  const { user } = useAuth()
  return (
    <div className="card empty">
      <h1>Page not found</h1>
      <p className="muted">The page you are looking for does not exist.</p>
      <Link className="btn btn-primary" to={homePathFor(user)}>
        Back to home
      </Link>
    </div>
  )
}