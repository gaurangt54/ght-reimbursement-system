import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { useAuth } from './hooks/useAuth'
import { ROLES, homePathFor } from './lib/routes'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'

function HomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={homePathFor(user)} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<HomeRedirect />} />

          {/* Employee screens (Phase 7) */}
          <Route element={<ProtectedRoute roles={[ROLES.EMPLOYEE]} />}>
            <Route path="claims" element={<ComingSoonPage title="My claims" phase={7} />} />
            <Route path="claims/new" element={<ComingSoonPage title="New claim" phase={7} />} />
            <Route path="claims/:id/edit" element={<ComingSoonPage title="Edit claim" phase={7} />} />
          </Route>

          {/* Shared: both roles open a claim, and see different actions (Phases 7 and 8) */}
          <Route path="claims/:id" element={<ComingSoonPage title="Claim details" phase="7 and 8" />} />

          {/* Approver screens (Phase 8) */}
          <Route element={<ProtectedRoute roles={[ROLES.APPROVER]} />}>
            <Route path="review" element={<ComingSoonPage title="Pending review" phase={8} />} />
            <Route path="review/history" element={<ComingSoonPage title="Reviewed claims" phase={8} />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}