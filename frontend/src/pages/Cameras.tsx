import { useEffect, useState } from 'react'
import { Direction, useAppStore } from '../store/appStore'
import { cameraApi } from '../services/api'
import { QRRegistration } from '../components/cameras/QRRegistration'
import { CameraCard } from '../components/cameras/CameraCard'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Smartphone, PlusCircle } from 'lucide-react'
import toast from 'react-hot-toast'

const DIRECTIONS: Direction[] = ['north', 'south', 'east', 'west']

interface CameraRecord {
  id: number
  unique_id: string
  direction: Direction
  status: string
  ip_address?: string | null
  last_seen?: string | null
}

export default function Cameras() {
  const [cameras, setCameras] = useState<CameraRecord[]>([])
  const [junctionCode, setJunctionCode] = useState('JCT-001-LOADING')
  const [qrDir, setQrDir] = useState<Direction>('north')
  const [manualDir, setManualDir] = useState<Direction>('north')
  const [deviceId, setDeviceId] = useState('')
  const [allowReplace, setAllowReplace] = useState(false)
  const [loading, setLoading] = useState(false)

  const cameraFeeds = useAppStore((s) => s.cameraFeeds)

  const loadData = async () => {
    try {
      const [camRes, codeRes] = await Promise.all([
        cameraApi.getAll(),
        cameraApi.getJunctionCode(),
      ])
      setCameras(camRes.data ?? [])
      if (codeRes.data?.code) setJunctionCode(codeRes.data.code)
    } catch {
      toast.error('Failed to load camera registry')
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleManualRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await cameraApi.register({
        junction_code: junctionCode,
        direction: manualDir,
        device_id: deviceId.trim() || `mobile-${manualDir}-${Date.now()}`,
        allow_replace: allowReplace,
      })
      toast.success(`Registered camera for ${manualDir.toUpperCase()}`)
      setDeviceId('')
      await loadData()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg ?? 'Registration failed (direction may already be assigned)')
    } finally {
      setLoading(false)
    }
  }

  const handleReconnect = async (dir: Direction) => {
    try {
      await cameraApi.reconnect(dir)
      toast.success(`Reconnect signal sent to ${dir.toUpperCase()}`)
      await loadData()
    } catch {
      toast.error(`Failed to reconnect ${dir.toUpperCase()}`)
    }
  }

  const handleUnregister = async (dir: Direction) => {
    try {
      await cameraApi.unregister(dir)
      toast.success(`Unregistered ${dir.toUpperCase()} camera`)
      await loadData()
    } catch {
      toast.error('Admin permission required to unregister cameras')
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-slate-100">Four-Camera System & Registration</h1>
          <p className="text-xs text-slate-400">
            Pair four Android phones via QR code or manual device registration across any network (WebRTC + TURN)
          </p>
        </div>
        <a href="/camera" target="_blank" rel="noreferrer">
          <Button variant="primary" size="sm" leftIcon={<Smartphone className="w-4 h-4" />}>
            Open Mobile Streamer
          </Button>
        </a>
      </div>

      {/* Method A & Method B */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-7">
          <QRRegistration
            junctionCode={junctionCode}
            selectedDirection={qrDir}
            onDirectionChange={setQrDir}
            onRefreshCode={loadData}
          />
        </div>

        <div className="lg:col-span-5">
          <Card title="Manual Camera Registration" subtitle="Assign direction manually with duplicate protection">
            <form onSubmit={handleManualRegister} className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Junction Direction</label>
                <select
                  value={manualDir}
                  onChange={(e) => setManualDir(e.target.value as Direction)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
                >
                  {DIRECTIONS.map((d) => (
                    <option key={d} value={d}>
                      {d.toUpperCase()} Approach
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Device / Phone Label or ID</label>
                <input
                  type="text"
                  value={deviceId}
                  onChange={(e) => setDeviceId(e.target.value)}
                  placeholder="e.g. Pixel-North-Cam"
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={allowReplace}
                  onChange={(e) => setAllowReplace(e.target.checked)}
                  className="rounded border-slate-600 bg-slate-900 text-cyan-500"
                />
                Allow administrator overwrite if direction already assigned
              </label>

              <Button type="submit" variant="primary" size="sm" isLoading={loading} leftIcon={<PlusCircle className="w-4 h-4" />} className="w-full">
                Register Camera
              </Button>
            </form>
          </Card>
        </div>
      </div>

      {/* 4-Camera Status Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {DIRECTIONS.map((dir) => (
          <CameraCard
            key={dir}
            direction={dir}
            camera={cameras.find((c) => c.direction === dir)}
            feed={cameraFeeds[dir]}
            onReconnect={handleReconnect}
            onUnregister={handleUnregister}
          />
        ))}
      </div>
    </div>
  )
}
