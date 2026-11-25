import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Camera, RefreshCw, Video, VideoOff, QrCode, Wifi, WifiOff } from 'lucide-react'
import { Direction } from '../store/appStore'
import { cameraApi } from '../services/api'
import { wsService } from '../services/websocket'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import toast from 'react-hot-toast'

const DIRECTIONS: Direction[] = ['north', 'south', 'east', 'west']

export default function MobileCamera() {
  const [searchParams] = useSearchParams()
  const initialDir = (searchParams.get('direction') as Direction) || 'north'
  const initialJunction = searchParams.get('junction') || 'JCT-001'

  const [direction, setDirection] = useState<Direction>(
    DIRECTIONS.includes(initialDir) ? initialDir : 'north'
  )
  const [junctionCode, setJunctionCode] = useState(initialJunction)
  const [deviceId] = useState(() => {
    const saved = localStorage.getItem('mobile_cam_device_id')
    if (saved) return saved
    const fresh = `phone-${Math.random().toString(36).slice(2, 10)}`
    localStorage.setItem('mobile_cam_device_id', fresh)
    return fresh
  })

  const [permissionState, setPermissionState] = useState<'idle' | 'granted' | 'denied'>('idle')
  const [streaming, setStreaming] = useState(false)
  const [connStatus, setConnStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const [fpsSent, setFpsSent] = useState(0)
  const [targetFps, setTargetFps] = useState(15)
  const [qrInput, setQrInput] = useState('')
  const [scanningQR, setScanningQR] = useState(false)
  const [modelStats, setModelStats] = useState<{
    connected: boolean
    vehicleCount: number
    densityLevel: string
    inferenceMs: number
    fps: number
  }>({ connected: false, vehicleCount: 0, densityLevel: 'LOW', inferenceMs: 0, fps: 0 })

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const frameIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Register PWA service worker and subscribe to ML model acknowledgements
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {})
    }
    const unsub = wsService.addListener((msg) => {
      if (msg.type === 'model_ack') {
        const p = (msg.payload ?? {}) as Record<string, unknown>
        if (p.direction === direction) {
          setModelStats({
            connected: true,
            vehicleCount: Number(p.vehicle_count ?? 0),
            densityLevel: String(p.density_level ?? 'LOW'),
            inferenceMs: Number(p.inference_ms ?? 0),
            fps: Number(p.fps ?? 0),
          })
        }
      }
    })
    return () => {
      unsub()
    }
  }, [direction])

  useEffect(() => {
    return () => {
      stopStreaming()
    }
  }, [])

  const applyQrString = (raw: string) => {
    try {
      const parsed = JSON.parse(raw)
      if (parsed.direction && DIRECTIONS.includes(parsed.direction)) {
        setDirection(parsed.direction)
      }
      if (parsed.junction_code) {
        setJunctionCode(parsed.junction_code)
      }
      toast.success(`Paired via QR: ${String(parsed.direction || direction).toUpperCase()}`)
      return true
    } catch {
      // Fallback: check URL query string
      try {
        const u = new URL(raw)
        const d = u.searchParams.get('direction') as Direction
        const j = u.searchParams.get('junction')
        if (d && DIRECTIONS.includes(d)) setDirection(d)
        if (j) setJunctionCode(j)
        toast.success('Parsed pairing URL')
        return true
      } catch {
        toast.error('Unrecognized QR payload')
        return false
      }
    }
  }

  const requestCameraPermission = async (): Promise<MediaStream | null> => {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setPermissionState('denied')
      toast.error('Mobile camera requires HTTPS (or localhost). Open the HTTPS camera URL shown on the Cameras page.')
      return null
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 15, max: 30 },
        },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
      setPermissionState('granted')
      return stream
    } catch {
      setPermissionState('denied')
      toast.error('Camera permission denied or camera unavailable')
      return null
    }
  }

  const scanQrFromVideo = async () => {
    const stream = streamRef.current ?? (await requestCameraPermission())
    if (!stream || !videoRef.current) return

    const Detector = (window as unknown as { BarcodeDetector?: new (opts: { formats: string[] }) => { detect: (el: HTMLVideoElement) => Promise<Array<{ rawValue: string }>> } }).BarcodeDetector
    if (!Detector) {
      toast.error('In-browser QR detector unsupported on this browser — paste pairing JSON or URL below')
      return
    }

    setScanningQR(true)
    const detector = new Detector({ formats: ['qr_code'] })
    const timer = setInterval(async () => {
      if (!videoRef.current) return
      try {
        const codes = await detector.detect(videoRef.current)
        if (codes.length > 0 && applyQrString(codes[0].rawValue)) {
          clearInterval(timer)
          setScanningQR(false)
        }
      } catch {
        // continue scanning
      }
    }, 500)
    setTimeout(() => {
      clearInterval(timer)
      setScanningQR(false)
    }, 15000)
  }

  const startStreaming = async () => {
    setConnStatus('connecting')
    const stream = streamRef.current ?? (await requestCameraPermission())
    if (!stream) {
      setConnStatus('disconnected')
      return
    }

    // 1. Register camera with backend (non-blocking warning if auth token absent)
    try {
      await cameraApi.register({
        junction_code: junctionCode,
        direction,
        device_id: deviceId,
        allow_replace: true,
      })
    } catch {
      // Continue WebSocket streaming with junction_code handshake
    }

    // 2. Fetch WebRTC ICE/TURN config for cross-network connectivity
    let iceServers: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }]
    try {
      const cfg = await cameraApi.getWebRTCConfig()
      if (cfg.data?.ice_servers) {
        iceServers = cfg.data.ice_servers
      }
    } catch {
      // fallback STUN
    }

    // 3. Connect WebSocket signaling & frame transport (camera client mode avoids stale JWT failure)
    wsService.connect('')

    // 4. Initialize RTCPeerConnection with TURN/STUN
    try {
      const pc = new RTCPeerConnection({ iceServers })
      pcRef.current = pc
      stream.getTracks().forEach((track) => pc.addTrack(track, stream))

      pc.onicecandidate = (e) => {
        if (e.candidate) {
          wsService.send({
            type: 'webrtc_ice',
            payload: {
              camera_id: deviceId,
              direction,
              candidate: e.candidate.candidate,
              sdp_mid: e.candidate.sdpMid,
              sdp_mline_index: e.candidate.sdpMLineIndex,
            },
          })
        }
      }

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      wsService.send({
        type: 'webrtc_offer',
        payload: {
          camera_id: deviceId,
          direction,
          junction_code: junctionCode,
          sdp: offer.sdp,
          type: offer.type,
        },
      })
    } catch (err) {
      console.warn('WebRTC offer setup warning:', err)
    }

    // 5. Stream frames with preallocated canvas & WS backpressure guard
    const captureW = 512
    const captureH = 288
    if (canvasRef.current) {
      canvasRef.current.width = captureW
      canvasRef.current.height = captureH
    }
    const intervalMs = Math.max(40, Math.round(1000 / targetFps))
    let sentInSec = 0
    let lastTick = Date.now()
    frameIntervalRef.current = setInterval(() => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.readyState < 2) return
      if (wsService.getBufferedAmount() > 131072) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      ctx.drawImage(video, 0, 0, captureW, captureH)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.55)

      const ok = wsService.send({
        type: 'camera_frame',
        payload: {
          direction,
          device_id: deviceId,
          junction_code: junctionCode,
          image: dataUrl,
          timestamp: Date.now(),
        },
      })

      if (ok) {
        sentInSec += 1
        setConnStatus('connected')
      }
      if (Date.now() - lastTick >= 1000) {
        setFpsSent(sentInSec)
        sentInSec = 0
        lastTick = Date.now()
      }
    }, intervalMs)

    setStreaming(true)
    toast.success(`Live streaming started for ${direction.toUpperCase()}`)
  }

  const stopStreaming = () => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current)
      frameIntervalRef.current = null
    }
    if (pcRef.current) {
      pcRef.current.close()
      pcRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setStreaming(false)
    setConnStatus('disconnected')
    setFpsSent(0)
    setModelStats({ connected: false, vehicleCount: 0, densityLevel: 'LOW', inferenceMs: 0, fps: 0 })
  }

  const handleRestart = async () => {
    stopStreaming()
    await new Promise((r) => setTimeout(r, 300))
    await startStreaming()
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 flex flex-col items-center">
      <div className="w-full max-w-lg space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between card px-4 py-3">
          <div className="flex items-center gap-2.5">
            <Camera className="w-5 h-5 text-cyan-400" />
            <div>
              <h1 className="text-sm font-bold">Mobile Traffic Camera</h1>
              <p className="text-[11px] font-mono text-slate-400">{deviceId}</p>
            </div>
          </div>
          <Badge variant={connStatus === 'connected' ? 'success' : connStatus === 'connecting' ? 'warning' : 'default'} dot pulse={streaming}>
            {connStatus === 'connected' ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connStatus.toUpperCase()}
          </Badge>
        </div>

        {/* Video preview */}
        <div className="card overflow-hidden">
          <div className="relative aspect-video bg-black flex items-center justify-center">
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
            <canvas ref={canvasRef} className="hidden" />
            {permissionState !== 'granted' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center bg-slate-950/90">
                <VideoOff className="w-10 h-10 text-slate-600 mb-2" />
                <p className="text-xs text-slate-400 mb-3">Grant camera permission to preview & stream road traffic</p>
                <Button variant="primary" size="sm" onClick={requestCameraPermission}>
                  Enable Camera Access
                </Button>
              </div>
            )}
            {streaming && (
              <div className="absolute top-2 left-2 right-2 flex justify-between pointer-events-none">
                <Badge variant="error" dot pulse>LIVE • {direction.toUpperCase()}</Badge>
                <Badge variant="cyan">{fpsSent} FPS</Badge>
              </div>
            )}
          </div>
          {streaming && (
            <div className="px-3 py-2 bg-slate-900/90 border-t border-slate-800 flex items-center justify-between text-[11px] font-mono">
              <span className={modelStats.connected ? 'text-emerald-400' : 'text-amber-400'}>
                {modelStats.connected
                  ? `AI ${modelStats.fps.toFixed(1)} FPS (${modelStats.inferenceMs.toFixed(1)}ms)`
                  : 'Waiting for AI Model ACK...'}
              </span>
              <span className="text-slate-300">
                Vehicles: <strong className="text-cyan-400">{modelStats.vehicleCount}</strong> • {modelStats.densityLevel}
              </span>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="card p-4 space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Select Junction Direction</label>
            <div className="grid grid-cols-4 gap-2">
              {DIRECTIONS.map((d) => (
                <button
                  key={d}
                  disabled={streaming}
                  onClick={() => setDirection(d)}
                  className={`py-2.5 rounded-lg text-xs font-mono uppercase border transition-colors ${
                    direction === d
                      ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 font-bold'
                      : 'bg-slate-900 border-slate-700 text-slate-400'
                  } disabled:opacity-60`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Junction Code</label>
              <input
                type="text"
                value={junctionCode}
                onChange={(e) => setJunctionCode(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Target FPS</label>
              <select
                disabled={streaming}
                value={targetFps}
                onChange={(e) => setTargetFps(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-2 text-xs font-mono text-slate-100 disabled:opacity-60"
              >
                <option value={10}>10 FPS</option>
                <option value={15}>15 FPS</option>
                <option value={20}>20 FPS</option>
              </select>
            </div>
            <div className="flex items-end">
              <Button variant="outline" size="sm" className="w-full" leftIcon={<QrCode className="w-3.5 h-3.5" />} onClick={scanQrFromVideo} isLoading={scanningQR}>
                Scan QR
              </Button>
            </div>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={qrInput}
              onChange={(e) => setQrInput(e.target.value)}
              placeholder="Or paste pairing QR / URL here"
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
            />
            <Button variant="secondary" size="xs" onClick={() => qrInput && applyQrString(qrInput)}>
              Apply
            </Button>
          </div>

          <div className="flex gap-2 pt-2">
            {!streaming ? (
              <Button variant="primary" className="flex-1" leftIcon={<Video className="w-4 h-4" />} onClick={startStreaming}>
                Start Live Streaming
              </Button>
            ) : (
              <>
                <Button variant="danger" className="flex-1" leftIcon={<VideoOff className="w-4 h-4" />} onClick={stopStreaming}>
                  Stop Stream
                </Button>
                <Button variant="secondary" leftIcon={<RefreshCw className="w-4 h-4" />} onClick={handleRestart}>
                  Reconnect
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
