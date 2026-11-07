import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/api'
import { ClaimsTable } from '../components/ClaimsTable'
import { ErrorState } from '../components/ErrorState'
import { Pagination } from '../components/Pagination'
import { SearchInput } from '../components/SearchInput'
import { Spinner } from '../components/Spinner'
import { SummaryCards } from '../components/SummaryCards'
import { useApi } from '../hooks/useApi'
import { STATUS_META } from '../lib/format'

const PAGE_SIZE = 10
const SORTS = [
  { value: 'updated_at:desc', label: 'Recently updated' },
  { value: 'expense_date:desc', label: 'Newest expense' },
  { value: 'amount:desc', label: 'Highest amount' },
  { value: 'amount:asc', label: 'Lowest amount' },
]

export function MyClaimsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? ''
  const category = searchParams.get('category') ?? ''
  const q = searchParams.get('q') ?? ''
  const sort = searchParams.get('sort') ?? SORTS[0].value
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const [sortBy, order] = sort.split(':')

  function setParam(name, value) {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (value) next.set(name, value)
        else next.delete(name)
        if (name !== 'page') next.delete('page') // any filter change goes back to page 1
        return next
      },
      { replace: true },
    )
  }

  const summary = useApi((_p, signal) => api.getSummary(signal), null)
  const meta = useApi(() => api.getMeta(), null)
  const claims = useApi((p, signal) => api.listClaims(p, signal), {
    status, category, q, sort_by: sortBy, order, page, page_size: PAGE_SIZE,
  })

  const counts = summary.data?.counts
  const totalAll = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0
  const filtersActive = Boolean(status || category || q)
  const tabs = [
    { value: '', label: 'All', count: totalAll },
    ...Object.entries(STATUS_META).map(([value, m]) => ({ value, label: m.label, count: counts?.[value] })),
  ]

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My claims</h1>
          <p className="muted">Track your expense claims from draft to payment.</p>
        </div>
        <Link className="btn btn-primary" to="/claims/new">New claim</Link>
      </div>

      {summary.data && <SummaryCards summary={summary.data} />}

      {counts?.REJECTED > 0 && status !== 'REJECTED' && (
        <div className="alert alert-warn">
          <div className="row row-between">
            <span>
              {counts.REJECTED} claim{counts.REJECTED === 1 ? ' was' : 's were'} rejected and need
              {counts.REJECTED === 1 ? 's' : ''} your attention.
            </span>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setParam('status', 'REJECTED')}>
              Show them
            </button>
          </div>
        </div>
      )}

      <div className="tabs" role="group" aria-label="Filter by status">
        {tabs.map((tab) => (
          <button
            key={tab.value || 'all'}
            type="button"
            className={`tab ${status === tab.value ? 'tab-active' : ''}`}
            aria-pressed={status === tab.value}
            onClick={() => setParam('status', tab.value)}
          >
            {tab.label}
            {tab.count !== undefined && <span className="tab-count">{tab.count}</span>}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="toolbar">
          <SearchInput key={q} value={q} placeholder="Search title or description" onChange={(v) => setParam('q', v)} />
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

        {claims.error && !claims.data && <ErrorState error={claims.error} onRetry={claims.reload} />}
        {!claims.data && !claims.error && <Spinner label="Loading claims…" />}

        {claims.data && claims.data.items.length === 0 && (
          <div className="empty">
            {filtersActive ? (
              <>
                <p>No claims match your filters.</p>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setSearchParams({}, { replace: true })}
                >
                  Clear filters
                </button>
              </>
            ) : (
              <>
                <h2>No claims yet</h2>
                <p className="muted">Create your first expense claim to get started.</p>
                <Link className="btn btn-primary" to="/claims/new">New claim</Link>
              </>
            )}
          </div>
        )}

        {claims.data && claims.data.items.length > 0 && (
          <div className={claims.loading ? 'is-loading' : ''}>
            <ClaimsTable claims={claims.data.items} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={claims.data.total} onPage={(p) => setParam('page', String(p))} />
          </div>
        )}
      </div>
    </>
  )
}