import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

// Keeps list filters in the URL (so refresh, back button and shared links work).
// setParam(name, value): empty value removes the param; any change except `page` resets to page 1.
export function useUrlFilters() {
  const [searchParams, setSearchParams] = useSearchParams()

  const setParam = useCallback(
    (name, value) => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          if (value) next.set(name, value)
          else next.delete(name)
          if (name !== 'page') next.delete('page')
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const clear = useCallback(() => setSearchParams({}, { replace: true }), [setSearchParams])

  return { searchParams, setParam, clear }
}