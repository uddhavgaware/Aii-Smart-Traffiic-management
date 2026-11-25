import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Lock, User } from 'lucide-react'
import { authApi } from '../services/api'
import { wsService } from '../services/websocket'
import { Button } from '../components/ui/Button'
import toast from 'react-hot-toast'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    try {
      const res = await authApi.login(username.trim(), password)
      localStorage.setItem('auth_token', res.data.access_token)
      if (res.data.refresh_token) {
        localStorage.setItem('refresh_token', res.data.refresh_token)
      }
      try {
        const me = await authApi.me()
        localStorage.setItem('auth_user', JSON.stringify(me.data))
      } catch {
        localStorage.setItem('auth_user', JSON.stringify({ username: username.trim(), role: 'operator' }))
      }
      wsService.connect(res.data.access_token)
      toast.success('Authenticated')
      navigate('/')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg ?? 'Invalid credentials or backend offline')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 grid-bg p-4">
      <div className="w-full max-w-md card p-8 space-y-6">
        <div className="flex flex-col items-center text-center">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center mb-3">
            <ShieldCheck className="w-6 h-6 text-cyan-400" />
          </div>
          <h1 className="text-xl font-bold text-slate-100">SmartTraffic AI Control</h1>
          <p className="text-xs text-slate-400 mt-1">
            Intelligent Four-Way Junction Management System
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Username</label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <Button type="submit" variant="primary" isLoading={loading} className="w-full">
            Sign In to Control Room
          </Button>
        </form>

        <div className="pt-4 border-t border-slate-800 text-center">
          <a href="/camera" className="text-xs text-cyan-400 hover:text-cyan-300 font-medium">
            Open Mobile Camera Streamer (/camera) →
          </a>
        </div>
      </div>
    </div>
  )
}
