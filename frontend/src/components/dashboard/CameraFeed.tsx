import { useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2, VideoOff, RefreshCw, AlertTriangle, Power } from 'lucide-react'
import clsx from 'clsx'
import { Direction, useAppStore } from '../../store/appStore'
import { Badge } from '../ui/Badge'
import { StatusIndicator } from '../ui/StatusIndicator'

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
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const feed = useAppStore((s) => s.cameraFeeds[direction])
  const snapshot = useAppStore((s) => s.cameraSnapshots[direction])
  const traffic = useAppStore((s) => s.trafficData[direction])
  const isDemoMode = useAppStore((s) => s.isDemoMode)

  useEffect(() => {
    if (videoRef.current && feed.stream) {
      videoRef.current.srcObject = feed.stream
    }
  }, [feed.stream])

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
        'card overflow-hidden flex flex-col transition-all',
        hasEmergency && 'border-red-500/70 shadow-glow-red',
        isFullscreen && 'fixed inset-4 z-50 bg-slate-950'
      )}
    >
      {/* Header */}
      <div className="px-3 py-2 border-b border-slate-800 flex items-center justify-between gap-2 bg-slate-900/60">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-cyan-400 font-mono">
            {direction}
          </span>
          <StatusIndicator status={feed.status} size="xs" />
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
          {onDisconnect && feed.status === 'connected' && (
            <button
              onClick={() => onDisconnect(direction)}
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
      <div className={clsx('relative bg-black overflow-hidden', compact ? 'aspect-video' : 'min-h-[240px] aspect-video')}>
        {feed.stream ? (
          <video
            ref={videoRef}
            autoPlay
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
            {feed.resolution}
          </div>
        </div>
      </div>
    </div>
  )
}
