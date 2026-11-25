import clsx from 'clsx'
import { Direction, SignalState } from '../../store/appStore'
import { Badge } from '../ui/Badge'
import { CountdownTimer } from '../ui/CountdownTimer'

interface TrafficSignalProps {
  direction: Direction
  signal: SignalState
  onSelect?: (direction: Direction) => void
}

export function TrafficSignal({ direction, signal, onSelect }: TrafficSignalProps) {
  const modeVariant =
    signal.mode === 'EMERGENCY'
      ? 'error'
      : signal.mode === 'MANUAL'
      ? 'warning'
      : 'cyan'

  return (
    <div
      onClick={() => onSelect?.(direction)}
      className={clsx(
        'card p-3 flex flex-col items-center gap-2.5',
        onSelect && 'cursor-pointer card-hover',
        signal.phase === 'GREEN' && 'border-emerald-500/40',
        signal.phase === 'YELLOW' && 'border-amber-500/40',
        signal.mode === 'EMERGENCY' && 'border-red-500/50'
      )}
    >
      <div className="w-full flex items-center justify-between">
        <span className="text-xs font-bold uppercase font-mono text-slate-300">
          {direction}
        </span>
        <Badge variant={modeVariant} size="xs">
          {signal.mode}
        </Badge>
      </div>

      {/* Physical signal housing */}
      <div className="bg-slate-950 border border-slate-800 rounded-2xl p-2.5 flex flex-col gap-2 shadow-inner">
        <div
          className={clsx(
            'signal-light',
            signal.phase === 'RED' ? 'active-red' : 'inactive'
          )}
          aria-label={`${direction} red light`}
        />
        <div
          className={clsx(
            'signal-light',
            signal.phase === 'YELLOW' ? 'active-amber' : 'inactive'
          )}
          aria-label={`${direction} yellow light`}
        />
        <div
          className={clsx(
            'signal-light',
            signal.phase === 'GREEN' ? 'active-green' : 'inactive'
          )}
          aria-label={`${direction} green light`}
        />
      </div>

      <CountdownTimer seconds={signal.countdown} phase={signal.phase} size="md" />

      <div className="w-full pt-1.5 border-t border-slate-800 text-[11px] flex justify-between text-slate-400 font-mono">
        <span>Next: {signal.nextPhase}</span>
        <span>Rec: {signal.recommendedGreen}s</span>
      </div>
    </div>
  )
}
