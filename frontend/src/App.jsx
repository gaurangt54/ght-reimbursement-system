import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { useAuth } from './hooks/useAuth'
import { ROLES, homePathFor } from './lib/routes'
import { ClaimDetailPage } from './pages/ClaimDetailPage'
import { ClaimFormPage } from './pages/ClaimFormPage'
import { LoginPage } from './pages/LoginPage'
import { MyClaimsPage } from './pages/MyClaimsPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { ReviewedClaimsPage } from './pages/ReviewedClaimsPage'

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

          {/* Employee screens */}
          <Route element={<ProtectedRoute roles={[ROLES.EMPLOYEE]} />}>
            <Route path="claims" element={<MyClaimsPage />} />
            <Route path="claims/new" element={<ClaimFormPage />} />
            <Route path="claims/:id/edit" element={<ClaimFormPage />} />
          </Route>

          {/* Shared: both roles open a claim; the server decides which actions each may use */}
          <Route path="claims/:id" element={<ClaimDetailPage />} />

          {/* Approver screens */}
          <Route element={<ProtectedRoute roles={[ROLES.APPROVER]} />}>
            <Route path="review" element={<ReviewQueuePage />} />
            <Route path="review/history" element={<ReviewedClaimsPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}