import { useAppStore, Direction, SignalPhase, DensityCategory, Detection } from '../store/appStore'
import toast from 'react-hot-toast'

type SignalHandler = (msg: Record<string, unknown>) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 2000
  private maxReconnectDelay = 30000
  private isConnecting = false
  private shouldReconnect = true
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private customListeners = new Set<SignalHandler>()
  private lastRawFrameAt: Partial<Record<Direction, number>> = {}

  addListener(fn: SignalHandler) {
    this.customListeners.add(fn)
    return () => this.customListeners.delete(fn)
  }

  private getWsUrl(token?: string | null): string {
    let base: string
    if (import.meta.env.VITE_WS_URL) {
      base = import.meta.env.VITE_WS_URL.replace(/\/$/, '')
    } else if (import.meta.env.VITE_API_URL) {
      base = import.meta.env.VITE_API_URL.replace(/\/$/, '').replace(/^http/i, 'ws')
    } else {
      base = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    }
    return `${base}/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`
  }

  connect(overrideToken?: string) {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) return
    this.isConnecting = true
    this.shouldReconnect = true

    const token = overrideToken ?? localStorage.getItem('auth_token')
    const wsUrl = this.getWsUrl(token)

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.isConnecting = false
        this.reconnectDelay = 2000
        useAppStore.getState().setSystemStatus({ wsConnected: true })
        this.startHeartbeat()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as Record<string, unknown>
          this.handleMessage(data)
          this.customListeners.forEach((fn) => fn(data))
        } catch {
          console.warn('[WS] Failed to parse message', event.data)
        }
      }

      this.ws.onclose = (event) => {
        this.isConnecting = false
        this.stopHeartbeat()
        useAppStore.getState().setSystemStatus({ wsConnected: false })
        if (event.code === 1008) {
          this.shouldReconnect = false
          return
        }
        if (!event.wasClean && this.shouldReconnect) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = () => {
        this.isConnecting = false
        useAppStore.getState().setSystemStatus({ wsConnected: false })
      }
    } catch (err) {
      this.isConnecting = false
      console.error('[WS] Connection error:', err)
      this.scheduleReconnect()
    }
  }

  private handleMessage(data: Record<string, unknown>) {
    const store = useAppStore.getState()
    const type = data.type as string
    const payload = (data.payload ?? data.data ?? {}) as Record<string, unknown>

    switch (type) {
      case 'signal_update': {
        if (payload.signals && typeof payload.signals === 'object') {
          const signals = payload.signals as Record<string, Record<string, unknown>>
          const mode = (payload.mode as 'AUTO' | 'MANUAL' | 'EMERGENCY') ?? 'AUTO'
          store.setAutoMode(mode === 'AUTO')
          ;(['north', 'south', 'east', 'west'] as Direction[]).forEach((dir) => {
            if (signals[dir]) {
              const s = signals[dir]
              store.setSignalState(dir, {
                phase: s.phase as SignalPhase,
                countdown: Number(s.countdown ?? s.time_remaining ?? 0),
                mode,
                recommendedGreen: Number(s.recommended_green ?? s.duration ?? 30),
                nextPhase: (s.next_phase as SignalPhase) ?? (s.phase === 'GREEN' ? 'YELLOW' : 'GREEN'),
              })
            }
          })
        } else if (payload.direction) {
          const direction = payload.direction as Direction
          store.setSignalState(direction, {
            phase: payload.phase as SignalPhase,
            countdown: Number(payload.countdown ?? 0),
            mode: (payload.mode as 'AUTO' | 'MANUAL' | 'EMERGENCY') ?? 'AUTO',
            recommendedGreen: Number(payload.recommended_green ?? 30),
            nextPhase: (payload.next_phase as SignalPhase) ?? 'GREEN',
          })
        }
        break
      }

      case 'traffic_update': {
        if (payload.direction) {
          const direction = payload.direction as Direction
          const densityNum = Number(payload.density ?? 0)
          const level = ((payload.density_level as string) ?? 'LOW').toUpperCase() as DensityCategory
          store.setTrafficData(direction, {
            count: Number(payload.count ?? payload.vehicle_count ?? 0),
            speed: Number(payload.speed ?? payload.speed_estimate ?? 0),
            speedIsEstimate: payload.speed_is_estimate !== false,
            queueLength: Number(payload.queue_length ?? 0),
            density: densityNum,
            densityLevel: level,
            trend: (payload.trend as 'increasing' | 'decreasing' | 'stable') ?? 'stable',
            predictedCount: payload.predicted_count as number | undefined,
            congestionPredicted: payload.congestion_predicted as boolean | undefined,
          })
        }
        break
      }

      case 'camera_update': {
        const direction = payload.direction as Direction
        if (!direction) break
        store.setCameraFeed(direction, {
          vehicleCount: Number(payload.vehicle_count ?? 0),
          density: Number(payload.density ?? 0),
          fps: Number(payload.fps ?? 0),
          status: (payload.status as 'connected' | 'disconnected' | 'connecting' | 'error') ?? 'connected',
          detections: (payload.detections as Detection[]) ?? [],
        })
        const lastRaw = this.lastRawFrameAt[direction] ?? 0
        if (payload.snapshot && Date.now() - lastRaw > 1500) {
          store.setCameraSnapshot(direction, payload.snapshot as string)
        }
        break
      }

      case 'camera_frame': {
        const direction = payload.direction as Direction
        if (direction && payload.image) {
          this.lastRawFrameAt[direction] = Date.now()
          store.setCameraSnapshot(direction, payload.image as string)
          store.setCameraFeed(direction, { status: 'connected' })
          store.setSystemStatus({
            camerasConnected: { ...store.systemStatus.camerasConnected, [direction]: true },
          })
        }
        break
      }

      case 'emergency_alert': {
        const wasActive = store.emergencyState.active
        const rawType = payload.type ?? payload.vehicle_type
        const emType = rawType === 'ambulance' || rawType === 'fire_brigade' ? rawType : null
        store.setEmergencyState({
          active: Boolean(payload.active),
          type: emType,
          direction: (payload.direction as Direction | null) ?? null,
          confidence: Number(payload.confidence ?? 0),
          status: (payload.status as 'detected' | 'stage1_confirmed' | 'stage2_confirmed' | 'cleared' | null) ?? null,
          firstDetected: (payload.first_detected as number | null) ?? Date.now(),
          estimatedArrival: (payload.estimated_arrival as number | null) ?? null,
        })
        if (payload.active && !wasActive && emType) {
          toast.error(`Emergency vehicle detected: ${emType} from ${String(payload.direction).toUpperCase()}`, {
            duration: 8000,
          })
          store.addNotification({
            type: 'error',
            message: `Emergency ${emType} detected from ${String(payload.direction).toUpperCase()}`,
          })
        } else if (!payload.active && wasActive) {
          store.addEmergencyHistory(store.emergencyState)
          toast.success('Emergency cleared — resuming normal operations')
          store.addNotification({ type: 'success', message: 'Emergency vehicle cleared' })
        }
        break
      }

      case 'system_status': {
        store.setSystemStatus({
          junctionStatus: (payload.junction_status as 'online' | 'offline' | 'degraded') ?? 'online',
          aiEngineStatus: (payload.ai_engine_status as 'running' | 'stopped' | 'error') ?? 'stopped',
          mqttConnected: Boolean(payload.mqtt_connected),
          esp32Connected: payload.esp32_connected !== undefined ? Boolean(payload.esp32_connected) : store.systemStatus.esp32Connected,
          uptime: Number(payload.uptime ?? 0),
          lastHeartbeat: Date.now(),
        })
        if (payload.demo_mode !== undefined) {
          store.setDemoMode(Boolean(payload.demo_mode))
        }
        break
      }

      case 'esp32_status': {
        store.setSystemStatus({ esp32Connected: Boolean(payload.connected) })
        store.setHardwareStatus({
          lastCommandTimestamp: (payload.last_command_ts as number | null) ?? store.hardwareStatus.lastCommandTimestamp,
          lastAckSequenceId: (payload.last_ack_seq as number | null) ?? store.hardwareStatus.lastAckSequenceId,
          hardwareError: (payload.error as string | null) ?? null,
          wifiRssi: (payload.wifi_rssi as number | null) ?? null,
        })
        break
      }

      case 'performance_metrics':
      case 'performance_update': {
        store.setPerformanceMetrics({
          cpuUsage: Number(payload.cpu_usage ?? payload.cpu_percent ?? 0),
          gpuUsage: Number(payload.gpu_usage ?? payload.gpu_percent ?? 0),
          vramUsed: Number(payload.vram_used ?? 0),
          vramTotal: Number(payload.vram_total ?? 0),
          inferenceLatency: Number(payload.inference_latency ?? payload.inference_latency_ms ?? 0),
          detectionFps: Number(payload.detection_fps ?? 0),
          memoryUsage: Number(payload.memory_usage ?? payload.memory_percent ?? 0),
        })
        break
      }

      case 'ai_decision': {
        store.setAIDecision({
          timestamp: Date.now(),
          action: String(payload.action ?? ''),
          reason: String(payload.reason ?? ''),
          metrics: (payload.metrics as Record<string, { count: number; density: number; queueLength: number }>) ?? {},
          confidence: Number(payload.confidence ?? 0),
          algorithm: String(payload.algorithm ?? 'Adaptive + Safety Controller'),
        })
        break
      }

      case 'camera_connected': {
        const direction = payload.direction as Direction
        store.setSystemStatus({
          camerasConnected: { ...store.systemStatus.camerasConnected, [direction]: true },
        })
        store.setCameraFeed(direction, { status: 'connected' })
        store.addNotification({ type: 'success', message: `Camera connected: ${direction}` })
        break
      }

      case 'camera_disconnected': {
        const direction = payload.direction as Direction
        store.setSystemStatus({
          camerasConnected: { ...store.systemStatus.camerasConnected, [direction]: false },
        })
        store.setCameraFeed(direction, { status: 'disconnected' })
        store.addNotification({ type: 'warning', message: `Camera disconnected: ${direction}` })
        break
      }

      case 'notification': {
        store.addNotification({
          type: (payload.severity as 'info' | 'warning' | 'error' | 'success') ?? 'info',
          message: String(payload.message ?? ''),
        })
        break
      }

      case 'pong':
        store.setSystemStatus({ lastHeartbeat: Date.now() })
        break

      default:
        break
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping' })
    }, 15000)
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect()
        this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay)
      }
    }, this.reconnectDelay)
  }

  send(data: unknown) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
      return true
    }
    return false
  }

  disconnect() {
    this.shouldReconnect = false
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close(1000, 'Client disconnected')
      this.ws = null
    }
  }

  isConnected() {
    return this.ws?.readyState === WebSocket.OPEN
  }

  getBufferedAmount(): number {
    return this.ws?.bufferedAmount ?? 0
  }
}

export const wsService = new WebSocketService()
