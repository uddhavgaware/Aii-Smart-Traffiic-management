import { useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2, VideoOff, RefreshCw, AlertTriangle, Power, ChevronDown, Upload, Film } from 'lucide-react'
import clsx from 'clsx'
import { Direction, useAppStore } from '../../store/appStore'
import { cameraApi } from '../../services/api'
import { wsService } from '../../services/websocket'
import { Badge } from '../ui/Badge'
import { StatusIndicator } from '../ui/StatusIndicator'
import toast from 'react-hot-toast'

type FeedSource = 'live' | 'low_traffic' | 'medium_traffic' | 'heavy_jam' | 'uploaded'

const SOURCE_LABELS: Record<FeedSource, string> = {
  live: 'Live',
  low_traffic: 'Low',
  medium_traffic: 'Med',
  heavy_jam: 'Jam',
  uploaded: 'Clip',
}

interface CameraFeedProps {
  direction: Direction
  onReconnect?: (direction: Direction) => void
  onDisconnect?: (direction: Direction) => void
  compact?: boolean
}

const CLASS_COLORS: Record<string, string> = {
  car: '#22d3ee',
  motorcycle: '#34d399',
  bus: '#a78bfa',
  truck: '#fbbf24',
  auto_rickshaw: '#f472b6',
  ambulance: '#ef4444',
  fire_brigade: '#ef4444',
}

function getDensityBadge(density: number) {
  if (density >= 85) return { label: 'TRAFFIC JAM', variant: 'error' as const }
  if (density >= 65) return { label: 'HIGH', variant: 'warning' as const }
  if (density >= 45) return { label: 'MEDIUM', variant: 'cyan' as const }
  if (density >= 20) return { label: 'NORMAL', variant: 'success' as const }
  return { label: 'LOW', variant: 'default' as const }
}

export function CameraFeed({ direction, onReconnect, onDisconnect, compact = false }: CameraFeedProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const uploadedVideoRef = useRef<HTMLVideoElement>(null)
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [isFullscreen, setIsFullscreen] = useState(false)
  const [sourceMenuOpen, setSourceMenuOpen] = useState(false)
  const [sourceMode, setSourceMode] = useState<FeedSource>('live')
  const [uploadedClipUrl, setUploadedClipUrl] = useState<string | null>(null)
  const [uploadedClipName, setUploadedClipName] = useState<string>('')

  const feed = useAppStore((s) => s.cameraFeeds[direction])
  const snapshot = useAppStore((s) => s.cameraSnapshots[direction])
  const traffic = useAppStore((s) => s.trafficData[direction])
  const isDemoMode = useAppStore((s) => s.isDemoMode)

  useEffect(() => {
    if (videoRef.current && feed.stream) {
      videoRef.current.srcObject = feed.stream
    }
  }, [feed.stream])

  // Close source dropdown on outside click
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setSourceMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  // Cleanup uploaded clip Object URL
  useEffect(() => {
    return () => {
      if (uploadedClipUrl) URL.revokeObjectURL(uploadedClipUrl)
    }
  }, [uploadedClipUrl])

  // Stream uploaded local clip frames into live WebSocket -> YOLOv8 ML pipeline
  useEffect(() => {
    if (sourceMode !== 'uploaded' || !uploadedClipUrl) return
    if (!captureCanvasRef.current) {
      captureCanvasRef.current = document.createElement('canvas')
    }
    const timer = setInterval(() => {
      const vid = uploadedVideoRef.current
      const cvs = captureCanvasRef.current
      if (!vid || !cvs || vid.readyState < 2 || vid.paused) return
      if (wsService.getBufferedAmount() > 32768) return

      const vw = vid.videoWidth || 640
      const vh = vid.videoHeight || 360
      const scale = Math.min(1, 512 / Math.max(vw, vh))
      const cw = Math.max(160, Math.round((vw * scale) / 2) * 2)
      const ch = Math.max(160, Math.round((vh * scale) / 2) * 2)
      if (cvs.width !== cw || cvs.height !== ch) {
        cvs.width = cw
        cvs.height = ch
      }
      const ctx = cvs.getContext('2d')
      if (!ctx) return
      ctx.drawImage(vid, 0, 0, cw, ch)
      const dataUrl = cvs.toDataURL('image/jpeg', 0.48)
      wsService.send({
        type: 'camera_frame',
        payload: {
          direction,
          device_id: `clip-${direction}`,
          junction_code: 'JCT-001',
          image: dataUrl,
          resolution: `${cw}x${ch}`,
          timestamp: Date.now(),
        },
      })
    }, 170)

    return () => clearInterval(timer)
  }, [sourceMode, uploadedClipUrl, direction])

  const clearUploadedClip = () => {
    if (uploadedClipUrl) URL.revokeObjectURL(uploadedClipUrl)
    setUploadedClipUrl(null)
    setUploadedClipName('')
  }

  const handleSelectSource = async (next: 'live' | 'low_traffic' | 'medium_traffic' | 'heavy_jam') => {
    setSourceMenuOpen(false)
    clearUploadedClip()
    setSourceMode(next)
    try {
      await cameraApi.setSource(direction, next)
      if (next === 'live') {
        useAppStore.getState().setCameraSnapshot(direction, null)
        toast.success(`${direction.toUpperCase()} switched to Live Camera`)
      } else {
        toast.success(`${direction.toUpperCase()} playing ${SOURCE_LABELS[next]} traffic clip`)
      }
    } catch {
      toast.error(`Failed to set ${direction.toUpperCase()} traffic source`)
    }
  }

  const handleUploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    setSourceMenuOpen(false)
    if (!file) return

    clearUploadedClip()
    try {
      await cameraApi.setSource(direction, 'live')
    } catch {
      // ignore if backend already in live mode
    }
    const url = URL.createObjectURL(file)
    setUploadedClipUrl(url)
    setUploadedClipName(file.name)
    setSourceMode('uploaded')
    useAppStore.getState().setCameraFeed(direction, { status: 'connected' })
    toast.success(`Streaming uploaded clip on ${direction.toUpperCase()}`)
  }

  const handleDisconnectClick = () => {
    clearUploadedClip()
    setSourceMode('live')
    onDisconnect?.(direction)
  }

  // Draw bounding boxes on canvas overlay aligned to object-contain frame area
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const cw = canvas.width
    const ch = canvas.height
    ctx.clearRect(0, 0, cw, ch)

    if (!feed.detections || feed.detections.length === 0) return

    // Match inner display rectangle inside 16:9 canvas when object-contain is active
    const [rw, rh] = (feed.resolution || '640x360').split('x').map(Number)
    let ox = 0
    let oy = 0
    let dw = cw
    let dh = ch
    if (rw > 0 && rh > 0) {
      const srcAspect = rw / rh
      const boxAspect = cw / ch
      if (srcAspect > boxAspect) {
        dh = cw / srcAspect
        oy = (ch - dh) / 2
      } else {
        dw = ch * srcAspect
        ox = (cw - dw) / 2
      }
    }

    for (const det of feed.detections) {
      const [nx, ny, nw, nh] = det.bbox
      const x = ox + nx * dw
      const y = oy + ny * dh
      const w = nw * dw
      const h = nh * dh
      const isEmergency = det.class === 'ambulance' || det.class === 'fire_brigade'
      const color = CLASS_COLORS[det.class] ?? '#22d3ee'

      ctx.strokeStyle = color
      ctx.lineWidth = isEmergency ? 3 : 2
      ctx.strokeRect(x, y, w, h)

      if (isEmergency) {
        ctx.fillStyle = 'rgba(239, 68, 68, 0.14)'
        ctx.fillRect(x, y, w, h)
      }

      const label = `${det.class}${det.trackId !== undefined ? ` #${det.trackId}` : ''} ${(det.confidence * 100).toFixed(0)}%`
      ctx.font = '600 11px "JetBrains Mono", monospace'
      const textWidth = ctx.measureText(label).width
      const labelY = Math.max(16, y)
      ctx.fillStyle = isEmergency ? '#dc2626' : '#0f172a'
      ctx.fillRect(x, labelY - 16, textWidth + 8, 16)
      ctx.fillStyle = isEmergency ? '#ffffff' : color
      ctx.fillText(label, x + 4, labelY - 4)
    }
  }, [feed.detections, feed.resolution])

  const densityInfo = getDensityBadge(traffic.density || feed.density)
  const hasEmergency = feed.detections.some((d) => d.class === 'ambulance' || d.class === 'fire_brigade')

  return (
    <div
      className={clsx(
        'card relative flex flex-col transition-all',
        hasEmergency && 'border-red-500/70 shadow-glow-red',
        isFullscreen && 'fixed inset-4 z-50 bg-slate-950'
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={handleUploadFile}
      />

      {/* Header */}
      <div className="px-3 py-2 border-b border-slate-800 flex items-center justify-between gap-2 bg-slate-900/60 rounded-t-xl">
        <div className="flex items-center gap-1.5 relative" ref={menuRef}>
          <span className="text-xs font-bold uppercase tracking-wider text-cyan-400 font-mono">
            {direction}
          </span>
          <StatusIndicator status={feed.status} size="xs" />

          {/* Small arrow dropdown to pick traffic clip or upload video */}
          <button
            onClick={() => setSourceMenuOpen((o) => !o)}
            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[10px] font-mono text-slate-300 transition-colors"
            title="Select traffic clip or upload video"
          >
            <span>{SOURCE_LABELS[sourceMode]}</span>
            <ChevronDown className="w-3 h-3 text-cyan-400" />
          </button>

          {sourceMenuOpen && (
            <div className="absolute top-full left-0 mt-1 w-48 rounded-lg bg-slate-900 border border-slate-700 shadow-xl py-1 z-40 text-xs">
              <button
                onClick={() => handleSelectSource('live')}
                className={clsx(
                  'w-full px-3 py-1.5 text-left flex items-center justify-between hover:bg-slate-800',
                  sourceMode === 'live' ? 'text-cyan-400 font-semibold' : 'text-slate-200'
                )}
              >
                <span>Live Mobile Camera</span>
              </button>
              <div className="my-1 border-t border-slate-800" />
              <button
                onClick={() => handleSelectSource('low_traffic')}
                className={clsx(
                  'w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-slate-800',
                  sourceMode === 'low_traffic' ? 'text-emerald-400 font-semibold' : 'text-slate-200'
                )}
              >
                <Film className="w-3.5 h-3.5 text-emerald-400" />
                <span>Low Traffic Clip</span>
              </button>
              <button
                onClick={() => handleSelectSource('medium_traffic')}
                className={clsx(
                  'w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-slate-800',
                  sourceMode === 'medium_traffic' ? 'text-amber-400 font-semibold' : 'text-slate-200'
                )}
              >
                <Film className="w-3.5 h-3.5 text-amber-400" />
                <span>Medium Traffic Clip</span>
              </button>
              <button
                onClick={() => handleSelectSource('heavy_jam')}
                className={clsx(
                  'w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-slate-800',
                  sourceMode === 'heavy_jam' ? 'text-red-400 font-semibold' : 'text-slate-200'
                )}
              >
                <Film className="w-3.5 h-3.5 text-red-400" />
                <span>Heavy / Jam Clip</span>
              </button>
              <div className="my-1 border-t border-slate-800" />
              <button
                onClick={() => fileInputRef.current?.click()}
                className={clsx(
                  'w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-slate-800',
                  sourceMode === 'uploaded' ? 'text-cyan-400 font-semibold' : 'text-cyan-300'
                )}
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Upload Video Clip...</span>
              </button>
            </div>
          )}

          {hasEmergency && (
            <Badge variant="error" size="xs" pulse>
              <AlertTriangle className="w-3 h-3" /> EMERGENCY
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={densityInfo.variant} size="xs">
            {densityInfo.label}
          </Badge>
          <span className="text-[11px] font-mono text-slate-400">
            {feed.fps.toFixed(1)} FPS
          </span>
          {onDisconnect && (feed.status === 'connected' || sourceMode !== 'live') && (
            <button
              onClick={handleDisconnectClick}
              className="p-1 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition-colors"
              title={`Disconnect ${direction} camera`}
            >
              <Power className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={() => setIsFullscreen((v) => !v)}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Video viewport — keep strict aspect-video with object-contain so horizontal & vertical cameras never crop/skew bboxes */}
      <div className={clsx('relative bg-black overflow-hidden rounded-b-xl', compact ? 'aspect-video' : 'min-h-[240px] aspect-video')}>
        {feed.stream ? (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-contain"
          />
        ) : uploadedClipUrl ? (
          <video
            ref={uploadedVideoRef}
            src={uploadedClipUrl}
            autoPlay
            loop
            playsInline
            muted
            className="w-full h-full object-contain"
          />
        ) : snapshot ? (
          <img
            src={snapshot}
            alt={`${direction} live camera frame`}
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 p-4 text-center">
            <VideoOff className="w-8 h-8 mb-2 text-slate-600" />
            <p className="text-xs font-medium text-slate-400">
              {isDemoMode ? 'Demo Stream Waiting' : 'No Live Camera Stream'}
            </p>
            <p className="text-[11px] text-slate-600 mt-0.5">
              Pair a mobile device via /camera or QR code for {direction.toUpperCase()}
            </p>
            {onReconnect && (
              <button
                onClick={() => onReconnect(direction)}
                className="mt-2.5 inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 px-2.5 py-1 rounded border border-cyan-500/30 bg-cyan-500/10"
              >
                <RefreshCw className="w-3 h-3" /> Request Reconnect
              </button>
            )}
          </div>
        )}

        {/* Bounding box canvas overlay */}
        <canvas
          ref={canvasRef}
          width={640}
          height={360}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />

        {/* Bottom HUD overlay */}
        <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none">
          <div className="px-2 py-1 rounded bg-slate-950/80 border border-slate-800 backdrop-blur-sm text-[11px] font-mono text-slate-200">
            Vehicles: <span className="text-cyan-400 font-bold">{feed.vehicleCount || traffic.count}</span>
          </div>
          <div className="px-2 py-1 rounded bg-slate-950/80 border border-slate-800 backdrop-blur-sm text-[11px] font-mono text-slate-400">
            {uploadedClipName ? uploadedClipName.slice(0, 18) : feed.resolution}
          </div>
        </div>
      </div>
    </div>
  )
}
