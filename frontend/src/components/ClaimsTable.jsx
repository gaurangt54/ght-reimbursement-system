import { Link } from 'react-router-dom'
import { formatAgo, formatDate, formatDateTime, formatMoney } from '../lib/format'
import { StatusBadge } from './StatusBadge'

const TIME_COLUMNS = {
  updated_at: 'Updated',
  submitted_at: 'Submitted',
  reviewed_at: 'Reviewed',
}

// One table for every list in the app. Optional columns:
//   showEmployee  - who made the claim (approver views)
//   showReviewer  - who approved/rejected it
//   timeColumn    - which timestamp to show: updated_at (default), submitted_at, reviewed_at
//   actionLabel   - adds a button column linking to the claim (e.g. "Review")
// On narrow screens each row turns into a card (CSS); data-label gives each cell its caption.
export function ClaimsTable({
  claims,
  showEmployee = false,
  showReviewer = false,
  timeColumn = 'updated_at',
  actionLabel,
}) {
  return (
    <div className="table-wrap">
      <table className="table table-cards">
        <thead>
          <tr>
            <th>#</th>
            <th>Claim</th>
            {showEmployee && <th>Employee</th>}
            <th>Expense date</th>
            <th className="right">Amount</th>
            <th>Status</th>
            {showReviewer && <th>Reviewer</th>}
            <th>{TIME_COLUMNS[timeColumn]}</th>
            {actionLabel && <th />}
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.id}>
              <td className="muted cell-id">{claim.id}</td>
              <td className="cell-title">
                <Link className="row-link" to={`/claims/${claim.id}`}>{claim.title}</Link>
                <div className="muted small">{claim.category}</div>
              </td>
              {showEmployee && <td data-label="Employee">{claim.employee.name}</td>}
              <td className="nowrap" data-label="Expense date">{formatDate(claim.expense_date)}</td>
              <td className="right nowrap" data-label="Amount">
                {formatMoney(claim.amount, claim.currency)}
                {claim.approved_amount && (
                  <div className={claim.is_partial ? 'small amount-partial' : 'muted small'}>
                    Approved {formatMoney(claim.approved_amount, claim.currency)}
                  </div>
                )}
              </td>
              <td data-label="Status">
                <StatusBadge status={claim.status} />{' '}
                {claim.is_partial && <span className="badge badge-warn">Partial</span>}
                {claim.resubmission_count > 0 && (
                  <div className="muted small">Resubmitted ×{claim.resubmission_count}</div>
                )}
              </td>
              {showReviewer && <td data-label="Reviewer">{claim.reviewer?.name ?? '-'}</td>}
              <td className="muted small nowrap" data-label={TIME_COLUMNS[timeColumn]}>
                {formatDateTime(claim[timeColumn])}
                {timeColumn === 'submitted_at' && <div>{formatAgo(claim.submitted_at)}</div>}
              </td>
              {actionLabel && (
                <td className="right cell-action">
                  <Link className="btn btn-secondary btn-sm" to={`/claims/${claim.id}`}>{actionLabel}</Link>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}