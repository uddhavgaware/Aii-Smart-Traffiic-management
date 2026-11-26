import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import toast from 'react-hot-toast'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api`
  : '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 45000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('auth_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (
      error.response?.status === 401 &&
      !window.location.pathname.startsWith('/login') &&
      !window.location.pathname.startsWith('/camera')
    ) {
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    } else if (error.response?.status === 500) {
      toast.error('Server error — please try again')
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ access_token: string; refresh_token: string; token_type: string }>('/auth/login', {
      username,
      password,
    }),
  logout: () => api.post('/auth/logout'),
  me: () => api.get<{ id: number; username: string; email: string; role: string }>('/auth/me'),
}

export const systemApi = {
  getStatus: () =>
    api.get<{
      junction_status: string
      ai_engine_status: string
      esp32_connected: boolean
      mqtt_connected: boolean
      demo_mode: boolean
      uptime: number
      version: string
    }>('/system/status'),
  getPerformanceMetrics: () =>
    api.get<{
      cpu_usage: number
      gpu_usage: number
      vram_used: number
      vram_total: number
      inference_latency: number
      detection_fps: number
      memory_usage: number
    }>('/system/metrics'),
  getSettings: () => api.get('/system/settings'),
  updateSettings: (settings: Record<string, unknown>) => api.patch('/system/settings', settings),
  restartAIEngine: () => api.post('/system/ai/restart'),
  toggleDemoMode: (enabled: boolean) => api.post('/system/demo/toggle', { enabled }),
  getEvents: (limit = 100) => api.get(`/system/events?limit=${limit}`),
  acknowledgeEvent: (id: number) => api.post(`/system/events/${id}/acknowledge`),
}

export const signalApi = {
  getCurrentState: () => api.get('/signals/state'),
  setMode: (mode: 'AUTO' | 'MANUAL') => api.post('/signals/mode', { mode }),
  override: (direction: string, phase: string, duration?: number, reason?: string) =>
    api.post('/signals/override', { direction, phase, duration: duration ?? 30, reason }),
  updateTiming: (config: {
    min_green: number
    max_green: number
    yellow_duration: number
    all_red_duration: number
    max_wait?: number
  }) => api.patch('/signals/timing', config),
  getConfig: () => api.get('/signals/config'),
  getHistory: (limit = 50) => api.get(`/signals/history?limit=${limit}`),
}

export const trafficApi = {
  getCurrent: () => api.get('/traffic/current'),
  getHistory: (direction?: string, hours = 24) =>
    api.get(`/traffic/history?${direction ? `direction=${direction}&` : ''}hours=${hours}`),
  exportCSV: (from: number, to: number) =>
    api.get(`/traffic/export?from=${from}&to=${to}`, { responseType: 'blob' }),
  getAnalytics: (period: string) => api.get(`/traffic/analytics?period=${period}`),
}

export const cameraApi = {
  getAll: () => api.get('/cameras'),
  register: (data: {
    junction_code?: string
    direction: string
    device_id?: string
    allow_replace?: boolean
    stream_url?: string
  }) => api.post('/cameras/register', data),
  unregister: (direction: string) => api.delete(`/cameras/${direction}`),
  getJunctionCode: () => api.get<{ code: string; expires_in: number }>('/cameras/junction-code'),
  reconnect: (direction: string) => api.post(`/cameras/${direction}/reconnect`),
  disconnect: (direction: string) => api.post(`/cameras/${direction}/disconnect`),
  setSource: (direction: string, source: 'live' | 'low_traffic' | 'medium_traffic' | 'heavy_jam') =>
    api.post(`/cameras/${direction}/source`, { source }),
  getStatus: (direction: string) => api.get(`/cameras/${direction}/status`),
  getWebRTCConfig: () => api.get('/cameras/webrtc/config'),
  sendOffer: (payload: { camera_id: string; sdp: string; type: string }) =>
    api.post('/cameras/webrtc/offer', payload),
  sendAnswer: (payload: { camera_id: string; sdp: string; type: string }) =>
    api.post('/cameras/webrtc/answer', payload),
  sendIce: (payload: { camera_id: string; candidate: string; sdp_mid?: string; sdp_mline_index?: number }) =>
    api.post('/cameras/webrtc/ice', payload),
}

export const emergencyApi = {
  getCurrent: () => api.get('/emergency/current'),
  getHistory: (limit = 20) => api.get(`/emergency/history?limit=${limit}`),
  acknowledge: (id: string) => api.post(`/emergency/${id}/acknowledge`),
  manualClear: () => api.post('/emergency/clear', {}),
}

export const hardwareApi = {
  getStatus: () => api.get('/hardware/status'),
  reboot: () => api.post('/hardware/reboot'),
  testLights: (direction: string) => api.post('/hardware/test', { direction }),
}

export default api
