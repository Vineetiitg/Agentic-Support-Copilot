import { useState, createContext, useContext, useCallback, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { X } from 'lucide-react'

type ToastType = 'success' | 'error' | 'info'
interface Toast { id: number; message: string; type: ToastType }

const ToastContext = createContext<{ toast: (message: string, type?: ToastType) => void }>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  let nextId = 0

  const addToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = ++nextId
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

  const removeToast = (id: number) => setToasts(prev => prev.filter(t => t.id !== id))

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={cn(
              'flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border animate-in slide-in-from-right',
              {
                'bg-green-900/80 border-green-500/30 text-green-200': t.type === 'success',
                'bg-red-900/80 border-red-500/30 text-red-200': t.type === 'error',
                'bg-slate-800/80 border-slate-600/30 text-slate-200': t.type === 'info',
              }
            )}
          >
            <span className="text-sm">{t.message}</span>
            <button onClick={() => removeToast(t.id)} className="ml-2 opacity-60 hover:opacity-100">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
