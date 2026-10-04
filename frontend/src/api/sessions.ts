import apiClient from './client'

export interface Session {
  session_id: string
  last_preview?: string
  message_count?: number
}

export async function listSessions(): Promise<Session[]> {
  const res = await apiClient.get('/api/v1/sessions')
  return res.data.sessions || []
}

export async function getSessionMessages(sessionId: string) {
  const res = await apiClient.get(`/api/v1/sessions/${sessionId}/messages`)
  return res.data.messages || []
}

export async function deleteSession(sessionId: string) {
  const res = await apiClient.delete(`/api/v1/sessions/${sessionId}`)
  return res.data
}
