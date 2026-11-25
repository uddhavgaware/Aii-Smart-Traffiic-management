import { useEffect, useState } from 'react'
import { Direction, SignalPhase, useAppStore } from '../store/appStore'
import { signalApi } from '../services/api'
import { TrafficSignal } from '../components/dashboard/TrafficSignal'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { ShieldCheck, Sliders, Hand } from 'lucide-react'
import toast from 'react-hot-toast'

const DIRECTIONS: Direction[] = ['north', 'south', 'east', 'west']

export default function Signals() {
  const signalState = useAppStore((s) => s.signalState)
  const isAutoMode = useAppStore((s) => s.isAutoMode)
  const setAutoMode = useAppStore((s) => s.setAutoMode)

  const [selectedDir, setSelectedDir] = useState<Direction>('north')
  const [selectedPhase, setSelectedPhase] = useState<SignalPhase>('GREEN')
  const [overrideDuration, setOverrideDuration] = useState(30)

  const [minGreen, setMinGreen] = useState(15)
  const [maxGreen, setMaxGreen] = useState(120)
  const [yellowTime, setYellowTime] = useState(3)
  const [allRedTime, setAllRedTime] = useState(2)
  const [maxWait, setMaxWait] = useState(180)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    signalApi.getConfig()
      .then((res) => {
        const c = res.data
        if (c) {
          setMinGreen(c.min_green_time ?? 15)
          setMaxGreen(c.max_green_time ?? 120)
          setYellowTime(c.yellow_time ?? 3)
          setAllRedTime(c.all_red_time ?? 2)
          setMaxWait(c.max_wait_time ?? 180)
        }
      })
      .catch(() => {})
  }, [])

  const handleModeSwitch = async (mode: 'AUTO' | 'MANUAL') => {
    try {
      await signalApi.setMode(mode)
      setAutoMode(mode === 'AUTO')
      toast.success(`Switched to ${mode} control mode`)
    } catch {
      toast.error('Failed to change control mode (Admin/Operator required)')
    }
  }

  const handleManualOverride = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await signalApi.override(selectedDir, selectedPhase, overrideDuration, 'Manual operator command')
      setAutoMode(false)
      toast.success(`Safe transition initiated for ${selectedDir.toUpperCase()} → ${selectedPhase}`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg ?? 'Signal command rejected by safety controller')
    }
  }

  const handleSaveTiming = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await signalApi.updateTiming({
        min_green: minGreen,
        max_green: maxGreen,
        yellow_duration: yellowTime,
        all_red_duration: allRedTime,
        max_wait: maxWait,
      })
      toast.success('Signal timing constraints updated')
    } catch {
      toast.error('Failed to update timing constraints')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-slate-100">Signal Control & Safety Controller</h1>
          <p className="text-xs text-slate-400">
            Deterministic safety sequence: GREEN → YELLOW → ALL RED → NEXT GREEN. Conflicting greens are blocked at both backend and ESP32.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={isAutoMode ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => handleModeSwitch('AUTO')}
          >
            AUTO (AI Adaptive)
          </Button>
          <Button
            variant={!isAutoMode ? 'primary' : 'secondary'}
            size="sm"
            leftIcon={<Hand className="w-4 h-4" />}
            onClick={() => handleModeSwitch('MANUAL')}
          >
            MANUAL OVERRIDE
          </Button>
        </div>
      </div>

      {/* Live 4-signal grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {DIRECTIONS.map((dir) => (
          <TrafficSignal key={dir} direction={dir} signal={signalState[dir]} onSelect={setSelectedDir} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Manual override */}
        <Card
          title="Manual Signal Override"
          subtitle="Admin/Operator control — safe clearance transitions remain enforced"
          headerRight={<Badge variant={isAutoMode ? 'default' : 'warning'}>{isAutoMode ? 'AUTO ACTIVE' : 'MANUAL ACTIVE'}</Badge>}
        >
          <form onSubmit={handleManualOverride} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Target Direction</label>
                <select
                  value={selectedDir}
                  onChange={(e) => setSelectedDir(e.target.value as Direction)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"
                >
                  {DIRECTIONS.map((d) => (
                    <option key={d} value={d}>
                      {d.toUpperCase()} ({d === 'north' || d === 'south' ? 'N+S Pair' : 'E+W Pair'})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Requested Phase</label>
                <select
                  value={selectedPhase}
                  onChange={(e) => setSelectedPhase(e.target.value as SignalPhase)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"
                >
                  <option value="GREEN">GREEN (with safe pair)</option>
                  <option value="RED">ALL RED (clearance)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Duration (seconds): <span className="text-cyan-400 font-mono">{overrideDuration}s</span>
              </label>
              <input
                type="range"
                min={minGreen}
                max={maxGreen}
                value={overrideDuration}
                onChange={(e) => setOverrideDuration(Number(e.target.value))}
                className="w-full accent-cyan-400"
              />
            </div>

            <div className="p-2.5 rounded bg-slate-900/70 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>All manual actions are logged and transitioned through Yellow + All-Red clearance.</span>
            </div>

            <Button type="submit" variant="primary" size="sm" className="w-full">
              Execute Safe Signal Transition
            </Button>
          </form>
        </Card>

        {/* Timing constraints */}
        <Card
          title="Configurable Timing & Safety Bounds"
          subtitle="Enforced deterministically by SignalSafetyController"
          headerRight={<Sliders className="w-4 h-4 text-cyan-400" />}
        >
          <form onSubmit={handleSaveTiming} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Min Green (s)</label>
                <input
                  type="number"
                  min={5}
                  max={60}
                  value={minGreen}
                  onChange={(e) => setMinGreen(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Max Green (s)</label>
                <input
                  type="number"
                  min={30}
                  max={300}
                  value={maxGreen}
                  onChange={(e) => setMaxGreen(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Yellow Transition (s)</label>
                <input
                  type="number"
                  min={2}
                  max={10}
                  value={yellowTime}
                  onChange={(e) => setYellowTime(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">All-Red Clearance (s)</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={allRedTime}
                  onChange={(e) => setAllRedTime(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-100"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Max Starvation Wait Time (s)</label>
              <input
                type="number"
                min={60}
                max={600}
                value={maxWait}
                onChange={(e) => setMaxWait(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-100"
              />
            </div>

            <Button type="submit" variant="secondary" size="sm" isLoading={saving} className="w-full">
              Save Signal Configuration
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
