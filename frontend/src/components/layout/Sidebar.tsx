import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Camera,
  BarChart3,
  TrafficCone,
  Siren,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Smartphone,
  ShieldCheck,
} from 'lucide-react'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { authApi } from '../../services/api'
import { wsService } from '../../services/websocket'

const NAV_ITEMS = [
  { to: '/', label: 'Control Room', icon: LayoutDashboard },
  { to: '/cameras', label: 'Cameras', icon: Camera },
  { to: '/signals', label: 'Signal Control', icon: TrafficCone },
  { to: '/emergency', label: 'Emergency', icon: Siren },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const { emergencyState, isAutoMode } = useAppStore()

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('auth_user')
      wsService.disconnect()
      navigate('/login')
    }
  }

  return (
    <aside
      className={clsx(
        'flex flex-col bg-slate-900/95 border-r border-slate-800 transition-all duration-200 select-none shrink-0',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Brand header */}
      <div className="h-14 flex items-center justify-between px-3 border-b border-slate-800">
        {!collapsed && (
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center shrink-0">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="truncate">
              <p className="text-sm font-bold tracking-tight text-slate-100">SmartTraffic</p>
              <p className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">Junction 001</p>
            </div>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors ml-auto"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Mode pill */}
      {!collapsed && (
        <div className="px-3 pt-3 pb-1">
          <div
            className={clsx(
              'px-2.5 py-1.5 rounded-lg border text-xs font-mono flex items-center justify-between',
              emergencyState.active
                ? 'bg-red-500/15 border-red-500/40 text-red-400'
                : isAutoMode
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
            )}
          >
            <span>MODE</span>
            <span className="font-bold">
              {emergencyState.active ? 'EMERGENCY' : isAutoMode ? 'AI AUTO' : 'MANUAL'}
            </span>
          </div>
        </div>
      )}

      {/* Navigation links */}
      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
          const isEmergencyNav = to === '/emergency'
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/70 border border-transparent'
                )
              }
              title={collapsed ? label : undefined}
            >
              <div className="relative shrink-0">
                <Icon className={clsx('w-4 h-4', isEmergencyNav && emergencyState.active && 'text-red-400 animate-pulse')} />
                {isEmergencyNav && emergencyState.active && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-red-500 animate-ping" />
                )}
              </div>
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          )
        })}

        <div className="pt-3 mt-3 border-t border-slate-800">
          <NavLink
            to="/camera"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-400 hover:text-cyan-400 hover:bg-slate-800/70 transition-all"
            title={collapsed ? 'Mobile Camera PWA' : undefined}
          >
            <Smartphone className="w-4 h-4 shrink-0" />
            {!collapsed && <span className="truncate">Mobile Camera UI</span>}
          </NavLink>
        </div>
      </nav>

      {/* Footer logout */}
      <div className="p-2 border-t border-slate-800">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          title={collapsed ? 'Sign out' : undefined}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>
    </aside>
  )
}
