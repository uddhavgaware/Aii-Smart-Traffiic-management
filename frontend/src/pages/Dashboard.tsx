import { useEffect, useState } from 'react'
import { Direction, useAppStore } from '../store/appStore'
import { cameraApi, hardwareApi, signalApi, systemApi, trafficApi } from '../services/api'
import { CameraFeed } from '../components/dashboard/CameraFeed'
import { TrafficSignal } from '../components/dashboard/TrafficSignal'
import { DigitalTwin } from '../components/dashboard/DigitalTwin'
import { AIDecisionPanel } from '../components/dashboard/AIDecisionPanel'
import { EmergencyPanel } from '../components/dashboard/EmergencyPanel'
import { PerformancePanel } from '../components/dashboard/PerformancePanel'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { StatusIndicator } from '../components/ui/StatusIndicator'
import { Activity, ArrowDown, ArrowUp, Minus, Radio, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'

const DIRECTIONS: Direction[] = ['north', 'south', 'east', 'west']

export default function Dashboard() {
  const [filterDir, setFilterDir] = useState<'all' | Direction>('all')
  const [refreshing, setRefreshing] = useState(false)

  const signalState = useAppStore((s) => s.signalState)
  const trafficData = useAppStore((s) => s.trafficData)
  const systemStatus = useAppStore((s) => s.systemStatus)
  const hardwareStatus = useAppStore((s) => s.hardwareStatus)
  const setSystemStatus = useAppStore((s) => s.setSystemStatus)
  const setPerformanceMetrics = useAppStore((s) => s.setPerformanceMetrics)
  const setDemoMode = useAppStore((s) => s.setDemoMode)
  const setSignalState = useAppStore((s) => s.setSignalState)
  const setTrafficData = useAppStore((s) => s.setTrafficData)
  const setAutoMode = useAppStore((s) => s.setAutoMode)

  const fetchSnapshot = async () => {
    setRefreshing(true)
    try {
      const [sysRes, metRes, sigRes, trafRes] = await Promise.allSettled([
        systemApi.getStatus(),
        systemApi.getPerformanceMetrics(),
        signalApi.getCurrentState(),
        trafficApi.getCurrent(),
      ])

      if (sysRes.status === 'fulfilled') {
        const d = sysRes.value.data
        setSystemStatus({
          junctionStatus: (d.junction_status as 'online' | 'offline' | 'degraded') ?? 'online',
          aiEngineStatus: (d.ai_engine_status as 'running' | 'stopped' | 'error') ?? 'stopped',
          esp32Connected: d.esp32_connected,
          mqttConnected: d.mqtt_connected,
          uptime: d.uptime,
        })
        setDemoMode(Boolean(d.demo_mode))
      }

      if (metRes.status === 'fulfilled') {
        const m = metRes.value.data
        setPerformanceMetrics({
          cpuUsage: m.cpu_usage,
          gpuUsage: m.gpu_usage,
          vramUsed: m.vram_used,
          vramTotal: m.vram_total,
          inferenceLatency: m.inference_latency,
          detectionFps: m.detection_fps,
          memoryUsage: m.memory_usage,
        })
      }

      if (sigRes.status === 'fulfilled') {
        const sd = sigRes.value.data
        setAutoMode(sd.mode === 'AUTO')
        DIRECTIONS.forEach((dir) => {
          const item = sd.directions?.[dir]
          if (item) {
            setSignalState(dir, {
              phase: item.phase,
              countdown: item.time_remaining,
              mode: sd.emergency_active ? 'EMERGENCY' : sd.mode,
              recommendedGreen: item.duration,
            })
          }
        })
      }

      if (trafRes.status === 'fulfilled') {
        const td = trafRes.value.data
        DIRECTIONS.forEach((dir) => {
          const item = td[dir]
          if (item) {
            setTrafficData(dir, {
              count: item.vehicle_count ?? 0,
              speed: item.speed_estimate ?? 0,
              speedIsEstimate: item.speed_is_estimate !== false,
              queueLength: item.queue_length ?? 0,
              density: item.density ?? 0,
              densityLevel: (item.density_level ?? 'LOW').toUpperCase(),
              congestionPredicted: item.congestion_predicted,
            })
          }
        })
      }
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchSnapshot()
    const timer = setInterval(fetchSnapshot, 10000)
    return () => clearInterval(timer)
  }, [])

  const handleCameraReconnect = async (direction: Direction) => {
    try {
      await cameraApi.reconnect(direction)
      toast.success(`Reconnect requested for ${direction.toUpperCase()} camera`)
    } catch {
      toast.error(`Camera ${direction.toUpperCase()} is not registered yet`)
    }
  }

  const handleCameraDisconnect = async (direction: Direction) => {
    try {
      await cameraApi.disconnect(direction)
      useAppStore.getState().setCameraSnapshot(direction, null)
      useAppStore.getState().setCameraFeed(direction, {
        status: 'disconnected',
        fps: 0,
        vehicleCount: 0,
        detections: [],
      })
      toast.success(`Disconnected ${direction.toUpperCase()} camera`)
    } catch {
      toast.error(`Failed to disconnect ${direction.toUpperCase()} camera`)
    }
  }

  const handleHardwarePing = async () => {
    try {
      await hardwareApi.getStatus()
      toast.success('Hardware status refreshed')
    } catch {
      toast.error('Failed to query ESP32 hardware status')
    }
  }

  const visibleDirections = filterDir === 'all' ? DIRECTIONS : [filterDir]

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-slate-100 tracking-tight">Junction Control Room</h1>
          <p className="text-xs text-slate-400">
            Four-way adaptive traffic monitoring, computer vision, and deterministic ESP32 signal execution
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-slate-900 border border-slate-800 p-0.5 text-xs font-mono">
            {(['all', ...DIRECTIONS] as const).map((dir) => (
              <button
                key={dir}
                onClick={() => setFilterDir(dir)}
                className={`px-2.5 py-1 rounded-md uppercase transition-colors ${
                  filterDir === dir ? 'bg-cyan-500/20 text-cyan-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {dir}
              </button>
            ))}
          </div>

          <button
            onClick={fetchSnapshot}
            className="p-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-cyan-400 transition-colors"
            title="Refresh live telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Top row: 2x2 Camera Grid + Digital Twin / Signal Overview */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <div className={`xl:col-span-7 grid gap-4 ${filterDir === 'all' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}`}>
          {visibleDirections.map((dir) => (
            <CameraFeed
              key={dir}
              direction={dir}
              onReconnect={handleCameraReconnect}
              onDisconnect={handleCameraDisconnect}
              compact
            />
          ))}
        </div>

        <div className="xl:col-span-5 flex flex-col gap-4">
          <DigitalTwin />

          <Card title="Four-Way Signal Control" subtitle="Synchronized physical LED phases">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {DIRECTIONS.map((dir) => (
                <TrafficSignal key={dir} direction={dir} signal={signalState[dir]} />
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Traffic Analytics Row */}
      <Card title="Live Approach Analytics" subtitle="Vehicle counts, density levels, relative speed estimates, and queue metrics">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {DIRECTIONS.map((dir) => {
            const t = trafficData[dir]
            const TrendIcon = t.trend === 'increasing' ? ArrowUp : t.trend === 'decreasing' ? ArrowDown : Minus
            const trendColor = t.trend === 'increasing' ? 'text-red-400' : t.trend === 'decreasing' ? 'text-emerald-400' : 'text-slate-400'
            return (
              <div key={dir} className="p-3 rounded-lg bg-slate-900/70 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase font-mono text-cyan-400">{dir}</span>
                  <Badge
                    variant={
                      t.densityLevel === 'TRAFFIC_JAM'
                        ? 'error'
                        : t.densityLevel === 'HIGH'
                        ? 'warning'
                        : t.densityLevel === 'MEDIUM'
                        ? 'cyan'
                        : 'success'
                    }
                    size="xs"
                  >
                    {t.densityLevel}
                  </Badge>
                </div>

                <div className="flex items-baseline justify-between">
                  <div>
                    <span className="text-2xl font-bold font-mono text-slate-100">{t.count}</span>
                    <span className="text-xs text-slate-500 ml-1">vehicles</span>
                  </div>
                  <span className={`flex items-center gap-0.5 text-xs font-mono ${trendColor}`}>
                    <TrendIcon className="w-3.5 h-3.5" /> {t.trend}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80 text-[11px] font-mono">
                  <div>
                    <span className="text-slate-500 block">SPEED</span>
                    <span className="text-slate-200">
                      {t.speed > 0 ? `${t.speed.toFixed(1)}` : '—'}{' '}
                      <span className="text-[10px] text-amber-400">{t.speedIsEstimate ? '(EST)' : 'km/h'}</span>
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">QUEUE</span>
                    <span className="text-slate-200">{t.queueLength.toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      {/* Bottom Row: Emergency, AI Explainability, Hardware, Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <EmergencyPanel />
        <AIDecisionPanel />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card
          title="ESP32 Hardware Monitoring"
          subtitle="MQTT TLS telemetry and signal execution acknowledgement"
          headerRight={
            <button onClick={handleHardwarePing} className="text-xs text-cyan-400 hover:text-cyan-300 font-mono">
              Refresh
            </button>
          }
        >
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">ESP32 NODE</span>
              <div className="mt-1">
                <StatusIndicator
                  status={systemStatus.esp32Connected}
                  label={systemStatus.esp32Connected ? 'Online' : 'Offline'}
                />
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">MQTT BROKER</span>
              <div className="mt-1">
                <StatusIndicator
                  status={systemStatus.mqttConnected}
                  label={systemStatus.mqttConnected ? 'TLS Connected' : 'Disconnected'}
                />
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">LAST COMMAND</span>
              <span className="text-slate-200 mt-1 block">
                {hardwareStatus.lastCommandTimestamp
                  ? new Date(hardwareStatus.lastCommandTimestamp).toLocaleTimeString()
                  : 'None sent'}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800">
              <span className="text-slate-500 block text-[10px]">LAST ACK SEQ / ERROR</span>
              <span className="text-slate-200 mt-1 flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-cyan-400" />
                {hardwareStatus.hardwareError
                  ? <span className="text-red-400 truncate">{hardwareStatus.hardwareError}</span>
                  : hardwareStatus.lastAckSequenceId ?? 'Awaiting ACK'}
              </span>
            </div>
          </div>
          <div className="mt-3 p-2.5 rounded bg-slate-900/50 border border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span className="flex items-center gap-1.5"><Activity className="w-3.5 h-3.5 text-emerald-400" /> Safe Transitions Enforced</span>
            <span>GREEN → YELLOW (3s) → ALL-RED (2s)</span>
          </div>
        </Card>

        <PerformancePanel />
      </div>
    </div>
  )
}
