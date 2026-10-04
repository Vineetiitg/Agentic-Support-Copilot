import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { User, Bot } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatMessage as ChatMessageType } from '@/types/chat'
import TypingIndicator from './TypingIndicator'

interface Props {
  message: ChatMessageType
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex gap-3 py-4', isUser ? 'flex-row-reverse' : 'flex-row')}>
      <div className={cn(
        'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
        isUser ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
      )}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      <div className={cn(
        'max-w-[75%] rounded-2xl px-4 py-3',
        isUser
          ? 'bg-blue-600/20 border border-blue-500/20 text-slate-200'
          : 'glass-card text-slate-300'
      )}>
        {message.isStreaming && !message.content ? (
          <TypingIndicator />
        ) : (
          <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:text-slate-200 prose-code:text-purple-300 prose-code:bg-white/5 prose-code:px-1 prose-code:rounded">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {message.confidence !== undefined && message.confidence > 0 && (
          <div className="mt-2 pt-2 border-t border-white/5">
            <span className={cn(
              'text-xs px-2 py-0.5 rounded-full',
              message.confidence >= 0.8 ? 'bg-green-500/20 text-green-400' :
              message.confidence >= 0.5 ? 'bg-yellow-500/20 text-yellow-400' :
              'bg-red-500/20 text-red-400'
            )}>
              Confidence: {(message.confidence * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
