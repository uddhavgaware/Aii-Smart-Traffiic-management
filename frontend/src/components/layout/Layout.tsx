import { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

interface LayoutProps {
  children: ReactNode
  isDemoMode: boolean
}

export default function Layout({ children, isDemoMode }: LayoutProps) {
  return (
    <div className="min-h-screen flex bg-slate-950 text-slate-100 grid-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {isDemoMode && (
          <div className="demo-banner flex items-center justify-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>
              DEMO MODE ACTIVE — Using simulated sample traffic data and simulated ESP32 responses. Not connected to live hardware.
            </span>
          </div>
        )}
        <TopBar />
        <main className="flex-1 p-4 md:p-5 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
