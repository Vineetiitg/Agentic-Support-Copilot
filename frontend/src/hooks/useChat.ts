import { useState, useCallback, useRef } from 'react'
import type { ChatMessage } from '@/types/chat'
import { useAuthStore } from '@/stores/authStore'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const token = useAuthStore((s) => s.token)

  const sendMessage = useCallback(async (query: string) => {
    // Add user message immediately
    const userMsg: ChatMessage = { role: 'user', content: query }
    setMessages((prev) => [...prev, userMsg])

    // Add placeholder assistant message
    const assistantMsg: ChatMessage = { role: 'assistant', content: '', isStreaming: true }
    setMessages((prev) => [...prev, assistantMsg])

    setIsStreaming(true)
    abortRef.current = new AbortController()

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query, session_id: sessionId }),
        signal: abortRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullText = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const chunk = decoder.decode(value, { stream: true })
          fullText += chunk
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') {
              updated[updated.length - 1] = { ...last, content: fullText }
            }
            return updated
          })
        }
      }

      // Finalize the message
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last.role === 'assistant') {
          updated[updated.length - 1] = { ...last, isStreaming: false }
        }
        return updated
      })
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + '\n\n🛑 *Generation stopped by user.*',
              isStreaming: false,
            }
          }
          return updated
        })
      } else {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: `⚠️ Error: ${err.message}`,
              isStreaming: false,
            }
          }
          return updated
        })
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [sessionId, token])

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return { messages, setMessages, isStreaming, sendMessage, stopGeneration, clearMessages }
}
