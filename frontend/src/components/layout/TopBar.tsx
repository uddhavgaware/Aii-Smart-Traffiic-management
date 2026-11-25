import { useEffect, useState } from 'react'
import { Bell, Cpu, Radio, User as UserIcon, CheckCheck, Trash2, Clock } from 'lucide-react'
import clsx from 'clsx'
import { useAppStore, Direction } from '../../store/appStore'
import { StatusIndicator } from '../ui/StatusIndicator'
import { Badge } from '../ui/Badge'

const DIRECTIONS: { key: Direction; short: string }[] = [
  { key: 'north', short: 'N' },
  { key: 'south', short: 'S' },
  { key: 'east', short: 'E' },
  { key: 'west', short: 'W' },
]

export default function TopBar() {
  const [now, setNow] = useState(() => new Date())
  const [notifOpen, setNotifOpen] = useState(false)

  const {
    systemStatus,
    notifications,
    markNotificationRead,
    clearNotifications,
    emergencyState,
  } = useAppStore()

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const unreadCount = notifications.filter((n) => !n.read).length
  const storedUser = (() => {
    try {
      const raw = localStorage.getItem('auth_user')
      return raw ? JSON.parse(raw) : { username: 'operator', role: 'admin' }
    } catch {
      return { username: 'operator', role: 'admin' }
    }
  })()

  return (
    <header className="h-14 bg-slate-900/90 border-b border-slate-800 px-4 flex items-center justify-between gap-4 shrink-0 relative z-30">
      {/* Left: Project & Statuses */}
      <div className="flex items-center gap-4 overflow-x-auto no-scrollbar">
        <div className="hidden md:flex items-center gap-2 pr-3 border-r border-slate-800">
          <span className="text-xs font-semibold text-slate-300 tracking-wide uppercase">
            AI Intelligent Traffic Control
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-800/80 border border-slate-700/80">
            <span className="text-slate-500">Junction:</span>
            <StatusIndicator status={systemStatus.junctionStatus} size="xs" />
          </div>

          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-800/80 border border-slate-700/80">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-500">AI:</span>
            <StatusIndicator status={systemStatus.aiEngineStatus} size="xs" />
          </div>

          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-800/80 border border-slate-700/80">
            <Radio className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-500">ESP32:</span>
            <StatusIndicator
              status={systemStatus.esp32Connected}
              label={systemStatus.esp32Connected ? 'Connected' : 'Offline'}
              size="xs"
            />
          </div>

          {/* 4 Camera indicators */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700/80">
            <span className="text-slate-500 mr-1">Cams:</span>
            {DIRECTIONS.map(({ key, short }) => {
              const connected = systemStatus.camerasConnected[key]
              return (
                <span
                  key={key}
                  title={`${key.toUpperCase()} camera: ${connected ? 'Connected' : 'Offline'}`}
                  className={clsx(
                    'w-5 h-5 rounded text-[10px] font-mono font-bold flex items-center justify-center border',
                    connected
                      ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                      : 'bg-slate-900 text-slate-500 border-slate-700'
                  )}
                >
                  {short}
                </span>
              )
            })}
          </div>

          {emergencyState.active && (
            <Badge variant="error" dot pulse>
              EMERGENCY: {emergencyState.type?.toUpperCase()} ({emergencyState.direction?.toUpperCase()})
            </Badge>
          )}
        </div>
      </div>

      {/* Right: Clock, Notifications, User */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="hidden sm:flex items-center gap-1.5 text-xs font-mono text-slate-300 bg-slate-800/70 px-2.5 py-1 rounded-md border border-slate-700/70">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>{now.toLocaleTimeString()}</span>
        </div>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen((o) => !o)}
            className="relative p-2 rounded-lg bg-slate-800/70 hover:bg-slate-800 border border-slate-700 text-slate-300 transition-colors"
            aria-label="Notification centre"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden z-50">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Notifications ({notifications.length})
                </span>
                <div className="flex items-center gap-2">
                  {notifications.length > 0 && (
                    <button
                      onClick={clearNotifications}
                      className="text-xs text-slate-400 hover:text-red-400 flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" /> Clear
                    </button>
                  )}
                </div>
              </div>
              <div className="max-h-80 overflow-y-auto divide-y divide-slate-800">
                {notifications.length === 0 ? (
                  <p className="py-8 text-center text-xs text-slate-500">No notifications yet</p>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      onClick={() => markNotificationRead(n.id)}
                      className={clsx(
                        'px-4 py-2.5 cursor-pointer hover:bg-slate-800/60 transition-colors flex items-start gap-2.5',
                        !n.read && 'bg-slate-800/30'
                      )}
                    >
                      <span
                        className={clsx(
                          'w-2 h-2 rounded-full mt-1.5 shrink-0',
                          n.type === 'error'
                            ? 'bg-red-500'
                            : n.type === 'warning'
                            ? 'bg-amber-400'
                            : n.type === 'success'
                            ? 'bg-emerald-400'
                            : 'bg-cyan-400'
                        )}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-slate-200 leading-snug">{n.message}</p>
                        <p className="text-[10px] font-mono text-slate-500 mt-1">
                          {new Date(n.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                      {!n.read && <CheckCheck className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-1" />}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Profile */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
            <UserIcon className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="hidden md:block leading-tight">
            <p className="text-xs font-medium text-slate-200">{storedUser.username}</p>
            <p className="text-[10px] font-mono uppercase text-slate-500">{storedUser.role}</p>
          </div>
        </div>
      </div>
    </header>
  )
}
