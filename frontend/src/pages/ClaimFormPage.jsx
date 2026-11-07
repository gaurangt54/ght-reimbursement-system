import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../api/api'
import { ClaimForm } from '../components/ClaimForm'
import { ErrorState } from '../components/ErrorState'
import { Spinner } from '../components/Spinner'
import { useApi } from '../hooks/useApi'

// Handles /claims/new and /claims/:id/edit. The form itself mounts only once its data
// is ready, so it can use that data as its initial state.
export function ClaimFormPage() {
  const { id } = useParams()
  const location = useLocation()
  const isEdit = Boolean(id)

  const meta = useApi(() => api.getMeta(), null)
  const claim = useApi((claimId, signal) => (claimId ? api.getClaim(claimId, signal) : Promise.resolve(null)), id ?? null)

  const error = meta.error ?? claim.error
  const ready = meta.data && (!isEdit || (claim.data && String(claim.data.id) === id))
  const editable = !isEdit || claim.data?.allowed_actions?.includes('edit')

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{isEdit ? `Edit claim #${id}` : 'New claim'}</h1>
          <p className="muted">
            {isEdit
              ? 'Update the details below.'
              : 'Save it as a draft, or submit it straight away.'}
          </p>
        </div>
      </div>

      {error && !ready && (
        <ErrorState
          error={error}
          onRetry={() => {
            meta.reload()
            claim.reload()
          }}
        />
      )}
      {!ready && !error && <Spinner />}

      {ready && !editable && (
        <div className="alert alert-warn">
          <p>This claim can no longer be edited because it is {claim.data.status.toLowerCase()}.</p>
          <Link className="btn btn-secondary btn-sm" to={`/claims/${id}`}>Back to the claim</Link>
        </div>
      )}

      {ready && editable && (
        <ClaimForm
          key={claim.data?.id ?? 'new'}
          meta={meta.data}
          claim={claim.data ?? undefined}
          initialError={location.state?.submitError}
        />
      )}
    </>
  )
}