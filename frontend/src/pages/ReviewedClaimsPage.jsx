import { useState } from 'react'
import { api } from '../api/api'
import { ClaimsTable } from '../components/ClaimsTable'
import { ErrorState } from '../components/ErrorState'
import { Pagination } from '../components/Pagination'
import { SearchInput } from '../components/SearchInput'
import { Spinner } from '../components/Spinner'
import { useApi } from '../hooks/useApi'
import { useToast } from '../hooks/useToast'
import { useUrlFilters } from '../hooks/useUrlFilters'
import { errorMessage } from '../lib/errors'
import { STATUS_META } from '../lib/format'
import { ROLES } from '../lib/routes'

const PAGE_SIZE = 10
const REVIEWED_STATUSES = ['APPROVED', 'REJECTED', 'PAID']
const SORTS = [
  { value: 'updated_at:desc', label: 'Recently updated' },
  { value: 'expense_date:desc', label: 'Newest expense' },
  { value: 'amount:desc', label: 'Highest amount' },
  { value: 'amount:asc', label: 'Lowest amount' },
]

// Everything already decided (approved, rejected, paid). This is also where approved claims
// wait to be marked as paid, and where the CSV export lives.
export function ReviewedClaimsPage() {
  const toast = useToast()
  const { searchParams, setParam, clear } = useUrlFilters()
  const status = searchParams.get('status') ?? ''
  const q = searchParams.get('q') ?? ''
  const category = searchParams.get('category') ?? ''
  const employeeId = searchParams.get('employee') ?? ''
  const dateFrom = searchParams.get('from') ?? ''
  const dateTo = searchParams.get('to') ?? ''
  const sort = searchParams.get('sort') ?? SORTS[0].value
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const [sortBy, order] = sort.split(':')
  const [exporting, setExporting] = useState(false)

  const summary = useApi((_p, signal) => api.getSummary(signal), null)
  const meta = useApi(() => api.getMeta(), null)
  const users = useApi(() => api.listUsers(), null)

  // The filters the server understands. Export uses the same ones (without paging),
  // so the file contains exactly what the filtered list shows.
  const filters = {
    scope: 'reviewed', status, category, q, employee_id: employeeId,
    date_from: dateFrom, date_to: dateTo, sort_by: sortBy, order,
  }
  const claims = useApi((p, signal) => api.listClaims(p, signal), { ...filters, page, page_size: PAGE_SIZE })

  async function exportCsv() {
    setExporting(true)
    try {
      await api.exportCsv(filters)
      toast.success('Export downloaded.')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setExporting(false)
    }
  }

  const counts = summary.data?.counts
  const totalReviewed = counts ? REVIEWED_STATUSES.reduce((sum, s) => sum + counts[s], 0) : undefined
  const tabs = [
    { value: '', label: 'All', count: totalReviewed },
    ...REVIEWED_STATUSES.map((value) => ({ value, label: STATUS_META[value].label, count: counts?.[value] })),
  ]
  const employees = (users.data ?? []).filter((u) => u.role === ROLES.EMPLOYEE)
  const filtersActive = Boolean(status || q || category || employeeId || dateFrom || dateTo)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Reviewed claims</h1>
          <p className="muted">Approved, rejected and paid claims. Mark approved claims as paid from here.</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={exportCsv} disabled={exporting}>
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>

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
          <SearchInput
            key={q}
            value={q}
            placeholder="Search title, description or employee"
            onChange={(v) => setParam('q', v)}
          />
          <select className="select" aria-label="Employee" value={employeeId} onChange={(e) => setParam('employee', e.target.value)}>
            <option value="">All employees</option>
            {employees.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
          <select className="select" aria-label="Category" value={category} onChange={(e) => setParam('category', e.target.value)}>
            <option value="">All categories</option>
            {(meta.data?.categories ?? []).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <label className="inline-field">
            <span className="muted small">Expense from</span>
            <input type="date" className="input" value={dateFrom} onChange={(e) => setParam('from', e.target.value)} />
          </label>
          <label className="inline-field">
            <span className="muted small">to</span>
            <input type="date" className="input" value={dateTo} onChange={(e) => setParam('to', e.target.value)} />
          </label>
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
                <p>No reviewed claims match your filters.</p>
                <button type="button" className="btn btn-secondary" onClick={clear}>Clear filters</button>
              </>
            ) : (
              <>
                <h2>Nothing reviewed yet</h2>
                <p className="muted">Claims you approve or reject will show up here.</p>
              </>
            )}
          </div>
        )}

        {claims.data && !claims.error && claims.data.items.length > 0 && (
          <div className={claims.loading ? 'is-loading' : ''}>
            <ClaimsTable
              claims={claims.data.items}
              showEmployee
              showReviewer
              timeColumn="updated_at"
              actionLabel={status === 'APPROVED' ? 'Mark paid' : undefined}
            />
            <Pagination page={page} pageSize={PAGE_SIZE} total={claims.data.total} onPage={(p) => setParam('page', String(p))} />
          </div>
        )}
      </div>
    </>
  )
}