export function Pagination({ page, pageSize, total, onPage }) {
    if (total === 0) return null
    const first = (page - 1) * pageSize + 1
    const last = Math.min(page * pageSize, total)
    const hasNext = page * pageSize < total
    return (
      <div className="pager">
        <span className="muted small">
          Showing {first}–{last} of {total}
        </span>
        <div className="row">
          <button type="button" className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            Previous
          </button>
          <button type="button" className="btn btn-secondary btn-sm" disabled={!hasNext} onClick={() => onPage(page + 1)}>
            Next
          </button>
        </div>
      </div>
    )
  }