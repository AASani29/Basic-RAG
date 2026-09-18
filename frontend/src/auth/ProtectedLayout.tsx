import { Link, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

// Combines the route guard AND the page chrome (nav bar) in one component,
// rather than a separate "guard" wrapper around a separate "layout" — a
// layout that only ever renders inside the guard is the same component
// wearing two names, and splitting them would be an abstraction with one
// implementation.
export default function ProtectedLayout() {
  const { user, isLoading, logout } = useAuth()

  // Waiting on AuthContext's bootstrap /auth/me call. Redirecting before it
  // resolves would bounce an already-logged-in user straight back to
  // /login on every single page refresh.
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-gray-500">Loading…</div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="flex items-center justify-between border-b bg-white px-6 py-4">
        <div className="flex gap-6">
          <Link to="/items" className="font-medium text-gray-900 hover:underline">
            Items
          </Link>
          <Link to="/chat" className="font-medium text-gray-900 hover:underline">
            Chat
          </Link>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">{user.email}</span>
          <button type="button" onClick={logout} className="text-sm text-red-600 hover:underline">
            Log out
          </button>
        </div>
      </nav>
      <main className="mx-auto max-w-4xl p-6">
        <Outlet />
      </main>
    </div>
  )
}
