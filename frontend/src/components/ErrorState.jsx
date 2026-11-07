import { errorMessage } from '../lib/errors'

export function ErrorState({ error, onRetry }) {
  return (
    <div className="alert alert-error" role="alert">
      <p>{errorMessage(error)}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}