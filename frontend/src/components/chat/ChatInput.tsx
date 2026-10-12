import { useState, useRef, useEffect } from 'react'
import { Send, Square, Globe } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Props {
  onSend: (message: string, enableWebSearch?: boolean) => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
  webSearchEnabled?: boolean
  onToggleWebSearch?: (enabled: boolean) => void
}

export default function ChatInput({ onSend, onStop, isStreaming, disabled, webSearchEnabled: initialWebSearch, onToggleWebSearch }: Props) {
  const [input, setInput] = useState('')
  const [webSearch, setWebSearch] = useState(initialWebSearch ?? false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (initialWebSearch !== undefined) {
      setWebSearch(initialWebSearch)
    }
  }, [initialWebSearch])

  const toggleSearch = () => {
    const nextVal = !webSearch
    setWebSearch(nextVal)
    onToggleWebSearch?.(nextVal)
  }

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed, webSearch)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="glass-card p-3">
      {/* Control bar with Web Search toggle */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/5">
        <button
          type="button"
          onClick={toggleSearch}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-200 cursor-pointer",
            webSearch
              ? "bg-purple-600/30 text-purple-300 border border-purple-500/50 shadow-sm shadow-purple-500/20"
              : "bg-white/5 text-slate-400 hover:text-slate-300 border border-white/10 hover:bg-white/10"
          )}
          title={webSearch ? "Web Search Fallback is ON (Tavily)" : "Web Search Fallback is OFF (Local Docs Only)"}
        >
          <Globe size={13} className={webSearch ? "text-purple-400 animate-pulse" : "text-slate-500"} />
          <span>Web Search: <strong className={webSearch ? "text-purple-300" : "text-slate-400"}>{webSearch ? "ON" : "OFF"}</strong></span>
        </button>

        <span className="text-[11px] text-slate-500">
          {webSearch ? "🌐 Searches web if docs insufficient" : "🔒 Strict local documentation only"}
        </span>
      </div>

      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a support question..."
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent text-slate-200 placeholder:text-slate-500 text-sm focus:outline-none min-h-[40px] max-h-[150px] py-2"
        />
        {isStreaming ? (
          <Button variant="destructive" size="icon" onClick={onStop} title="Stop generation">
            <Square size={16} />
          </Button>
        ) : (
          <Button size="icon" onClick={handleSubmit} disabled={!input.trim() || disabled} title="Send message">
            <Send size={16} />
          </Button>
        )}
      </div>
      <p className="text-[10px] text-slate-600 mt-1.5 text-right">Shift+Enter for new line</p>
    </div>
  )
}
