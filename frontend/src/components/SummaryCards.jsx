import { formatMoney } from '../lib/format'

// Dashboard numbers from GET /api/claims/summary. Same component for both roles.
export function SummaryCards({ summary }) {
  const { counts } = summary
  return (
    <div className="grid-stats">
      <div className="stat">
        <div className="stat-label">Total claimed</div>
        <div className="stat-value">{formatMoney(summary.total_claimed)}</div>
        <div className="stat-sub">Excluding drafts</div>
      </div>
      <div className="stat">
        <div className="stat-label">Waiting for approval</div>
        <div className="stat-value">{formatMoney(summary.pending_amount)}</div>
        <div className="stat-sub">{counts.SUBMITTED} claim{counts.SUBMITTED === 1 ? '' : 's'}</div>
      </div>
      <div className="stat">
        <div className="stat-label">Approved</div>
        <div className="stat-value">{formatMoney(summary.approved_amount)}</div>
        <div className="stat-sub">Approved amounts, incl. paid</div>
      </div>
      <div className="stat">
        <div className="stat-label">Paid</div>
        <div className="stat-value">{formatMoney(summary.paid_amount)}</div>
        <div className="stat-sub">{counts.PAID} claim{counts.PAID === 1 ? '' : 's'}</div>
      </div>
    </div>
  )
}