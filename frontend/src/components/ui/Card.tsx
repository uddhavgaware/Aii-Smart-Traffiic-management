import clsx from 'clsx'
import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
  subtitle?: string
  headerRight?: ReactNode
  noPadding?: boolean
  glowColor?: 'cyan' | 'red' | 'green' | 'amber' | null
}

export function Card({ children, className, title, subtitle, headerRight, noPadding, glowColor }: CardProps) {
  return (
    <div
      className={clsx(
        'bg-slate-800/50 border border-slate-700 rounded-xl backdrop-blur-sm transition-all duration-200',
        glowColor === 'cyan' && 'border-cyan-500/50 shadow-glow-cyan',
        glowColor === 'red' && 'border-red-500/50 shadow-glow-red',
        glowColor === 'green' && 'border-emerald-500/50 shadow-glow-green',
        glowColor === 'amber' && 'border-amber-500/50 shadow-glow-amber',
        className
      )}
    >
      {(title || headerRight) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
            {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
          {headerRight && <div>{headerRight}</div>}
        </div>
      )}
      <div className={noPadding ? '' : 'p-4'}>{children}</div>
    </div>
  )
}
