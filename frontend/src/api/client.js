// Thin wrapper around fetch: adds the auth token, parses JSON, and turns every failure
// into one ApiError shape that matches the backend:
//   { status, code, message, fields: { fieldName: "message" } }

const TOKEN_KEY = 'reimbursement.token'

export const tokenStore = {
  get() {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token) {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* storage unavailable (private mode): the session just won't survive a reload */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },
}

export class ApiError extends Error {
  constructor({ status = 0, code = 'UNKNOWN', message = 'Something went wrong.', fields = {} }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

// AuthProvider registers a callback here so an expired/invalid token logs the user out.
let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

function buildUrl(path, params) {
  const query = new URLSearchParams()
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.append(key, value)
  })
  const qs = query.toString()
  return qs ? `${path}?${qs}` : path
}

async function send(method, path, { params, body, signal } = {}) {
  const headers = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let response
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
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

  if (!response.ok) {
    let payload = null
    try {
      payload = await response.json()
    } catch {
      /* non-JSON error body */
    }
    const error = payload?.error ?? {}
    if (response.status === 401 && token && !path.endsWith('/auth/login')) onUnauthorized()
    throw new ApiError({
      status: response.status,
      code: error.code ?? 'HTTP_ERROR',
      message: error.message ?? `Request failed (${response.status}).`,
      fields: error.fields ?? {},
    })
  }
  return response
}

export async function request(method, path, options) {
  const response = await send(method, path, options)
  if (response.status === 204) return null
  return response.json()
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