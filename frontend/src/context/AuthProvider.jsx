import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/api'
import { setUnauthorizedHandler, tokenStore } from '../api/client'
import { useToast } from '../hooks/useToast'
import { AuthContext } from './authContext'

// status: 'loading' (checking a saved token) | 'authenticated' | 'anonymous'
export function AuthProvider({ children }) {
  const toast = useToast()
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(() => (tokenStore.get() ? 'loading' : 'anonymous'))

  // Restore the session after a page reload.
  useEffect(() => {
    if (status !== 'loading') return undefined
    let cancelled = false
    api
      .me()
      .then((me) => {
        if (cancelled) return
        setUser(me)
        setStatus('authenticated')
      })
      .catch(() => {
        if (cancelled) return
        tokenStore.clear()
        setStatus('anonymous')
      })
    return () => {
      cancelled = true
    }
  }, [status])

  // If any request comes back 401 (expired token), drop the session.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      tokenStore.clear()
      setUser(null)
      setStatus('anonymous')
      toast.info('Your session ended. Please log in again.')
    })
  }, [toast])

  const login = useCallback(async (userId) => {
    const { token, user: loggedIn } = await api.login(userId)
    tokenStore.set(token)
    setUser(loggedIn)
    setStatus('authenticated')
    return loggedIn
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* even if the server call fails, log out locally */
    }
    tokenStore.clear()
    setUser(null)
    setStatus('anonymous')
  }, [])

  const value = useMemo(() => ({ user, status, login, logout }), [user, status, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}