import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedLayout from './auth/ProtectedLayout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

// Placeholder until Phase 7 adds the real ItemsPage/ChatPage. Exists so the
// route guard (ProtectedLayout) has something concrete to prove works —
// login, refresh-persists-session, and unauthenticated-redirect all need a
// protected route to land on — without pretending pages exist that don't.
function ComingSoon({ title }: { title: string }) {
  return <p className="text-gray-500">{title} — coming in the next phase.</p>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedLayout />}>
        <Route path="/items" element={<ComingSoon title="Items" />} />
        <Route path="/chat" element={<ComingSoon title="Chat" />} />
        <Route index element={<Navigate to="/items" replace />} />
      </Route>

      {/* Anything unmatched falls back to the protected area, which itself
          redirects to /login if there is no session — so a bad URL never
          shows a bare blank page. */}
      <Route path="*" element={<Navigate to="/items" replace />} />
    </Routes>
  )
}
