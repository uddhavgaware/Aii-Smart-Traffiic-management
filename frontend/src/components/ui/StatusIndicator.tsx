import clsx from 'clsx'

type Status = 'online' | 'offline' | 'degraded' | 'connecting' | 'error' | 'running' | 'stopped' | 'connected' | 'disconnected'

interface StatusIndicatorProps {
  status: Status | boolean
  label?: string
  size?: 'xs' | 'sm' | 'md'
  showLabel?: boolean
  pulse?: boolean
}

export function StatusIndicator({ status, label, size = 'sm', showLabel = true, pulse }: StatusIndicatorProps) {
  const isPositive = status === true || status === 'online' || status === 'running' || status === 'connected'
  const isWarning = status === 'degraded' || status === 'connecting'
  const isNegative = status === false || status === 'offline' || status === 'stopped' || status === 'error' || status === 'disconnected'

  const dotSize = { xs: 'w-1.5 h-1.5', sm: 'w-2 h-2', md: 'w-2.5 h-2.5' }
  const textSize = { xs: 'text-xs', sm: 'text-xs', md: 'text-sm' }

  const dotColor = isPositive
    ? 'bg-emerald-400'
    : isWarning
    ? 'bg-amber-400'
    : 'bg-red-500'

  const textColor = isPositive
    ? 'text-emerald-400'
    : isWarning
    ? 'text-amber-400'
    : 'text-red-400'

  const statusText = typeof status === 'boolean'
    ? status ? 'Online' : 'Offline'
    : status.charAt(0).toUpperCase() + status.slice(1)

  return (
    <div className="flex items-center gap-1.5">
      <span className={clsx(dotSize[size], dotColor, 'rounded-full', (pulse ?? isPositive) && 'animate-pulse')} />
      {showLabel && (
        <span className={clsx(textSize[size], textColor, 'font-medium')}>
          {label ?? statusText}
        </span>
      )}
    </div>
  )
}
