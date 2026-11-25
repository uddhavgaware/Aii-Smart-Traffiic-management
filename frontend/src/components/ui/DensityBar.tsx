import clsx from 'clsx'

interface DensityBarProps {
  value: number // 0–100
  label?: string
  showValue?: boolean
  height?: 'sm' | 'md' | 'lg'
  className?: string
}

export function DensityBar({ value, label, showValue = true, height = 'md', className }: DensityBarProps) {
  const clamped = Math.min(100, Math.max(0, value))

  const color =
    clamped >= 80 ? 'bg-red-500'
    : clamped >= 60 ? 'bg-amber-400'
    : clamped >= 40 ? 'bg-yellow-400'
    : 'bg-emerald-400'

  const heights = { sm: 'h-1', md: 'h-2', lg: 'h-3' }

  return (
    <div className={clsx('w-full', className)}>
      {(label || showValue) && (
        <div className="flex justify-between items-center mb-1">
          {label && <span className="text-xs text-slate-500">{label}</span>}
          {showValue && (
            <span className={clsx('text-xs font-mono font-semibold',
              clamped >= 80 ? 'text-red-400' : clamped >= 60 ? 'text-amber-400' : 'text-emerald-400'
            )}>
              {clamped.toFixed(0)}%
            </span>
          )}
        </div>
      )}
      <div className={clsx('w-full bg-slate-700 rounded-full overflow-hidden', heights[height])}>
        <div
          className={clsx('h-full rounded-full transition-all duration-500', color)}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
