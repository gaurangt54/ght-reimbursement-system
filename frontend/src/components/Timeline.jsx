import { ACTION_LABELS, formatDate, formatDateTime, formatMoney } from '../lib/format'

const FIELD_LABELS = {
  title: 'Title',
  description: 'Description',
  category: 'Category',
  amount: 'Amount',
  expense_date: 'Expense date',
  receipt_ref: 'Receipt',
}

function showValue(field, value) {
  if (value === 'None' || value === '') return '(empty)'
  if (field === 'amount') return formatMoney(value)
  if (field === 'expense_date') return formatDate(value)
  return value
}

function EventDetails({ event }) {
  const { action, details } = event
  if (action === 'edited' && details) {
    return (
      <ul className="change-list">
        {Object.entries(details).map(([field, [from, to]]) => (
          <li key={field}>
            <strong>{FIELD_LABELS[field] ?? field}:</strong> {showValue(field, from)} → {showValue(field, to)}
          </li>
        ))}
      </ul>
    )
  }
  if (action === 'partially_approved' && details) {
    return (
      <p className="small">
        Approved {formatMoney(details.approved)} of {formatMoney(details.claimed)} claimed.
      </p>
    )
  }
  if (action === 'approved' && details) {
    return <p className="small">Approved in full: {formatMoney(details.approved)}.</p>
  }
  if (action === 'paid' && details) {
    return <p className="small">Amount paid: {formatMoney(details.amount)}.</p>
  }
  return null
}

export function Timeline({ events }) {
  return (
    <ol className="timeline">
      {events.map((event) => (
        <li key={event.id}>
          <strong>{ACTION_LABELS[event.action] ?? event.action}</strong>{' '}
          <span className="muted">by {event.user.name}</span>
          <div className="when">{formatDateTime(event.created_at)}</div>
          <EventDetails event={event} />
          {event.comment && <div className="note">“{event.comment}”</div>}
        </li>
      ))}
    </ol>
  )
}