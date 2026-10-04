export interface DocumentInfo {
  doc_id: string
  source: string
  chunks: number
  file_hash?: string
}

export interface EvalReport {
  status: string
  report?: string
}
