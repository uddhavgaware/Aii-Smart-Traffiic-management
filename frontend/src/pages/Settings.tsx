import { useEffect, useState } from 'react'
import { systemApi } from '../services/api'
import { useAppStore } from '../store/appStore'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Save, RotateCw } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Settings() {
  const isDemoMode = useAppStore((s) => s.isDemoMode)
  const setDemoMode = useAppStore((s) => s.setDemoMode)

  const [resolution, setResolution] = useState('720p')
  const [fpsPerCam, setFpsPerCam] = useState(15)
  const [lowThreshold, setLowThreshold] = useState(5)
  const [normalThreshold, setNormalThreshold] = useState(15)
  const [mediumThreshold, setMediumThreshold] = useState(25)
  const [highThreshold, setHighThreshold] = useState(40)
  const [mqttPrefix, setMqttPrefix] = useState('smarttraffic/junction_001')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    systemApi.getSettings()
      .then((res) => {
        const s = res.data
        if (s) {
          if (s.resolution) setResolution(s.resolution)
          if (s.fps_per_camera) setFpsPerCam(s.fps_per_camera)
          if (s.density_thresholds) {
            setLowThreshold(s.density_thresholds.low ?? 5)
            setNormalThreshold(s.density_thresholds.normal ?? 15)
            setMediumThreshold(s.density_thresholds.medium ?? 25)
            setHighThreshold(s.density_thresholds.high ?? 40)
          }
          if (s.mqtt_topic_prefix) setMqttPrefix(s.mqtt_topic_prefix)
        }
      })
      .catch(() => {})
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await systemApi.updateSettings({
        resolution,
        fps_per_camera: fpsPerCam,
        density_thresholds: {
          low: lowThreshold,
          normal: normalThreshold,
          medium: mediumThreshold,
          high: highThreshold,
        },
      })
      toast.success('System settings saved')
    } catch {
      toast.error('Failed to save settings (Admin role required)')
    } finally {
      setSaving(false)
    }
  }

  const handleToggleDemo = async () => {
    try {
      const next = !isDemoMode
      await systemApi.toggleDemoMode(next)
      setDemoMode(next)
      toast.success(next ? 'Demo Mode enabled (labeled simulation)' : 'Demo Mode disabled (live hardware mode)')
    } catch {
      toast.error('Failed to toggle demo mode')
    }
  }

  const handleRestartAI = async () => {
    try {
      await systemApi.restartAIEngine()
      toast.success('AI engine reload triggered')
    } catch {
      toast.error('Failed to reach AI engine')
    }
  }

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-lg font-bold text-slate-100">System Configuration</h1>
        <p className="text-xs text-slate-400">
          Configure traffic density thresholds, RTX 3050 inference budget, and clearly-labeled Demo Mode
        </p>
      </div>

      {/* Demo mode card */}
      <Card
        title="Operational vs Demo Mode"
        subtitle="Demo mode uses synthetic/sample traffic streams and simulated ESP32 ACKs — never confused with real hardware"
        headerRight={<Badge variant={isDemoMode ? 'warning' : 'success'}>{isDemoMode ? 'DEMO MODE' : 'LIVE HARDWARE MODE'}</Badge>}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-xs text-slate-300 max-w-xl">
            Enable Demo Mode only when demonstrating the dashboard without physical phones or ESP32 hardware connected.
          </p>
          <div className="flex gap-2">
            <Button variant={isDemoMode ? 'danger' : 'secondary'} size="sm" onClick={handleToggleDemo}>
              {isDemoMode ? 'Disable Demo Mode' : 'Enable Demo Mode'}
            </Button>
            <Button variant="outline" size="sm" leftIcon={<RotateCw className="w-3.5 h-3.5" />} onClick={handleRestartAI}>
              Check AI Engine
            </Button>
          </div>
        </div>
      </Card>

      {/* Main settings form */}
      <form onSubmit={handleSave} className="space-y-4">
        <Card title="Inference & Camera Performance" subtitle="Optimized for NVIDIA RTX 3050 6GB + Intel Core i5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Camera Capture Resolution</label>
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"
              >
                <option value="480p">480p (854×480 — lowest latency)</option>
                <option value="720p">720p (1280×720 — target default)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Sampling Rate per Camera: <span className="text-cyan-400 font-mono">{fpsPerCam} FPS (~{fpsPerCam * 4} total)</span>
              </label>
              <input
                type="range"
                min={2}
                max={25}
                value={fpsPerCam}
                onChange={(e) => setFpsPerCam(Number(e.target.value))}
                className="w-full accent-cyan-400 mt-2"
              />
            </div>
          </div>
        </Card>

        <Card title="Traffic Density Classification Thresholds" subtitle="Vehicle count cutoffs (paired with queue & speed weighting)">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">LOW (≤)</label>
              <input type="number" value={lowThreshold} onChange={(e) => setLowThreshold(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">NORMAL (≤)</label>
              <input type="number" value={normalThreshold} onChange={(e) => setNormalThreshold(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">MEDIUM (≤)</label>
              <input type="number" value={mediumThreshold} onChange={(e) => setMediumThreshold(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">HIGH (≤ / Jam above)</label>
              <input type="number" value={highThreshold} onChange={(e) => setHighThreshold(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono" />
            </div>
          </div>
        </Card>

        <Card title="MQTT Hardware Topic (Read-Only)" subtitle="Credentials and TLS certificates are stored exclusively in backend environment variables">
          <input
            type="text"
            readOnly
            value={mqttPrefix}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm font-mono text-slate-400"
          />
        </Card>

        <Button type="submit" variant="primary" isLoading={saving} leftIcon={<Save className="w-4 h-4" />}>
          Save Configuration
        </Button>
      </form>
    </div>
  )
}
