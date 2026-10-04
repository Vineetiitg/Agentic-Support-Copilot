export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: SourceCitation[]
  confidence?: number
  isStreaming?: boolean
}

export interface SourceCitation {
  source: string
  page?: number
  chunk_id?: string
  doc_id?: string
  snippet: string
}

export interface ChatResponse {
  query: string
  answer: string
  sources: SourceCitation[]
  confidence: number
  session_id: string
}
