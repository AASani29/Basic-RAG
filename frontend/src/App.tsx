import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedLayout from './auth/ProtectedLayout'
import ChatPage from './pages/ChatPage'
import ItemsPage from './pages/ItemsPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedLayout />}>
        <Route path="/items" element={<ItemsPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route index element={<Navigate to="/items" replace />} />
      </Route>

      {/* Anything unmatched falls back to the protected area, which itself
          redirects to /login if there is no session — so a bad URL never
          shows a bare blank page. */}
      <Route path="*" element={<Navigate to="/items" replace />} />
    </Routes>
  )
}
