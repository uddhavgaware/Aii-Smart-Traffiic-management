import { useEffect, useRef } from 'react'
import { Direction, useAppStore } from '../../store/appStore'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'

const PHASE_COLOR = {
  RED: '#ef4444',
  YELLOW: '#fbbf24',
  GREEN: '#34d399',
}

export function DigitalTwin() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const signalState = useAppStore((s) => s.signalState)
  const trafficData = useAppStore((s) => s.trafficData)
  const cameraFeeds = useAppStore((s) => s.cameraFeeds)
  const emergencyState = useAppStore((s) => s.emergencyState)
  const esp32Connected = useAppStore((s) => s.systemStatus.esp32Connected)
  const isDemoMode = useAppStore((s) => s.isDemoMode)

  useEffect(() => {
    let animId = 0
    let lastDraw = 0

    const draw = (now: number) => {
      animId = requestAnimationFrame(draw)
      if (now - lastDraw < 100) return // 10 FPS lightweight render for RTX 3050 + i5
      lastDraw = now

      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const w = canvas.width
      const h = canvas.height
      const cx = w / 2
      const cy = h / 2
      const roadW = 112
      const halfRoad = roadW / 2

      // Clear background
      ctx.fillStyle = '#020617'
      ctx.fillRect(0, 0, w, h)

      // Subtle grass/urban blocks
      ctx.fillStyle = '#0b1325'
      ctx.fillRect(0, 0, cx - halfRoad - 6, cy - halfRoad - 6)
      ctx.fillRect(cx + halfRoad + 6, 0, cx - halfRoad - 6, cy - halfRoad - 6)
      ctx.fillRect(0, cy + halfRoad + 6, cx - halfRoad - 6, cy - halfRoad - 6)
      ctx.fillRect(cx + halfRoad + 6, cy + halfRoad + 6, cx - halfRoad - 6, cy - halfRoad - 6)

      // Roads
      ctx.fillStyle = '#1e293b'
      ctx.fillRect(cx - halfRoad, 0, roadW, h) // N-S
      ctx.fillRect(0, cy - halfRoad, w, roadW) // E-W

      // Intersection box
      ctx.fillStyle = '#243247'
      ctx.fillRect(cx - halfRoad, cy - halfRoad, roadW, roadW)

      // Road lane dividers (dashed yellow/white)
      ctx.strokeStyle = '#64748b'
      ctx.lineWidth = 2
      ctx.setLineDash([10, 10])
      // Vertical divider
      ctx.beginPath()
      ctx.moveTo(cx, 0)
      ctx.lineTo(cx, cy - halfRoad)
      ctx.moveTo(cx, cy + halfRoad)
      ctx.lineTo(cx, h)
      // Horizontal divider
      ctx.moveTo(0, cy)
      ctx.lineTo(cx - halfRoad, cy)
      ctx.moveTo(cx + halfRoad, cy)
      ctx.lineTo(w, cy)
      ctx.stroke()
      ctx.setLineDash([])

      // Stop lines
      ctx.strokeStyle = '#e2e8f0'
      ctx.lineWidth = 3
      ctx.beginPath()
      // North approach (top half, left lane in right-hand or incoming)
      ctx.moveTo(cx - halfRoad, cy - halfRoad - 4)
      ctx.lineTo(cx, cy - halfRoad - 4)
      // South approach
      ctx.moveTo(cx, cy + halfRoad + 4)
      ctx.lineTo(cx + halfRoad, cy + halfRoad + 4)
      // West approach
      ctx.moveTo(cx - halfRoad - 4, cy)
      ctx.lineTo(cx - halfRoad - 4, cy + halfRoad)
      // East approach
      ctx.moveTo(cx + halfRoad + 4, cy - halfRoad)
      ctx.lineTo(cx + halfRoad + 4, cy)
      ctx.stroke()

      // Draw vehicles from real traffic count & detections (no fake random simulation)
      const drawApproach = (dir: Direction) => {
        const count = Math.min(trafficData[dir].count || cameraFeeds[dir].vehicleCount, 18)
        const queue = Math.min(trafficData[dir].queueLength, 100)
        const phase = signalState[dir].phase
        const isEmergencyDir = emergencyState.active && emergencyState.direction === dir

        // Queue bar indicator along curb
        if (queue > 0) {
          ctx.fillStyle = queue > 65 ? 'rgba(239,68,68,0.35)' : 'rgba(251,191,36,0.28)'
          const barLen = (queue / 100) * (cy - halfRoad - 20)
          if (dir === 'north') ctx.fillRect(cx - halfRoad + 4, cy - halfRoad - 8 - barLen, 6, barLen)
          if (dir === 'south') ctx.fillRect(cx + halfRoad - 10, cy + halfRoad + 8, 6, barLen)
          if (dir === 'west') ctx.fillRect(cx - halfRoad - 8 - barLen, cy + halfRoad - 10, barLen, 6)
          if (dir === 'east') ctx.fillRect(cx + halfRoad + 8, cy - halfRoad + 4, barLen, 6)
        }

        // Draw detected vehicles queued/approaching
        for (let i = 0; i < count; i++) {
          const laneOffset = i % 2 === 0 ? 16 : 36
          const slot = Math.floor(i / 2)
          const spacing = 18
          const motionOffset = phase === 'GREEN' ? ((now / 60 + i * 8) % 14) : 0
          const dist = halfRoad + 18 + slot * spacing - motionOffset

          let vx = cx
          let vy = cy
          let vw = 12
          let vh = 14

          if (dir === 'north') {
            vx = cx - laneOffset - 6
            vy = cy - dist
          } else if (dir === 'south') {
            vx = cx + laneOffset - 6
            vy = cy + dist - 14
          } else if (dir === 'west') {
            vx = cx - dist
            vy = cy + laneOffset - 6
            vw = 14
            vh = 12
          } else {
            vx = cx + dist - 14
            vy = cy - laneOffset - 6
            vw = 14
            vh = 12
          }

          const isEmergVehicle = isEmergencyDir && i === 0
          ctx.fillStyle = isEmergVehicle ? '#ef4444' : '#38bdf8'
          ctx.fillRect(vx, vy, vw, vh)
          ctx.strokeStyle = isEmergVehicle ? '#fecaca' : '#0f172a'
          ctx.lineWidth = isEmergVehicle ? 2 : 1
          ctx.strokeRect(vx, vy, vw, vh)
        }

        // Traffic light beacon at stop line
        const sigColor = PHASE_COLOR[phase]
        let lx = cx
        let ly = cy
        if (dir === 'north') { lx = cx - halfRoad - 14; ly = cy - halfRoad - 14 }
        if (dir === 'south') { lx = cx + halfRoad + 14; ly = cy + halfRoad + 14 }
        if (dir === 'west') { lx = cx - halfRoad - 14; ly = cy + halfRoad + 14 }
        if (dir === 'east') { lx = cx + halfRoad + 14; ly = cy - halfRoad - 14 }

        ctx.beginPath()
        ctx.arc(lx, ly, 9, 0, Math.PI * 2)
        ctx.fillStyle = '#0f172a'
        ctx.fill()
        ctx.lineWidth = 2
        ctx.strokeStyle = sigColor
        ctx.stroke()

        ctx.beginPath()
        ctx.arc(lx, ly, 5, 0, Math.PI * 2)
        ctx.fillStyle = sigColor
        ctx.fill()

        // Direction label + count
        ctx.fillStyle = '#94a3b8'
        ctx.font = '600 11px "JetBrains Mono", monospace'
        if (dir === 'north') ctx.fillText(`N (${trafficData.north.count})`, cx - 22, 18)
        if (dir === 'south') ctx.fillText(`S (${trafficData.south.count})`, cx - 22, h - 10)
        if (dir === 'west') ctx.fillText(`W (${trafficData.west.count})`, 10, cy - halfRoad - 12)
        if (dir === 'east') ctx.fillText(`E (${trafficData.east.count})`, w - 58, cy - halfRoad - 12)
      }

      ;(['north', 'south', 'east', 'west'] as Direction[]).forEach(drawApproach)
    }

    animId = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(animId)
  }, [signalState, trafficData, cameraFeeds, emergencyState])

  return (
    <Card
      title="2D Junction Digital Twin"
      subtitle="Live geometry synced to detected vehicles & ESP32 signal states"
      headerRight={
        <div className="flex items-center gap-2">
          <Badge variant={esp32Connected ? 'success' : isDemoMode ? 'warning' : 'default'} size="xs">
            {esp32Connected ? 'ESP32 SYNCED' : isDemoMode ? 'DEMO SYNC' : 'AWAITING HARDWARE'}
          </Badge>
        </div>
      }
    >
      <div className="flex flex-col items-center">
        <canvas
          ref={canvasRef}
          width={420}
          height={340}
          className="w-full max-w-[440px] rounded-lg border border-slate-800 bg-slate-950"
        />
        <div className="w-full flex flex-wrap items-center justify-center gap-4 mt-3 text-[11px] text-slate-400 font-mono">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-sky-400" /> Detected Vehicle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-red-500" /> Emergency Vehicle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-400/60" /> Queue Length
          </span>
        </div>
      </div>
    </Card>
  )
}
