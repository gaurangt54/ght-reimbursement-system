import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/api'
import { authToken, setSessionHandlers } from '../api/client'
import { useToast } from '../hooks/useToast'
import { AuthContext } from './authContext'

// Tells other open tabs about logins/logouts (not available in every environment).
const CHANNEL_NAME = 'reimbursement-auth'
function openChannel() {
  try {
    return typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel(CHANNEL_NAME)
  } catch {
    return null
  }
}

// status: 'loading' (restoring the session on app start) | 'authenticated' | 'anonymous'
//
// The access token lives only in memory (see api/client.js). After a reload it is gone, so on
// start we call /api/auth/refresh: the HttpOnly cookie gets us a new one if the session is alive.
export function AuthProvider({ children }) {
  const toast = useToast()
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading')
  const userRef = useRef(null)
  const channelRef = useRef(null)

  const applyUser = useCallback((next) => {
    userRef.current = next
    setUser(next)
    setStatus(next ? 'authenticated' : 'anonymous')
  }, [])

  const clearLocalSession = useCallback(() => {
    authToken.clear()
    applyUser(null)
  }, [applyUser])

  // Restore the session after a reload. refreshSession() is single-flight, so StrictMode's
  // double effect still makes only one request; the `cancelled` flag ignores the first run.
  useEffect(() => {
    let cancelled = false
    api
      .refresh()
      .then((session) => !cancelled && applyUser(session.user))
      .catch(() => !cancelled && applyUser(null))
    return () => {
      cancelled = true
    }
  }, [applyUser])

  // The API client calls these when a refresh succeeds or the session is gone for good.
  useEffect(() => {
    setSessionHandlers({
      refreshed: (next) => {
        if (userRef.current) applyUser(next) // keeps role/name current
      },
      expired: () => {
        if (!userRef.current) return // never signed in: nothing to announce
        clearLocalSession()
        toast.info('Your session expired. Please sign in again.')
      },
    })
    return () => setSessionHandlers()
  }, [applyUser, clearLocalSession, toast])

  // Keep tabs in sync. They share one refresh cookie, so one browser = one signed-in user:
  //   logout in one tab -> log out everywhere;
  //   sign-in (possibly as someone else) in one tab -> the others switch to that user now,
  //   instead of silently at their next refresh.
  useEffect(() => {
    const channel = openChannel()
    channelRef.current = channel
    if (!channel) return undefined
    channel.onmessage = (event) => {
      const message = event.data
      if (message?.type === 'logout' && userRef.current) {
        clearLocalSession()
        toast.info('You signed out in another tab.')
      }
      if (message?.type === 'login' && userRef.current?.id !== message.userId) {
        const previous = userRef.current
        api
          .refresh() // the shared cookie now belongs to the new user
          .then((session) => {
            applyUser(session.user)
            if (previous) toast.info(`You're now signed in as ${session.user.name} (from another tab).`)
          })
          .catch(() => clearLocalSession())
      }
    }
    return () => {
      channel.close()
      channelRef.current = null
    }
  }, [applyUser, clearLocalSession, toast])

  const login = useCallback(
    async (email, password) => {
      const session = await api.login(email, password)
      authToken.set(session.access_token)
      applyUser(session.user)
      channelRef.current?.postMessage({ type: 'login', userId: session.user.id })
      return session.user
    },
    [applyUser],
  )

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* even if the server call fails, log out locally */
    }
    clearLocalSession()
    channelRef.current?.postMessage({ type: 'logout' })
  }, [clearLocalSession])

  const value = useMemo(() => ({ user, status, login, logout }), [user, status, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
