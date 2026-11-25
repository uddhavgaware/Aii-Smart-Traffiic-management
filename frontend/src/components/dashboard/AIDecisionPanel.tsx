import { BrainCircuit, Clock } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'

export function AIDecisionPanel() {
  const decision = useAppStore((s) => s.lastAIDecision)
  const emergency = useAppStore((s) => s.emergencyState)

  return (
    <Card
      title="AI Decision Explanation"
      subtitle="Transparent reasoning behind signal recommendations"
      headerRight={
        <Badge variant={emergency.active ? 'error' : 'cyan'} size="xs">
          <BrainCircuit className="w-3 h-3" />
          {decision?.algorithm ?? 'Safety + Adaptive Engine'}
        </Badge>
      }
    >
      {!decision ? (
        <div className="py-6 text-center text-xs text-slate-500">
          Waiting for live traffic analysis cycle from inference engine...
        </div>
      ) : (
        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-700/80">
            <p className="text-sm text-slate-100 leading-relaxed">{decision.reason}</p>
            <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400">
              <span>Action: <strong className="text-cyan-400">{decision.action}</strong></span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(decision.timestamp).toLocaleTimeString()}
              </span>
            </div>
          </div>

          {decision.metrics && Object.keys(decision.metrics).length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(decision.metrics).map(([dir, m]) => (
                <div key={dir} className="p-2 rounded bg-slate-900/60 border border-slate-800 text-xs font-mono">
                  <div className="text-slate-400 uppercase text-[10px]">{dir}</div>
                  <div className="text-slate-200 mt-0.5">Count: {m?.count ?? 0}</div>
                  <div className="text-slate-400 text-[11px]">Queue: {m?.queueLength ?? 0}%</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
