import { useState } from 'react'
import { ThumbsUp, ThumbsDown } from 'lucide-react'
import apiClient from '@/api/client'

interface Props {
  query: string
  answer: string
}

export default function FeedbackButtons({ query, answer }: Props) {
  const [submitted, setSubmitted] = useState<'positive' | 'negative' | null>(null)

  const handleFeedback = async (isPositive: boolean) => {
    try {
      await apiClient.post('/chat/feedback', {
        query,
        answer: answer.slice(0, 500),
        is_positive: isPositive,
      })
      setSubmitted(isPositive ? 'positive' : 'negative')
    } catch (err) {
      console.error('Feedback submission failed:', err)
    }
  }

  if (submitted) {
    return (
      <span className="text-xs text-slate-500">
        {submitted === 'positive' ? '👍 Thanks!' : '👎 We\'ll improve'}
      </span>
    )
  }

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => handleFeedback(true)}
        className="p-1 rounded hover:bg-green-500/10 text-slate-500 hover:text-green-400 transition-colors"
        title="Helpful"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        onClick={() => handleFeedback(false)}
        className="p-1 rounded hover:bg-red-500/10 text-slate-500 hover:text-red-400 transition-colors"
        title="Not helpful"
      >
        <ThumbsDown size={14} />
      </button>
    </div>
  )
}
