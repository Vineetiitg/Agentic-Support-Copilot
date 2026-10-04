import { useQuery } from '@tanstack/react-query'
import { MessageSquare, Trash2 } from 'lucide-react'
import { listSessions, deleteSession } from '@/api/sessions'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface Props {
  activeSessionId: string
  onSelectSession: (sessionId: string, messages: any[]) => void
}

export default function SessionList({ activeSessionId, onSelectSession }: Props) {
  const { data: sessions, isLoading, refetch } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
    refetchInterval: 30000, // refresh every 30s
  })

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    try {
      await deleteSession(sessionId)
      refetch()
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-2 p-1">
        {[1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-full" />)}
      </div>
    )
  }

  if (!sessions?.length) {
    return (
      <p className="text-xs text-slate-500 px-2 py-4 text-center">
        No previous sessions
      </p>
    )
  }

  return (
    <div className="space-y-0.5">
      {sessions.slice(0, 15).map((session) => (
        <div
          key={session.session_id}
          onClick={() => onSelectSession(session.session_id, [])}
          className={cn(
            'group flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-sm transition-all',
            session.session_id === activeSessionId
              ? 'bg-purple-500/10 text-purple-300'
              : 'text-slate-400 hover:bg-white/5 hover:text-slate-300'
          )}
        >
          <MessageSquare size={14} className="flex-shrink-0" />
          <span className="flex-1 truncate">
            {session.last_preview || session.session_id.slice(0, 12) + '...'}
          </span>
          <button
            onClick={(e) => handleDelete(e, session.session_id)}
            className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-opacity"
            title="Delete session"
          >
            <Trash2 size={12} />
          </button>
        </div>
      ))}
    </div>
  )
}
