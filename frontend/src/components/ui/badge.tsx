import { type HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        {
          'bg-slate-700/50 text-slate-300': variant === 'default',
          'bg-green-500/20 text-green-400 border border-green-500/30': variant === 'success',
          'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30': variant === 'warning',
          'bg-red-500/20 text-red-400 border border-red-500/30': variant === 'danger',
          'bg-blue-500/20 text-blue-400 border border-blue-500/30': variant === 'info',
        },
        className
      )}
      {...props}
    />
  )
}
