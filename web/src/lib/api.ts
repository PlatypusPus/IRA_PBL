// Thin wrapper over the WADR API. Auth rides on an httpOnly cookie, so there
// is no token to store here and nothing for a script to steal - every call
// just needs credentials: "include".

export type User = { id: number; email: string }

export type Hit = {
  chunk_id: number
  document_id: number
  filename: string
  snippet: string
  score: number
  sender: string | null
  sent_at: string | null
  // nothing lexical matched and the embedding was only loosely close: shown as
  // a guess, not asserted as a hit
  weak: boolean
}

export type Message = {
  id: number
  role: "user" | "assistant"
  text: string
  results: Hit[]
  created_at: string
}

export type Account = {
  id: number
  label: string
  phone: string | null
  session_key: string
  status: "pending" | "linked" | "logged_out"
  documents: number
}

export type LinkState = {
  status: string
  qr?: string | null
  phone?: string | null
  pairing_code?: string
  detail?: string
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: init.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(body.detail ?? res.statusText, res.status)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const post = <T,>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) })

export const api = {
  me: () => call<User>("/api/auth/me"),
  signUp: (email: string, password: string) =>
    post<User>("/api/auth/signup", { email, password }),
  logIn: (email: string, password: string) =>
    post<User>("/api/auth/login", { email, password }),
  logOut: () => post<{ ok: boolean }>("/api/auth/logout"),

  accounts: () => call<Account[]>("/api/accounts"),
  addAccount: (label: string) => post<Account>("/api/accounts", { label }),
  linkState: (id: number) => call<LinkState>(`/api/accounts/${id}/qr`),
  pairingCode: (id: number, phone: string) =>
    post<LinkState>(`/api/accounts/${id}/pair`, { phone }),
  removeAccount: (id: number) =>
    call<{ ok: boolean }>(`/api/accounts/${id}`, { method: "DELETE" }),

  history: () => call<Message[]>("/api/chat"),
  ask: (text: string) => post<Message>("/api/chat", { text }),
  similar: (documentId: number) => call<Hit[]>(`/api/documents/${documentId}/similar`),
  fileUrl: (documentId: number) => `/api/documents/${documentId}/file`,
}
