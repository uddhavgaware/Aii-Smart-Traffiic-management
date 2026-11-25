import { create } from 'zustand'

export type Direction = 'north' | 'south' | 'east' | 'west'
export type SignalPhase = 'RED' | 'YELLOW' | 'GREEN'
export type SignalMode = 'AUTO' | 'MANUAL' | 'EMERGENCY'
export type EmergencyType = 'ambulance' | 'fire_brigade' | null
export type DensityCategory = 'LOW' | 'NORMAL' | 'MEDIUM' | 'HIGH' | 'TRAFFIC_JAM'

export interface Detection {
  id: string
  class: string
  confidence: number
  bbox: [number, number, number, number] // x, y, w, h normalized
  trackId?: number
}

export interface CameraFeed {
  stream: MediaStream | null
  vehicleCount: number
  density: number // 0–100
  fps: number
  status: 'connected' | 'disconnected' | 'connecting' | 'error'
  detections: Detection[]
  resolution: string
  bitrate: number
}

export interface SignalState {
  phase: SignalPhase
  countdown: number
  mode: SignalMode
  recommendedGreen: number
  nextPhase: SignalPhase
}

export interface TrafficData {
  count: number
  speed: number    // relative or calibrated speed
  speedIsEstimate: boolean
  queueLength: number
  density: number  // 0–100
  densityLevel: DensityCategory
  trend: 'increasing' | 'decreasing' | 'stable'
  predictedCount?: number
  congestionPredicted?: boolean
  history: { timestamp: number; count: number; density: number }[]
}

export interface HardwareStatus {
  lastCommandTimestamp: number | null
  lastAckSequenceId: number | null
  hardwareError: string | null
  wifiRssi: number | null
}

export interface EmergencyState {
  active: boolean
  type: EmergencyType
  direction: Direction | null
  confidence: number
  status: 'detected' | 'stage1_confirmed' | 'stage2_confirmed' | 'cleared' | null
  firstDetected: number | null
  estimatedArrival: number | null
}

export interface Notification {
  id: string
  type: 'info' | 'warning' | 'error' | 'success'
  message: string
  timestamp: number
  read: boolean
}

export interface SystemStatus {
  junctionStatus: 'online' | 'offline' | 'degraded'
  aiEngineStatus: 'running' | 'stopped' | 'error'
  esp32Connected: boolean
  mqttConnected: boolean
  wsConnected: boolean
  camerasConnected: Record<Direction, boolean>
  uptime: number
  lastHeartbeat: number | null
}

export interface PerformanceMetrics {
  cpuUsage: number
  gpuUsage: number
  vramUsed: number
  vramTotal: number
  inferenceLatency: number
  detectionFps: number
  memoryUsage: number
}

export interface AIDecision {
  timestamp: number
  action: string
  reason: string
  metrics: Partial<Record<Direction, { count: number; density: number; queueLength: number }>>
  confidence: number
  algorithm: string
}

export interface AppState {
  systemStatus: SystemStatus
  cameraFeeds: Record<Direction, CameraFeed>
  signalState: Record<Direction, SignalState>
  trafficData: Record<Direction, TrafficData>
  emergencyState: EmergencyState
  notifications: Notification[]
  isDemoMode: boolean
  isAutoMode: boolean
  performanceMetrics: PerformanceMetrics
  lastAIDecision: AIDecision | null
  emergencyHistory: (EmergencyState & { id: string; resolvedAt?: number })[]
  signalHistory: { timestamp: number; direction: Direction; phase: SignalPhase; duration: number }[]
  hardwareStatus: HardwareStatus
  cameraSnapshots: Record<Direction, string | null>

  // Actions
  setSystemStatus: (status: Partial<SystemStatus>) => void
  setCameraFeed: (direction: Direction, feed: Partial<CameraFeed>) => void
  setCameraSnapshot: (direction: Direction, dataUrl: string | null) => void
  setHardwareStatus: (status: Partial<HardwareStatus>) => void
  setSignalState: (direction: Direction, signal: Partial<SignalState>) => void
  setTrafficData: (direction: Direction, data: Partial<TrafficData>) => void
  setEmergencyState: (state: Partial<EmergencyState>) => void
  addNotification: (notif: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  markNotificationRead: (id: string) => void
  clearNotifications: () => void
  setDemoMode: (enabled: boolean) => void
  setAutoMode: (enabled: boolean) => void
  setPerformanceMetrics: (metrics: Partial<PerformanceMetrics>) => void
  setAIDecision: (decision: AIDecision) => void
  addEmergencyHistory: (event: EmergencyState) => void
  addSignalHistory: (entry: { direction: Direction; phase: SignalPhase; duration: number }) => void
}

const defaultCameraFeed = (): CameraFeed => ({
  stream: null,
  vehicleCount: 0,
  density: 0,
  fps: 0,
  status: 'disconnected',
  detections: [],
  resolution: '1280x720',
  bitrate: 0,
})

const defaultSignalState = (phase: SignalPhase = 'RED'): SignalState => ({
  phase,
  countdown: 0,
  mode: 'AUTO',
  recommendedGreen: 30,
  nextPhase: phase === 'GREEN' ? 'YELLOW' : 'GREEN',
})

const defaultTrafficData = (): TrafficData => ({
  count: 0,
  speed: 0,
  speedIsEstimate: true,
  queueLength: 0,
  density: 0,
  densityLevel: 'LOW',
  trend: 'stable',
  history: [],
})

const defaultSystemStatus = (): SystemStatus => ({
  junctionStatus: 'offline',
  aiEngineStatus: 'stopped',
  esp32Connected: false,
  mqttConnected: false,
  wsConnected: false,
  camerasConnected: { north: false, south: false, east: false, west: false },
  uptime: 0,
  lastHeartbeat: null,
})

export const useAppStore = create<AppState>((set) => ({
  systemStatus: defaultSystemStatus(),
  cameraFeeds: {
    north: defaultCameraFeed(),
    south: defaultCameraFeed(),
    east: defaultCameraFeed(),
    west: defaultCameraFeed(),
  },
  signalState: {
    north: defaultSignalState('RED'),
    south: defaultSignalState('RED'),
    east: defaultSignalState('RED'),
    west: defaultSignalState('RED'),
  },
  trafficData: {
    north: defaultTrafficData(),
    south: defaultTrafficData(),
    east: defaultTrafficData(),
    west: defaultTrafficData(),
  },
  emergencyState: {
    active: false,
    type: null,
    direction: null,
    confidence: 0,
    status: null,
    firstDetected: null,
    estimatedArrival: null,
  },
  notifications: [],
  isDemoMode: false,
  isAutoMode: true,
  performanceMetrics: {
    cpuUsage: 0,
    gpuUsage: 0,
    vramUsed: 0,
    vramTotal: 0,
    inferenceLatency: 0,
    detectionFps: 0,
    memoryUsage: 0,
  },
  lastAIDecision: null,
  emergencyHistory: [],
  signalHistory: [],
  hardwareStatus: {
    lastCommandTimestamp: null,
    lastAckSequenceId: null,
    hardwareError: null,
    wifiRssi: null,
  },
  cameraSnapshots: {
    north: null,
    south: null,
    east: null,
    west: null,
  },

  setSystemStatus: (status) =>
    set((s) => ({ systemStatus: { ...s.systemStatus, ...status } })),

  setCameraFeed: (direction, feed) =>
    set((s) => ({
      cameraFeeds: {
        ...s.cameraFeeds,
        [direction]: { ...s.cameraFeeds[direction], ...feed },
      },
    })),

  setCameraSnapshot: (direction, dataUrl) =>
    set((s) => ({
      cameraSnapshots: { ...s.cameraSnapshots, [direction]: dataUrl },
    })),

  setHardwareStatus: (status) =>
    set((s) => ({ hardwareStatus: { ...s.hardwareStatus, ...status } })),

  setSignalState: (direction, signal) =>
    set((s) => ({
      signalState: {
        ...s.signalState,
        [direction]: { ...s.signalState[direction], ...signal },
      },
    })),

  setTrafficData: (direction, data) =>
    set((s) => ({
      trafficData: {
        ...s.trafficData,
        [direction]: {
          ...s.trafficData[direction],
          ...data,
          history: data.history !== undefined
            ? data.history
            : [
                ...s.trafficData[direction].history.slice(-59),
                ...(data.count !== undefined
                  ? [{ timestamp: Date.now(), count: data.count, density: data.density ?? s.trafficData[direction].density }]
                  : []),
              ],
        },
      },
    })),

  setEmergencyState: (state) =>
    set((s) => ({ emergencyState: { ...s.emergencyState, ...state } })),

  addNotification: (notif) =>
    set((s) => ({
      notifications: [
        {
          ...notif,
          id: `notif-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          timestamp: Date.now(),
          read: false,
        },
        ...s.notifications.slice(0, 49),
      ],
    })),

  markNotificationRead: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
    })),

  clearNotifications: () => set({ notifications: [] }),

  setDemoMode: (enabled) => set({ isDemoMode: enabled }),

  setAutoMode: (enabled) => set({ isAutoMode: enabled }),

  setPerformanceMetrics: (metrics) =>
    set((s) => ({ performanceMetrics: { ...s.performanceMetrics, ...metrics } })),

  setAIDecision: (decision) => set({ lastAIDecision: decision }),

  addEmergencyHistory: (event) =>
    set((s) => ({
      emergencyHistory: [
        { ...event, id: `em-${Date.now()}`, resolvedAt: Date.now() },
        ...s.emergencyHistory.slice(0, 19),
      ],
    })),

  addSignalHistory: (entry) =>
    set((s) => ({
      signalHistory: [
        { ...entry, timestamp: Date.now() },
        ...s.signalHistory.slice(0, 99),
      ],
    })),
}))
