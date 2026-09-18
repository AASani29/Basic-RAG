import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import * as api from '../api/endpoints'
import type { User } from '../api/endpoints'

interface AuthContextValue {
  user: User | null
  /** Distinguishes "haven't checked yet" from "checked, not logged in".
   * ProtectedLayout needs this to avoid redirecting to /login for a split
   * second on every page refresh, before the bootstrap check below has had
   * a chance to confirm an existing token is still valid. */
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  // Derived directly from localStorage instead of always starting true and
  // setting it false inside the effect below: with no token there is
  // nothing to verify, so there is no "loading" state to be in at all —
  // computing that during render (not as an effect side-effect) skips a
  // pointless extra render on every page load that has no session.
  const [isLoading, setIsLoading] = useState<boolean>(() => localStorage.getItem('token') !== null)

  useEffect(() => {
    // On every fresh page load, React state always starts empty — the only
    // thing that survives a refresh is the token in localStorage. This
    // reconstructs `user` from that token by asking the API who it belongs
    // to, which doubles as confirming the token is still valid (an
    // expired/invalid one 401s, and the axios interceptor in client.ts
    // already clears it and redirects — nothing more to do here on failure).
    const token = localStorage.getItem('token')
    if (!token) {
      return
    }
    api
      .getCurrentUser()
      .then(setUser)
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const token = await api.login(email, password)
    localStorage.setItem('token', token.access_token)
    setUser(await api.getCurrentUser())
  }

  async function register(email: string, password: string) {
    await api.register(email, password)
    // POST /auth/register returns the created user, not a token (see
    // backend/app/api/routes/auth.py) — log straight in afterward so a new
    // user lands in the app immediately instead of being bounced to a
    // second, separate login form.
    await login(email, password)
  }

  function logout() {
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
