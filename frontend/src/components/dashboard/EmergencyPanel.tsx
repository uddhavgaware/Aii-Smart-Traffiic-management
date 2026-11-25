import { Siren, ShieldAlert, CheckCircle2, HelpCircle } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { emergencyApi } from '../../services/api'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import toast from 'react-hot-toast'

export function EmergencyPanel() {
  const emergency = useAppStore((s) => s.emergencyState)
  const history = useAppStore((s) => s.emergencyHistory)
  const setEmergencyState = useAppStore((s) => s.setEmergencyState)

  const handleManualClear = async () => {
    try {
      await emergencyApi.manualClear()
      setEmergencyState({ active: false, status: 'cleared', type: null, direction: null })
      toast.success('Emergency priority cleared')
    } catch {
      toast.error('Failed to clear emergency state')
    }
  }

  const isConfirmed = emergency.status === 'stage2_confirmed'
  const isUnconfirmed = emergency.active && !isConfirmed

  return (
    <Card
      title="Emergency Intelligence"
      subtitle="Two-stage detection: Ambulance & Fire Brigade (Police excluded)"
      glowColor={emergency.active ? (isConfirmed ? 'red' : 'amber') : null}
      headerRight={
        <Badge variant={emergency.active ? (isConfirmed ? 'error' : 'warning') : 'success'} dot pulse={emergency.active}>
          {emergency.active ? (isConfirmed ? 'CONFIRMED' : 'UNCONFIRMED') : 'CLEAR'}
        </Badge>
      }
    >
      {emergency.active ? (
        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <Siren className="w-5 h-5 text-red-400 shrink-0 mt-0.5 animate-pulse" />
              <div>
                <p className="text-sm font-semibold text-red-300 uppercase">
                  {emergency.type?.replace('_', ' ') ?? 'Emergency Vehicle'} — {emergency.direction?.toUpperCase()}
                </p>
                <p className="text-xs text-slate-300 mt-1">
                  {isConfirmed
                    ? 'Stage 2 visual beacons confirmed. Priority signal transition active.'
                    : 'Stage 1 vehicle detected — emergency flashing lights unconfirmed. Displaying uncertainty.'}
                </p>
              </div>
            </div>
            <Button variant="danger" size="xs" onClick={handleManualClear}>
              Clear
            </Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div className="p-2 rounded bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">CONFIDENCE</span>
              <span className="text-slate-100 font-bold">{(emergency.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="p-2 rounded bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">STAGE 1</span>
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Detected
              </span>
            </div>
            <div className="p-2 rounded bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">STAGE 2</span>
              <span className={isUnconfirmed ? 'text-amber-400 flex items-center gap-1' : 'text-red-400 flex items-center gap-1'}>
                {isUnconfirmed ? <HelpCircle className="w-3 h-3" /> : <ShieldAlert className="w-3 h-3" />}
                {isConfirmed ? 'Confirmed' : 'Uncertain'}
              </span>
            </div>
            <div className="p-2 rounded bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">DETECTED AT</span>
              <span className="text-slate-200">
                {emergency.firstDetected ? new Date(emergency.firstDetected).toLocaleTimeString() : '—'}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="py-4 text-center text-xs text-slate-400">
          No active ambulance or fire brigade emergency. All 4 approaches monitored.
        </div>
      )}

      {history.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-800">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Recent Events
          </p>
          <div className="space-y-1.5 max-h-28 overflow-y-auto">
            {history.slice(0, 4).map((ev) => (
              <div key={ev.id} className="flex items-center justify-between text-xs font-mono text-slate-400 bg-slate-900/50 px-2.5 py-1.5 rounded">
                <span className="text-slate-200">
                  {ev.type ?? 'emergency'} @ {ev.direction?.toUpperCase() ?? 'N/A'}
                </span>
                <span>{ev.resolvedAt ? new Date(ev.resolvedAt).toLocaleTimeString() : 'Active'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}
