import { Link } from 'react-router-dom'
import { formatDate, formatDateTime, formatMoney } from '../lib/format'
import { StatusBadge } from './StatusBadge'

export function ClaimsTable({ claims, showEmployee = false }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>Claim</th>
            {showEmployee && <th>Employee</th>}
            <th>Expense date</th>
            <th className="right">Amount</th>
            <th>Status</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.id}>
              <td className="muted">{claim.id}</td>
              <td>
                <Link className="row-link" to={`/claims/${claim.id}`}>{claim.title}</Link>
                <div className="muted small">{claim.category}</div>
              </td>
              {showEmployee && <td>{claim.employee.name}</td>}
              <td className="nowrap">{formatDate(claim.expense_date)}</td>
              <td className="right nowrap">
                {formatMoney(claim.amount, claim.currency)}
                {claim.approved_amount && (
                  <div className={claim.is_partial ? 'small amount-partial' : 'muted small'}>
                    Approved {formatMoney(claim.approved_amount, claim.currency)}
                  </div>
                )}
              </td>
              <td>
                <StatusBadge status={claim.status} />{' '}
                {claim.is_partial && <span className="badge badge-warn">Partial</span>}
                {claim.resubmission_count > 0 && (
                  <div className="muted small">Resubmitted ×{claim.resubmission_count}</div>
                )}
              </td>
              <td className="muted small nowrap">{formatDateTime(claim.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}