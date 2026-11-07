// Thin wrapper around fetch. It:
//   - adds the access token (kept in memory only: never localStorage, so an XSS bug cannot
//     read a long-lived credential out of storage),
//   - sends cookies (`credentials: 'include'`) so the HttpOnly refresh cookie reaches /api/auth,
//   - on a 401, refreshes the session once (single-flight) and retries the request once,
//   - turns every failure into one ApiError shape that matches the backend:
//       { status, code, message, fields: { fieldName: "message" } }

export class ApiError extends Error {
  constructor({ status = 0, code = 'UNKNOWN', message = 'Something went wrong.', fields = {} }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

// ---- access token (memory only) ----
let accessToken = null
export const authToken = {
  get: () => accessToken,
  set: (token) => {
    accessToken = token
  },
  clear: () => {
    accessToken = null
  },
}

// AuthProvider registers callbacks here.
let onSessionExpired = () => {}
let onSessionRefreshed = () => {}
export function setSessionHandlers({ expired, refreshed } = {}) {
  onSessionExpired = expired ?? (() => {})
  onSessionRefreshed = refreshed ?? (() => {})
}

// Cookie-authenticated endpoints need this header (the backend's CSRF check).
const CSRF_HEADERS = { 'X-Requested-With': 'XMLHttpRequest' }
const NO_RETRY = ['/api/auth/login', '/api/auth/refresh', '/api/auth/logout']

function buildUrl(path, params) {
  const query = new URLSearchParams()
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.append(key, value)
  })
  const qs = query.toString()
  return qs ? `${path}?${qs}` : path
}

async function toApiError(response) {
  let payload = null
  try {
    payload = await response.json()
  } catch {
    /* non-JSON error body */
  }
  const error = payload?.error ?? {}
  return new ApiError({
    status: response.status,
    code: error.code ?? 'HTTP_ERROR',
    message: error.message ?? `Request failed (${response.status}).`,
    fields: error.fields ?? {},
  })
}

async function rawFetch(method, path, { params, body, signal, headers: extra } = {}) {
  const headers = { ...extra }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  try {
    return await fetch(buildUrl(path, params), {
      method,
      headers,
      credentials: 'include',
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError({
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the server. Check that the backend is running and try again.',
    })
  }
}

// ---- refresh (single-flight) ----
// Every caller that needs a refresh at the same moment (several 401s at once, or React
// StrictMode running the startup effect twice) shares this one promise, so only one
// POST /api/auth/refresh is ever in flight.
let refreshPromise = null

export function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const response = await rawFetch('POST', '/api/auth/refresh', { headers: CSRF_HEADERS })
      if (!response.ok) {
        accessToken = null
        throw await toApiError(response)
      }
      const session = await response.json()
      accessToken = session.access_token
      onSessionRefreshed(session.user)
      return session
    })().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

async function send(method, path, options = {}) {
  let response = await rawFetch(method, path, options)

  if (response.status === 401 && !NO_RETRY.includes(path)) {
    const original = await toApiError(response)
    try {
      await refreshSession()
    } catch {
      onSessionExpired()
      throw original
    }
    response = await rawFetch(method, path, options) // retry exactly once
    if (response.status === 401) {
      accessToken = null
      onSessionExpired()
    }
  }

  if (!response.ok) throw await toApiError(response)
  return response
}

export async function request(method, path, options) {
  const response = await send(method, path, options)
  if (response.status === 204) return null
  return response.json()
}

// For cookie-authenticated auth endpoints (refresh, logout).
export function requestWithCsrf(method, path, options = {}) {
  return request(method, path, { ...options, headers: { ...options.headers, ...CSRF_HEADERS } })
}

// Downloads a file (e.g. CSV) while still sending the auth header.
export async function download(path, { params, filename }) {
  const response = await send('GET', path, { params })
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
