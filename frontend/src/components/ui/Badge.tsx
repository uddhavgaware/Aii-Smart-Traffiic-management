import clsx from 'clsx'

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'cyan' | 'purple'
type BadgeSize = 'xs' | 'sm' | 'md'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  size?: BadgeSize
  dot?: boolean
  pulse?: boolean
  className?: string
}

export function Badge({ children, variant = 'default', size = 'sm', dot, pulse, className }: BadgeProps) {
  const variants: Record<BadgeVariant, string> = {
    default: 'bg-slate-700 text-slate-300 border-slate-600',
    success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    warning: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    error: 'bg-red-500/20 text-red-400 border-red-500/40',
    info: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    cyan: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    purple: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
  }

  const dotColors: Record<BadgeVariant, string> = {
    default: 'bg-slate-400',
    success: 'bg-emerald-400',
    warning: 'bg-amber-400',
    error: 'bg-red-400',
    info: 'bg-blue-400',
    cyan: 'bg-cyan-400',
    purple: 'bg-purple-400',
  }

  const sizes: Record<BadgeSize, string> = {
    xs: 'px-1.5 py-0.5 text-xs',
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  }

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 font-medium rounded-full border',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {dot && (
        <span
          className={clsx(
            'w-1.5 h-1.5 rounded-full',
            dotColors[variant],
            pulse && 'animate-pulse'
          )}
        />
      )}
      {children}
    </span>
  )
}
