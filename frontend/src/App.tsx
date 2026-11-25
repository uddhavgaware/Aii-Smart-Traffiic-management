import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useAppStore } from './store/appStore'
import { wsService } from './services/websocket'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Cameras from './pages/Cameras'
import Analytics from './pages/Analytics'
import Signals from './pages/Signals'
import Emergency from './pages/Emergency'
import Settings from './pages/Settings'
import Login from './pages/Login'
import MobileCamera from './pages/MobileCamera'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('auth_token')
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
  const { isDemoMode } = useAppStore()

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      wsService.connect()
    }
    return () => {
      wsService.disconnect()
    }
  }, [])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/camera" element={<MobileCamera />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout isDemoMode={isDemoMode}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/cameras" element={<Cameras />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/signals" element={<Signals />} />
                <Route path="/emergency" element={<Emergency />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
