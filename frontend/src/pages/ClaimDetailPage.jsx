import { Link, useParams } from 'react-router-dom'
import { api } from '../api/api'
import { EmployeeActions } from '../components/EmployeeActions'
import { ErrorState } from '../components/ErrorState'
import { Spinner } from '../components/Spinner'
import { StatusBadge } from '../components/StatusBadge'
import { Timeline } from '../components/Timeline'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { formatDate, formatDateTime, formatMoney } from '../lib/format'
import { ROLES } from '../lib/routes'

export function ClaimDetailPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const { data: claim, error, reload, mutate } = useApi((claimId, signal) => api.getClaim(claimId, signal), id)

  const backTo = user.role === ROLES.APPROVER ? '/review' : '/claims'

  if (error && !claim) {
    return (
      <div className="stack">
        <Link to={backTo}>← Back</Link>
        {error.status === 404 ? (
          <div className="card empty">
            <h1>Claim not found</h1>
            <p className="muted">It may have been deleted, or you may not have access to it.</p>
          </div>
        ) : (
          <ErrorState error={error} onRetry={reload} />
        )}
      </div>
    )
  }
  if (!claim || String(claim.id) !== id) return <Spinner label="Loading claim…" />

  const cur = claim.currency
  const notApproved = claim.is_partial ? Number(claim.amount) - Number(claim.approved_amount) : 0

  return (
    <div className="stack">
      <Link to={backTo}>← Back to claims</Link>

      <div className="page-head">
        <div>
          <h1>{claim.title}</h1>
          <div className="row">
            <StatusBadge status={claim.status} />
            {claim.is_partial && <span className="badge badge-warn">Partial approval</span>}
            <span className="muted small">Claim #{claim.id}</span>
            {claim.resubmission_count > 0 && (
              <span className="muted small">Resubmitted ×{claim.resubmission_count}</span>
            )}
          </div>
        </div>
        <EmployeeActions claim={claim} onChanged={(updated) => (updated ? mutate(updated) : reload())} />
      </div>

      {claim.status === 'REJECTED' && (
        <div className="alert alert-error">
          <p>
            <strong>Rejected{claim.reviewer ? ` by ${claim.reviewer.name}` : ''}:</strong>{' '}
            “{claim.review_comment}”
          </p>
          {claim.allowed_actions.includes('edit') && <p>Correct the claim and resubmit it.</p>}
        </div>
      )}
      {claim.status === 'APPROVED' && claim.is_partial && claim.review_comment && (
        <div className="alert alert-warn">
          <p>
            <strong>Partially approved by {claim.reviewer?.name}:</strong> “{claim.review_comment}”
          </p>
        </div>
      )}
      {claim.status === 'PAID' && (
        <div className="alert alert-info">
          <p>
            Paid on {formatDateTime(claim.paid_at)}
            {claim.payment_reference ? ` · Reference ${claim.payment_reference}` : ''}.
          </p>
        </div>
      )}

      <section className="card">
        <h2>Amounts</h2>
        <div className="amount-compare">
          <div>
            <div className="muted small">Claimed</div>
            <div className="amount-big">{formatMoney(claim.amount, cur)}</div>
          </div>
          {claim.approved_amount && (
            <div>
              <div className="muted small">Approved</div>
              <div className={`amount-big ${claim.is_partial ? 'amount-partial' : 'amount-ok'}`}>
                {formatMoney(claim.approved_amount, cur)}
              </div>
              {claim.is_partial && (
                <div className="small amount-partial">{formatMoney(notApproved, cur)} not approved</div>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="card">
        <h2>Details</h2>
        <dl className="detail-grid">
          <div><dt>Employee</dt><dd>{claim.employee.name}</dd></div>
          <div><dt>Category</dt><dd>{claim.category}</dd></div>
          <div><dt>Expense date</dt><dd>{formatDate(claim.expense_date)}</dd></div>
          <div><dt>Receipt reference</dt><dd>{claim.receipt_ref ?? '-'}</dd></div>
          <div><dt>Submitted</dt><dd>{formatDateTime(claim.submitted_at)}</dd></div>
          <div><dt>Reviewed by</dt><dd>{claim.reviewer?.name ?? '-'}</dd></div>
        </dl>
        {claim.description && (
          <>
            <h3 className="detail-subhead">Description</h3>
            <p>{claim.description}</p>
          </>
        )}
      </section>

      <section className="card">
        <h2>History</h2>
        <Timeline events={claim.events} />
      </section>
    </div>
  )
}