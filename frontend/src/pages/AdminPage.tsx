import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Trash2, Upload, RefreshCw, Play, Loader2 } from 'lucide-react'
import AppLayout from '@/components/layout/AppLayout'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/toast'
import { getDocuments, ingestDocuments, uploadFiles, deleteDocument, resetIndex, getEvalReport, runEvaluation } from '@/api/admin'

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<'documents' | 'evaluation'>('documents')
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const tabs = [
    { id: 'documents' as const, label: 'Documents', icon: FileText },
    { id: 'evaluation' as const, label: 'Evaluation', icon: Play },
  ]

  return (
    <AppLayout>
      <div className="p-6 overflow-y-auto">
        <h2 className="text-2xl font-bold text-slate-100 mb-6">Admin Dashboard</h2>

        {/* Tab bar */}
        <div className="flex gap-1 mb-6 p-1 rounded-lg bg-white/5 w-fit">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                activeTab === id
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>

        {activeTab === 'documents' && <DocumentsTab toast={toast} queryClient={queryClient} />}
        {activeTab === 'evaluation' && <EvaluationTab toast={toast} />}
      </div>
    </AppLayout>
  )
}

function DocumentsTab({ toast, queryClient }: { toast: any; queryClient: any }) {
  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: getDocuments,
  })

  const ingestMutation = useMutation({
    mutationFn: () => ingestDocuments(),
    onSuccess: () => {
      toast('Ingestion started successfully', 'success')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: () => toast('Ingestion failed', 'error'),
  })

  const resetMutation = useMutation({
    mutationFn: resetIndex,
    onSuccess: () => {
      toast('Index reset successfully', 'success')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: () => toast('Reset failed', 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      toast('Document deleted', 'success')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    try {
      await uploadFiles(files)
      toast(`Uploaded ${files.length} file(s)`, 'success')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    } catch {
      toast('Upload failed', 'error')
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Indexed Documents</CardTitle>
          <div className="flex gap-2">
            <label className="cursor-pointer">
              <input type="file" multiple className="hidden" onChange={handleUpload} />
              <span className="inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 border border-white/10 hover:bg-white/5 text-slate-300 h-8 px-3 text-xs">
                <Upload size={14} className="mr-1" /> Upload
              </span>
            </label>
            <Button
              variant="outline"
              size="sm"
              onClick={() => ingestMutation.mutate()}
              disabled={ingestMutation.isPending}
            >
              {ingestMutation.isPending ? <Loader2 size={14} className="mr-1 animate-spin" /> : <RefreshCw size={14} className="mr-1" />}
              Ingest
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => { if (confirm('Reset the entire index?')) resetMutation.mutate() }}
              disabled={resetMutation.isPending}
            >
              Reset Index
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-slate-500">Loading documents...</p>
        ) : !documents?.length ? (
          <p className="text-slate-500">No documents indexed yet. Upload files and run ingestion.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-white/5">
                  <th className="pb-2 font-medium">Source</th>
                  <th className="pb-2 font-medium">Doc ID</th>
                  <th className="pb-2 font-medium">Chunks</th>
                  <th className="pb-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc: any, i: number) => (
                  <tr key={i} className="border-b border-white/5">
                    <td className="py-2 text-slate-300">{doc.source || doc.file_name || 'Unknown'}</td>
                    <td className="py-2"><Badge>{(doc.doc_id || '').slice(0, 8)}</Badge></td>
                    <td className="py-2 text-slate-400">{doc.chunks || doc.chunk_count || '—'}</td>
                    <td className="py-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteMutation.mutate(doc.doc_id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        <Trash2 size={14} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function EvaluationTab({ toast }: { toast: any }) {
  const { data: evalData, isLoading } = useQuery({
    queryKey: ['eval'],
    queryFn: getEvalReport,
  })

  const evalMutation = useMutation({
    mutationFn: runEvaluation,
    onSuccess: () => toast('Evaluation started', 'success'),
    onError: () => toast('Evaluation failed', 'error'),
  })

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>RAGAS Evaluation</CardTitle>
          <Button
            onClick={() => evalMutation.mutate()}
            disabled={evalMutation.isPending}
            size="sm"
          >
            {evalMutation.isPending ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Play size={14} className="mr-1" />}
            Run Evaluation
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-slate-500">Loading report...</p>
        ) : evalData?.report ? (
          <pre className="text-sm text-slate-300 bg-black/20 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap">
            {evalData.report}
          </pre>
        ) : (
          <p className="text-slate-500">No evaluation report yet. Click "Run Evaluation" to generate one.</p>
        )}
      </CardContent>
    </Card>
  )
}
