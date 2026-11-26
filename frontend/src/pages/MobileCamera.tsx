import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Camera, RefreshCw, Video, VideoOff, QrCode, Wifi, WifiOff,
  Maximize2, Minimize2, SlidersHorizontal, ChevronDown, SwitchCamera,
} from 'lucide-react'
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
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showControls, setShowControls] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)
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
      } else if (msg.type === 'camera_disconnected') {
        const p = (msg.payload ?? {}) as Record<string, unknown>
        if (p.direction === direction) {
          stopStreaming()
          toast('Stream disconnected from dashboard')
        }
      }
    })
    return () => {
      unsub()
    }
  }, [direction])

  useEffect(() => {
    const onFsChange = () => setIsFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onFsChange)
    return () => {
      document.removeEventListener('fullscreenchange', onFsChange)
      stopStreaming()
    }
  }, [])

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement && containerRef.current?.requestFullscreen) {
        await containerRef.current.requestFullscreen()
        const ori = screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> }
        ori?.lock?.('landscape').catch(() => {})
      } else if (document.fullscreenElement) {
        screen.orientation?.unlock?.()
        await document.exitFullscreen()
      }
    } catch {
      toast.error('Fullscreen mode blocked by browser')
    }
  }

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

  const requestCameraPermission = async (overrideFacing?: 'environment' | 'user'): Promise<MediaStream | null> => {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setPermissionState('denied')
      toast.error('Mobile camera requires HTTPS (or localhost). Open the HTTPS camera URL shown on the Cameras page.')
      return null
    }
    const facing = overrideFacing ?? facingMode
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facing },
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

    // 5. Stream frames preserving actual horizontal/vertical video aspect ratio up to 640px
    const intervalMs = Math.max(40, Math.round(1000 / targetFps))
    let sentInSec = 0
    let lastTick = Date.now()
    frameIntervalRef.current = setInterval(() => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.readyState < 2) return
      if (wsService.getBufferedAmount() > 131072) return

      const vw = video.videoWidth || 640
      const vh = video.videoHeight || 360
      const maxEdge = 640
      const scale = Math.min(1, maxEdge / Math.max(vw, vh))
      const captureW = Math.max(160, Math.round((vw * scale) / 2) * 2)
      const captureH = Math.max(160, Math.round((vh * scale) / 2) * 2)
      if (canvas.width !== captureW || canvas.height !== captureH) {
        canvas.width = captureW
        canvas.height = captureH
      }

      const ctx = canvas.getContext('2d')
      if (!ctx) return

      ctx.drawImage(video, 0, 0, captureW, captureH)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.6)

      const ok = wsService.send({
        type: 'camera_frame',
        payload: {
          direction,
          device_id: deviceId,
          junction_code: junctionCode,
          image: dataUrl,
          resolution: `${captureW}x${captureH}`,
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
    setShowControls(false)
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

  const switchCameraFacing = async () => {
    const nextFacing = facingMode === 'environment' ? 'user' : 'environment'
    setFacingMode(nextFacing)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    const newStream = await requestCameraPermission(nextFacing)
    if (newStream && pcRef.current) {
      const newTrack = newStream.getVideoTracks()[0]
      const sender = pcRef.current.getSenders().find((s) => s.track?.kind === 'video')
      if (sender && newTrack) {
        sender.replaceTrack(newTrack).catch(() => {})
      }
    }
  }

  return (
    <div ref={containerRef} className="relative h-[100dvh] w-screen overflow-hidden bg-black text-slate-100 select-none">
      {/* Full-screen live camera feed (object-contain prevents stretching/cropping in horizontal & vertical modes) */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        onClick={() => streaming && setShowControls((v) => !v)}
        className="absolute inset-0 w-full h-full object-contain bg-black"
      />
      <canvas ref={canvasRef} className="hidden" />

      {/* Camera permission overlay */}
      {permissionState !== 'granted' && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center p-6 text-center bg-slate-950/90 backdrop-blur-sm">
          <VideoOff className="w-12 h-12 text-slate-500 mb-3" />
          <p className="text-sm text-slate-300 mb-4 max-w-xs">
            Grant camera permission to preview & stream road traffic in full screen
          </p>
          <Button variant="primary" size="md" onClick={() => requestCameraPermission()}>
            Enable Camera Access
          </Button>
        </div>
      )}

      {/* Floating Top HUD */}
      <div className="absolute top-0 inset-x-0 z-30 p-3 bg-gradient-to-b from-black/80 via-black/40 to-transparent flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Camera className="w-4 h-4 text-cyan-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-xs font-bold leading-tight truncate">
              {direction.toUpperCase()} CAM
            </p>
            <p className="text-[10px] font-mono text-slate-300 truncate">{deviceId}</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {streaming && (
            <Badge variant="error" dot pulse>{fpsSent} FPS</Badge>
          )}
          <Badge variant={connStatus === 'connected' ? 'success' : connStatus === 'connecting' ? 'warning' : 'default'} dot pulse={streaming}>
            {connStatus === 'connected' ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connStatus.toUpperCase()}
          </Badge>
          <button
            onClick={switchCameraFacing}
            title="Switch Front/Rear Camera"
            className="p-2 rounded-lg bg-slate-900/80 border border-slate-700/80 text-slate-200 hover:bg-slate-800"
          >
            <SwitchCamera className="w-4 h-4" />
          </button>
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
            className="p-2 rounded-lg bg-slate-900/80 border border-slate-700/80 text-slate-200 hover:bg-slate-800"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setShowControls((v) => !v)}
            title={showControls ? 'Hide Controls' : 'Show Controls'}
            className="p-2 rounded-lg bg-slate-900/80 border border-slate-700/80 text-slate-200 hover:bg-slate-800"
          >
            {showControls ? <ChevronDown className="w-4 h-4" /> : <SlidersHorizontal className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Live AI telemetry pill */}
      {streaming && (
        <div className="absolute top-14 inset-x-3 z-20 flex items-center justify-between px-3 py-1.5 rounded-lg bg-black/65 backdrop-blur-md border border-white/10 text-[11px] font-mono pointer-events-none">
          <span className={modelStats.connected ? 'text-emerald-400' : 'text-amber-400'}>
            {modelStats.connected
              ? `AI ${modelStats.fps.toFixed(1)} FPS (${modelStats.inferenceMs.toFixed(1)}ms)`
              : 'Waiting for AI Model ACK...'}
          </span>
          <span className="text-slate-200">
            Vehicles: <strong className="text-cyan-400">{modelStats.vehicleCount}</strong> • {modelStats.densityLevel}
          </span>
        </div>
      )}

      {/* Floating Bottom Controls — scrollable in short landscape screens */}
      {showControls ? (
        <div className="absolute bottom-0 inset-x-0 z-30 p-2 sm:p-3 pb-3 sm:pb-5 bg-gradient-to-t from-black/95 via-black/80 to-transparent">
          <div className="max-w-lg mx-auto max-h-[68dvh] overflow-y-auto bg-slate-950/85 backdrop-blur-md border border-slate-800 rounded-2xl p-3 space-y-2.5">
            <div className="grid grid-cols-4 gap-1.5">
              {DIRECTIONS.map((d) => (
                <button
                  key={d}
                  disabled={streaming}
                  onClick={() => setDirection(d)}
                  className={`py-2 rounded-lg text-xs font-mono uppercase border transition-colors ${
                    direction === d
                      ? 'bg-cyan-500/25 border-cyan-400 text-cyan-200 font-bold'
                      : 'bg-slate-900/90 border-slate-700 text-slate-400'
                  } disabled:opacity-60`}
                >
                  {d}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-2">
              <input
                type="text"
                value={junctionCode}
                onChange={(e) => setJunctionCode(e.target.value)}
                aria-label="Junction Code"
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100"
              />
              <select
                disabled={streaming}
                value={targetFps}
                onChange={(e) => setTargetFps(Number(e.target.value))}
                aria-label="Target FPS"
                className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs font-mono text-slate-100 disabled:opacity-60"
              >
                <option value={10}>10 FPS</option>
                <option value={15}>15 FPS</option>
                <option value={20}>20 FPS</option>
              </select>
              <Button variant="outline" size="sm" className="w-full" leftIcon={<QrCode className="w-3.5 h-3.5" />} onClick={scanQrFromVideo} isLoading={scanningQR}>
                Scan QR
              </Button>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={qrInput}
                onChange={(e) => setQrInput(e.target.value)}
                placeholder="Paste pairing QR / URL"
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200"
              />
              <Button variant="secondary" size="xs" onClick={() => qrInput && applyQrString(qrInput)}>
                Apply
              </Button>
            </div>

            <div className="flex gap-2">
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
      ) : (
        <div className="absolute bottom-4 inset-x-0 z-30 flex justify-center gap-2 px-4">
          {!streaming ? (
            <Button variant="primary" leftIcon={<Video className="w-4 h-4" />} onClick={startStreaming}>
              Start Live Streaming
            </Button>
          ) : (
            <Button variant="danger" leftIcon={<VideoOff className="w-4 h-4" />} onClick={stopStreaming}>
              Stop Stream
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
