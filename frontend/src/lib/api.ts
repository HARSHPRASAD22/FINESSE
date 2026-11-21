export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
export const ACCESS_REQUIRED_EVENT = 'permitpilot:access-required'

function notifyUnauthorized(response: Response) {
  if (response.status === 401) {
    window.dispatchEvent(new Event(ACCESS_REQUIRED_EVENT))
  }
}

let activeWorkspaceId: string | null = null

export function setActiveWorkspaceId(workspaceId: string | null) {
  activeWorkspaceId = workspaceId
  if (workspaceId) localStorage.setItem('permitpilot-workspace-id', workspaceId)
  else localStorage.removeItem('permitpilot-workspace-id')
}

export function getWorkspaceId() {
  if (activeWorkspaceId) return activeWorkspaceId
  const storedWorkspaceId = localStorage.getItem('permitpilot-workspace-id')
  if (!storedWorkspaceId) throw new Error('Workspace not initialized')
  activeWorkspaceId = storedWorkspaceId
  return storedWorkspaceId
}

export async function getActiveBusinessId(): Promise<string | null> {
  const workspaceId = getWorkspaceId()
  const data = await api<{items:any[]}>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/businesses`)
  return data.items[0]?.id || null
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'same-origin',
    headers,
  })
  if (!response.ok) {
    notifyUnauthorized(response)
    const detail = await response.text()
    let message = detail
    try {
      const parsed = JSON.parse(detail)
      message = parsed.detail || parsed.message || detail
    } catch {
      // Keep the raw response text as the user-facing error.
    }
    throw new Error(typeof message === 'string' ? message : `Request failed with status ${response.status}`)
  }
  return response.json()
}

export async function uploadFile(path: string, file: File): Promise<any> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_BASE}${path}`, { method: 'POST', body: form, credentials: 'same-origin' })
  if (!response.ok) {
    notifyUnauthorized(response)
    throw new Error(await response.text())
  }
  return response.json()
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { method: 'GET', credentials: 'same-origin' })
  if (!response.ok) {
    notifyUnauthorized(response)
    throw new Error(await response.text())
  }
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export async function downloadPostFile(path: string, filename: string, body: unknown): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    notifyUnauthorized(response)
    const detail = await response.text()
    let message = detail
    try {
      const parsed = JSON.parse(detail)
      message = parsed.detail || parsed.message || detail
    } catch {
      // Keep the raw response text as the user-facing error.
    }
    throw new Error(typeof message === 'string' ? message : `Request failed with status ${response.status}`)
  }
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}
