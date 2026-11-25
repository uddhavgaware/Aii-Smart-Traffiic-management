import { RefreshCw, Trash2, Wifi, WifiOff } from 'lucide-react'
import { Direction, CameraFeed as CameraFeedType } from '../../store/appStore'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { StatusIndicator } from '../ui/StatusIndicator'

interface CameraRecord {
  id: number
  unique_id: string
  direction: Direction
  status: string
  ip_address?: string | null
  last_seen?: string | null
}

interface CameraCardProps {
  direction: Direction
  camera?: CameraRecord
  feed: CameraFeedType
  onReconnect: (direction: Direction) => void
  onUnregister: (direction: Direction) => void
}

export function CameraCard({ direction, camera, feed, onReconnect, onUnregister }: CameraCardProps) {
  const isRegistered = Boolean(camera)
  const isOnline = feed.status === 'connected' || camera?.status === 'online'

  return (
    <Card
      title={`${direction.toUpperCase()} Approach Camera`}
      subtitle={camera ? `ID: ${camera.unique_id}` : 'Not registered'}
      headerRight={<StatusIndicator status={isOnline ? 'online' : camera?.status === 'connecting' ? 'connecting' : 'offline'} size="xs" />}
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <div className="p-2 rounded bg-slate-900/70 border border-slate-800">
            <span className="text-[10px] text-slate-500 block">STREAM FPS</span>
            <span className="text-slate-100 font-bold">{feed.fps.toFixed(1)}</span>
          </div>
          <div className="p-2 rounded bg-slate-900/70 border border-slate-800">
            <span className="text-[10px] text-slate-500 block">VEHICLES</span>
            <span className="text-cyan-400 font-bold">{feed.vehicleCount}</span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            {isOnline ? <Wifi className="w-3.5 h-3.5 text-emerald-400" /> : <WifiOff className="w-3.5 h-3.5 text-slate-500" />}
            {camera?.ip_address ?? 'WebRTC Cross-Network'}
          </span>
          <Badge variant={isRegistered ? 'cyan' : 'default'} size="xs">
            {isRegistered ? 'Registered' : 'Unpaired'}
          </Badge>
        </div>

        {isRegistered && (
          <div className="flex gap-2 pt-1">
            <Button
              variant="secondary"
              size="xs"
              className="flex-1"
              leftIcon={<RefreshCw className="w-3 h-3" />}
              onClick={() => onReconnect(direction)}
            >
              Reconnect
            </Button>
            <Button
              variant="danger"
              size="xs"
              leftIcon={<Trash2 className="w-3 h-3" />}
              onClick={() => onUnregister(direction)}
            >
              Remove
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}
