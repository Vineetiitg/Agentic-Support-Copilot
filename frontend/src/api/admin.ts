import apiClient from './client'

export async function getDocuments() {
  const res = await apiClient.get('/documents')
  return res.data.documents || []
}

export async function ingestDocuments(dataDir: string = 'data/docs', force: boolean = false) {
  const res = await apiClient.post('/admin/ingest', { data_dir: dataDir, force })
  return res.data
}

export async function uploadFiles(files: File[]) {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  const res = await apiClient.post('/admin/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function deleteDocument(docId: string) {
  const res = await apiClient.delete(`/admin/documents/${docId}`)
  return res.data
}

export async function resetIndex() {
  const res = await apiClient.post('/admin/reset')
  return res.data
}

export async function getEvalReport() {
  const res = await apiClient.get('/admin/eval')
  return res.data
}

export async function runEvaluation() {
  const res = await apiClient.post('/admin/eval')
  return res.data
}

export async function getSessions() {
  const res = await apiClient.get('/api/v1/admin/sessions')
  return res.data.sessions || []
}

export async function getSessionMessages(userId: string, sessionId: string) {
  const res = await apiClient.get(`/api/v1/admin/sessions/${userId}/${sessionId}/messages`)
  return res.data
}

export async function injectMessage(userId: string, sessionId: string, message: string) {
  const res = await apiClient.post(`/api/v1/admin/sessions/${userId}/${sessionId}/message`, {
    message,
    role: 'supervisor'
  })
  return res.data
}
