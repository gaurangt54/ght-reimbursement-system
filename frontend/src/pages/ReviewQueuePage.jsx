import { Link } from 'react-router-dom'
import { api } from '../api/api'
import { ClaimsTable } from '../components/ClaimsTable'
import { ErrorState } from '../components/ErrorState'
import { Pagination } from '../components/Pagination'
import { SearchInput } from '../components/SearchInput'
import { Spinner } from '../components/Spinner'
import { SummaryCards } from '../components/SummaryCards'
import { useApi } from '../hooks/useApi'
import { useUrlFilters } from '../hooks/useUrlFilters'
import { formatMoney } from '../lib/format'

const PAGE_SIZE = 10
const SORTS = [
  { value: 'submitted_at:asc', label: 'Waiting longest first' },
  { value: 'submitted_at:desc', label: 'Newest first' },
  { value: 'amount:desc', label: 'Highest amount' },
  { value: 'amount:asc', label: 'Lowest amount' },
]

// Claims waiting for a decision (status SUBMITTED), oldest first by default.
export function ReviewQueuePage() {
  const { searchParams, setParam, clear } = useUrlFilters()
  const q = searchParams.get('q') ?? ''
  const category = searchParams.get('category') ?? ''
  const sort = searchParams.get('sort') ?? SORTS[0].value
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const [sortBy, order] = sort.split(':')

  const summary = useApi((_p, signal) => api.getSummary(signal), null)
  const meta = useApi(() => api.getMeta(), null)
  const claims = useApi((p, signal) => api.listClaims(p, signal), {
    scope: 'pending', q, category, sort_by: sortBy, order, page, page_size: PAGE_SIZE,
  })

  const awaitingPayment = summary.data?.counts.APPROVED ?? 0
  const filtersActive = Boolean(q || category)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Pending review</h1>
          <p className="muted">Claims waiting for your decision. Open one to approve or reject it.</p>
        </div>
      </div>

      {summary.data && <SummaryCards summary={summary.data} />}

      {awaitingPayment > 0 && (
        <div className="alert alert-info">
          <div className="row row-between">
            <span>
              {awaitingPayment} approved claim{awaitingPayment === 1 ? ' is' : 's are'} waiting to be
              paid
              {summary.data && ` (${formatMoney(Number(summary.data.approved_amount) - Number(summary.data.paid_amount))})`}.
            </span>
            <Link className="btn btn-secondary btn-sm" to="/review/history?status=APPROVED">
              View them
            </Link>
          </div>
        </div>
      )}

      <div className="card">
        <div className="toolbar">
          <SearchInput
            key={q}
            value={q}
            placeholder="Search title, description or employee"
            onChange={(v) => setParam('q', v)}
          />
          <select className="select" aria-label="Category" value={category} onChange={(e) => setParam('category', e.target.value)}>
            <option value="">All categories</option>
            {(meta.data?.categories ?? []).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select className="select" aria-label="Sort by" value={sort} onChange={(e) => setParam('sort', e.target.value)}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        {claims.error && <ErrorState error={claims.error} onRetry={claims.reload} />}
        {!claims.data && !claims.error && <Spinner label="Loading claims…" />}

        {claims.data && !claims.error && claims.data.items.length === 0 && (
          <div className="empty">
            {filtersActive ? (
              <>
                <p>No pending claims match your filters.</p>
                <button type="button" className="btn btn-secondary" onClick={clear}>Clear filters</button>
              </>
            ) : (
              <>
                <h2>You’re all caught up</h2>
                <p className="muted">There are no claims waiting for review.</p>
              </>
            )}
          </div>
        )}

        {claims.data && !claims.error && claims.data.items.length > 0 && (
          <div className={claims.loading ? 'is-loading' : ''}>
            <ClaimsTable claims={claims.data.items} showEmployee timeColumn="submitted_at" actionLabel="Review" />
            <Pagination page={page} pageSize={PAGE_SIZE} total={claims.data.total} onPage={(p) => setParam('page', String(p))} />
          </div>
        )}
      </div>
    </>
  )
}