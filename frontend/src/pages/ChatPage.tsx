import { useState, useRef, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import AppLayout from '@/components/layout/AppLayout'
import ChatMessage from '@/components/chat/ChatMessage'
import ChatInput from '@/components/chat/ChatInput'
import { useChat } from '@/hooks/useChat'
import { getSessionMessages } from '@/api/sessions'

export default function ChatPage() {
  const [sessionId, setSessionId] = useState(() => uuidv4())
  const { messages, setMessages, isStreaming, sendMessage, stopGeneration, clearMessages } = useChat(sessionId)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleNewChat = () => {
    setSessionId(uuidv4())
    clearMessages()
  }

  const handleSelectSession = async (id: string) => {
    setSessionId(id)
    try {
      const msgs = await getSessionMessages(id)
      setMessages(msgs)
    } catch (err) {
      console.error("Failed to load session", err)
      clearMessages()
    }
  }

  return (
    <AppLayout 
      onNewChat={handleNewChat}
      activeSessionId={sessionId}
      onSelectSession={handleSelectSession}
    >
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 lg:px-16 xl:px-32">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <img src="/logo.png" alt="Logo" className="w-20 h-20 mb-4 object-contain opacity-80" />
            <h2 className="text-2xl font-semibold text-slate-200 mb-2">Support Docs Copilot</h2>
            <p className="text-slate-400 max-w-md">
              Ask any question about our product documentation. I'll find the most relevant answer with source citations.
            </p>
            <div className="flex flex-wrap gap-2 mt-6 justify-center">
              {['How do I reset my password?', 'What file formats are supported?', 'How do I contact support?'].map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="px-3 py-2 text-sm rounded-lg border border-white/10 text-slate-400 hover:text-slate-200 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="py-4">
            {messages.map((msg, i) => (
              <ChatMessage key={i} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="px-4 md:px-8 lg:px-16 xl:px-32 pb-4">
        <ChatInput
          onSend={sendMessage}
          onStop={stopGeneration}
          isStreaming={isStreaming}
        />
      </div>
    </AppLayout>
  )
}
