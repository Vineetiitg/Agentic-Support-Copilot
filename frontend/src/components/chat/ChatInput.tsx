import { useState, useRef, useEffect } from 'react'
import { Send, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  onSend: (message: string) => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
}

export default function ChatInput({ onSend, onStop, isStreaming, disabled }: Props) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
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
