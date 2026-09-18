import axios from 'axios'

// One axios instance for the whole app. Every typed endpoint function in
// endpoints.ts imports and calls this instance, so the auth header and
// 401 handling below apply everywhere automatically, instead of being
// repeated at every call site.
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

// Attaches the JWT to every outgoing request. Reads localStorage on each
// request rather than once at module load, so a token written moments ago
// (e.g. right after login) is picked up by the very next call without
// needing to rebuild the client.
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// A 401 means the token is missing, expired, or invalid — in every case the
// correct response is the same: drop it and send the user to /login. This
// is the one place that logic lives, instead of every page having to check
// for 401 itself.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      localStorage.removeItem('token')
      // A hard navigation, not react-router's navigate(): this interceptor
      // runs outside any component or route context, so there is no
      // navigate() to call here — and reloading the page also resets
      // AuthContext's in-memory user state, not just the stored token.
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

/** Pulls the backend's own error message out of its one error shape
 * ({"error": {"code", "message", "details"}}) — see backend/app/main.py.
 * Falls back to a generic message for network failures or anything that
 * isn't shaped like our API's errors at all. */
export function getErrorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.error?.message
    if (typeof message === 'string') {
      return message
    }
  }
  return fallback
}

export default apiClient
