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

// --- items ---------------------------------------------------------------

export interface Item {
  id: number
  title: string
  description: string | null
  owner_id: number
  created_at: string
}

export interface ItemPage {
  items: Item[]
  total: number
  limit: number
  offset: number
}

export interface ItemCreate {
  title: string
  description?: string | null
}

export async function listItems(limit: number, offset: number): Promise<ItemPage> {
  const { data } = await apiClient.get<ItemPage>('/items', { params: { limit, offset } })
  return data
}

export async function createItem(payload: ItemCreate): Promise<Item> {
  const { data } = await apiClient.post<Item>('/items', payload)
  return data
}

export async function deleteItem(id: number): Promise<void> {
  await apiClient.delete(`/items/${id}`)
}

// --- rag -------------------------------------------------------------------

export interface SourceChunk {
  filename: string
  chunk_index: number
  content: string
}

export interface ChatResponse {
  answer: string
  sources: SourceChunk[]
}

export interface UploadResponse {
  filename: string
  chunk_count: number
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  // No explicit Content-Type header: axios sets `multipart/form-data` with
  // the correct boundary itself when the body is a FormData instance.
  // Setting it manually here would omit that boundary (it's generated per
  // request) and silently break the upload.
  const { data } = await apiClient.post<UploadResponse>('/rag/documents', form)
  return data
}

export async function chat(question: string): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>('/rag/chat', { question })
  return data
}
