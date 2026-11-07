import { beforeEach, describe, expect, it, vi } from 'vitest'

// The client keeps module-level state (token, in-flight refresh), so each test gets a fresh copy.
let client
beforeEach(async () => {
  vi.resetModules()
  client = await import('./client')
})

const json = (status, body) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const USER = { id: 1, name: 'Aarav Sharma', email: 'aarav@napho.test', role: 'employee' }

// A fake backend: /api/auth/refresh issues "new-token"; everything else needs that token.
function fakeBackend({ refreshOk = true } = {}) {
  const fetchMock = vi.fn(async (url, init) => {
    if (url === '/api/auth/refresh') {
      await Promise.resolve() // let concurrent callers pile up on the same refresh
      return refreshOk
        ? json(200, { access_token: 'new-token', token_type: 'bearer', expires_in: 900, user: USER })
        : json(401, { error: { code: 'INVALID_REFRESH_TOKEN', message: 'Your session has ended.' } })
    }
    if (url === '/api/auth/login') {
      return json(401, { error: { code: 'INVALID_CREDENTIALS', message: 'Incorrect email or password.' } })
    }
    if (init.headers.Authorization !== 'Bearer new-token') {
      return json(401, { error: { code: 'TOKEN_EXPIRED', message: 'Your session has expired.' } })
    }
    return json(200, { url })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const calls = (fetchMock, url) => fetchMock.mock.calls.filter(([u]) => u === url)

describe('API client: 401 -> refresh -> retry', () => {
  it('refreshes once for concurrent 401s and retries each request once', async () => {
    const fetchMock = fakeBackend()
    const refreshed = vi.fn()
    client.setSessionHandlers({ refreshed })
    client.authToken.set('expired-token')

    const [a, b] = await Promise.all([
      client.request('GET', '/api/claims'),
      client.request('GET', '/api/claims/summary'),
    ])

    expect(a).toEqual({ url: '/api/claims' })
    expect(b).toEqual({ url: '/api/claims/summary' })
    const refreshCalls = calls(fetchMock, '/api/auth/refresh')
    expect(refreshCalls).toHaveLength(1) // single-flight
    expect(refreshCalls[0][1]).toMatchObject({
      method: 'POST',
      credentials: 'include',
      headers: expect.objectContaining({ 'X-Requested-With': 'XMLHttpRequest' }),
    })
    expect(calls(fetchMock, '/api/claims')).toHaveLength(2) // original + one retry
    expect(client.authToken.get()).toBe('new-token') // kept in memory only
    expect(refreshed).toHaveBeenCalledWith(USER)
  })

  it('sends cookies with every request', async () => {
    const fetchMock = fakeBackend()
    client.authToken.set('new-token')
    await client.request('GET', '/api/claims')
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer new-token')
  })

  it('ends the session when the refresh fails, and surfaces the original 401', async () => {
    const fetchMock = fakeBackend({ refreshOk: false })
    const expired = vi.fn()
    client.setSessionHandlers({ expired })
    client.authToken.set('expired-token')

    await expect(client.request('GET', '/api/claims')).rejects.toMatchObject({
      status: 401,
      code: 'TOKEN_EXPIRED',
    })
    expect(expired).toHaveBeenCalledTimes(1)
    expect(client.authToken.get()).toBeNull()
    expect(calls(fetchMock, '/api/claims')).toHaveLength(1) // no retry without a new token
  })

  it('does not try to refresh after a failed login', async () => {
    const fetchMock = fakeBackend()
    await expect(
      client.request('POST', '/api/auth/login', { body: { email: 'x@y.z', password: 'nope' } }),
    ).rejects.toMatchObject({ status: 401, code: 'INVALID_CREDENTIALS' })
    expect(calls(fetchMock, '/api/auth/refresh')).toHaveLength(0)
  })

  it('shares one in-flight refresh between callers (e.g. StrictMode double effect)', async () => {
    const fetchMock = fakeBackend()
    const [first, second] = await Promise.all([client.refreshSession(), client.refreshSession()])
    expect(first).toBe(second)
    expect(calls(fetchMock, '/api/auth/refresh')).toHaveLength(1)
  })

  it('never writes the token to localStorage', async () => {
    fakeBackend()
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    await client.refreshSession()
    expect(setItem).not.toHaveBeenCalled()
    expect(localStorage.length).toBe(0)
  })
})
