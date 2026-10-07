import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Trash2, Upload, RefreshCw, Play, Loader2, Activity, User, Bot, Crown, Send } from 'lucide-react'
import AppLayout from '@/components/layout/AppLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/toast'
import { getDocuments, ingestDocuments, uploadFiles, deleteDocument, resetIndex, getEvalReport, runEvaluation, getSessions, getSessionMessages, injectMessage, getTaskStatus } from '@/api/admin'

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<'sessions' | 'documents' | 'evaluation'>('sessions')
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const tabs = [
    { id: 'sessions' as const, label: 'Live Sessions', icon: Activity },
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

        {activeTab === 'sessions' && <SessionsTab toast={toast} queryClient={queryClient} />}
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
  const queryClient = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)

  const { data: evalData, isLoading } = useQuery({
    queryKey: ['eval'],
    queryFn: getEvalReport,
  })

  const evalMutation = useMutation({
    mutationFn: runEvaluation,
    onSuccess: (data) => {
      toast('Evaluation started', 'success')
      if (data.job_id) {
        setJobId(data.job_id)
      }
    },
    onError: () => toast('Evaluation failed', 'error'),
  })

  const { data: taskData } = useQuery({
    queryKey: ['task', jobId],
    queryFn: () => getTaskStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'completed' || status === 'failed') return false
      return 2000
    },
  })

  useEffect(() => {
    if (taskData?.status === 'completed') {
      toast('Evaluation completed', 'success')
      queryClient.invalidateQueries({ queryKey: ['eval'] })
      setJobId(null)
    } else if (taskData?.status === 'failed') {
      toast('Evaluation failed: ' + (taskData.error || 'Unknown error'), 'error')
      setJobId(null)
    }
  }, [taskData?.status, taskData?.error, toast, queryClient])

  const isPolling = !!jobId && taskData?.status !== 'completed' && taskData?.status !== 'failed'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>RAGAS Evaluation</CardTitle>
          <Button
            onClick={() => evalMutation.mutate()}
            disabled={evalMutation.isPending || isPolling}
            size="sm"
          >
            {(evalMutation.isPending || isPolling) ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Play size={14} className="mr-1" />}
            {isPolling ? 'Running...' : 'Run Evaluation'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-slate-500">Loading report...</p>
        ) : isPolling ? (
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 size={32} className="animate-spin text-purple-500 mb-4" />
            <p className="text-slate-400 mb-2">Evaluation in progress...</p>
          </div>
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
function SessionsTab({ toast, queryClient }: { toast: any; queryClient: any }) {
  const [selectedSession, setSelectedSession] = useState<any>(null)
  const [injectText, setInjectText] = useState('')

  const { data: sessions, isLoading: loadingSessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: getSessions,
    refetchInterval: 5000,
  })

  const { data: sessionData, isLoading: loadingMessages } = useQuery({
    queryKey: ['sessionMessages', selectedSession?.user_id, selectedSession?.session_id],
    queryFn: () => getSessionMessages(selectedSession.user_id, selectedSession.session_id),
    enabled: !!selectedSession,
    refetchInterval: 3000,
  })

  const injectMutation = useMutation({
    mutationFn: () => injectMessage(selectedSession.user_id, selectedSession.session_id, injectText),
    onSuccess: () => {
      toast('Message injected', 'success')
      setInjectText('')
      queryClient.invalidateQueries({ queryKey: ['sessionMessages'] })
    },
    onError: () => toast('Failed to inject message', 'error'),
  })

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <Card className="md:col-span-1 h-[calc(100vh-12rem)] overflow-hidden flex flex-col">
        <CardHeader className="py-4 border-b border-white/5 shrink-0">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Active Threads</CardTitle>
            <Button variant="ghost" size="icon" onClick={() => queryClient.invalidateQueries({ queryKey: ['sessions'] })}>
              <RefreshCw size={14} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto p-2">
          {loadingSessions ? (
            <div className="p-4 text-center text-slate-500">Loading sessions...</div>
          ) : !sessions?.length ? (
            <div className="p-4 text-center text-slate-500">No active sessions</div>
          ) : (
            <div className="space-y-1">
              {sessions.map((s: any) => (
                <button
                  key={s.session_id}
                  onClick={() => setSelectedSession(s)}
                  className={`w-full text-left p-3 rounded-lg transition-all ${
                    selectedSession?.session_id === s.session_id
                      ? 'bg-purple-500/20 border border-purple-500/30'
                      : 'hover:bg-white/5 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <User size={14} className="text-blue-400" />
                    <span className="text-sm font-medium text-slate-200">{s.user_id}</span>
                  </div>
                  <p className="text-xs text-slate-400 truncate">{s.last_preview || 'New Session'}</p>
                  <p className="text-[10px] text-slate-500 mt-2">
                    {new Date((s.updated_at || Date.now() / 1000) * 1000).toLocaleTimeString()}
                  </p>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="md:col-span-2 h-[calc(100vh-12rem)] overflow-hidden flex flex-col">
        {selectedSession ? (
          <>
            <CardHeader className="py-4 border-b border-white/5 shrink-0">
              <CardTitle className="text-base">Thread: {selectedSession.session_id.slice(0, 8)}</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
              {sessionData?.summary && (
                <div className="p-3 rounded-lg bg-blue-500/10 border-l-2 border-blue-500 mb-6">
                  <p className="text-xs font-semibold text-blue-400 mb-1">Background Memory Summary</p>
                  <p className="text-sm text-slate-300">{sessionData.summary}</p>
                </div>
              )}
              
              {loadingMessages ? (
                <div className="text-center text-slate-500">Loading messages...</div>
              ) : sessionData?.messages?.map((msg: any, i: number) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                    msg.role === 'user' ? 'bg-blue-500/20 text-blue-400' :
                    msg.role === 'supervisor' ? 'bg-amber-500/20 text-amber-400' :
                    'bg-purple-500/20 text-purple-400'
                  }`}>
                    {msg.role === 'user' ? <User size={14} /> : msg.role === 'supervisor' ? <Crown size={14} /> : <Bot size={14} />}
                  </div>
                  <div className={`max-w-[80%] p-3 rounded-xl text-sm ${
                    msg.role === 'user' ? 'bg-blue-600/20 border border-blue-500/20 text-slate-200' :
                    msg.role === 'supervisor' ? 'bg-amber-500/10 border border-amber-500/20 text-amber-200 font-medium' :
                    'bg-white/5 border border-white/10 text-slate-300'
                  }`}>
                    {msg.content}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-white/5">
                        <p className="text-[10px] text-slate-400 mb-1">Cited {msg.sources.length} sources (Confidence: {((msg.confidence || 0) * 100).toFixed(0)}%)</p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
            <div className="p-4 border-t border-white/5 shrink-0 bg-black/20">
              <div className="flex gap-2">
                <Input
                  value={injectText}
                  onChange={(e) => setInjectText(e.target.value)}
                  placeholder="Inject a supervisor message into this thread..."
                  onKeyDown={(e) => e.key === 'Enter' && injectText && injectMutation.mutate()}
                  className="bg-white/5"
                />
                <Button 
                  onClick={() => injectMutation.mutate()} 
                  disabled={!injectText || injectMutation.isPending}
                  className="bg-amber-600 hover:bg-amber-700 text-white"
                >
                  <Send size={14} className="mr-2" /> Inject
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500">
            Select a session from the list to view history
          </div>
        )}
      </Card>
    </div>
  )
}
