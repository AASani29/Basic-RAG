import apiClient from './client'

// Types mirror the backend's Pydantic schemas field-for-field (see
// backend/app/schemas/). Kept here next to the functions that return them
// rather than in a separate types file — there is exactly one place either
// is used.

export interface User {
  id: number
  email: string
}

interface Token {
  access_token: string
  token_type: string
}

// --- auth --------------------------------------------------------------

export async function register(email: string, password: string): Promise<User> {
  const { data } = await apiClient.post<User>('/auth/register', { email, password })
  return data
}

export async function login(email: string, password: string): Promise<Token> {
  // OAuth2's password grant (which the backend's OAuth2PasswordRequestForm
  // implements) expects form-encoded `username`/`password` fields, not
  // JSON — that field naming is the spec's, not a choice made here.
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)
  const { data } = await apiClient.post<Token>('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>('/auth/me')
  return data
}
