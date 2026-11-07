import { useCallback, useEffect, useRef, useState } from 'react'

// Loads data from the API and re-loads when `params` change.
//   const { data, error, loading, reload, mutate } = useApi((params, signal) => api.x(params, signal), params)
// - loading is true whenever the data on screen is not yet for the current params
//   (the previous data stays available, so lists can dim instead of flashing empty)
// - mutate(newData) replaces the data without a network call (e.g. after an action)
export function useApi(fetcher, params) {
  const [reloadCount, setReloadCount] = useState(0)
  const key = `${JSON.stringify(params ?? null)}#${reloadCount}`
  const [result, setResult] = useState({ key: null, data: null, error: null })

  const fetcherRef = useRef(fetcher)
  const paramsRef = useRef(params)
  useEffect(() => {
    fetcherRef.current = fetcher
    paramsRef.current = params
  })

  useEffect(() => {
    const controller = new AbortController()
    fetcherRef
      .current(paramsRef.current, controller.signal)
      .then((data) => setResult({ key, data, error: null }))
      .catch((error) => {
        if (error.name === 'AbortError') return
        setResult((previous) => ({ key, data: previous.data, error }))
      })
    return () => controller.abort()
  }, [key])

  const reload = useCallback(() => setReloadCount((n) => n + 1), [])
  const mutate = useCallback(
    (data) => setResult((previous) => ({ ...previous, key, data, error: null })),
    [key],
  )

  return { data: result.data, error: result.error, loading: result.key !== key, reload, mutate }
}