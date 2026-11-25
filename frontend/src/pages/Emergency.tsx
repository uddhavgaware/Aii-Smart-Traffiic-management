import { useEffect, useState } from 'react'
import { emergencyApi } from '../services/api'
import { EmergencyPanel } from '../components/dashboard/EmergencyPanel'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'

interface EmergencyLogRow {
  id: number
  timestamp: string
  direction: string
  vehicle_type: string
  stage1_detected: boolean
  stage2_confirmed: boolean
  confidence: number
  cleared_at?: string | null
  signal_response?: string | null
}

export default function Emergency() {
  const [history, setHistory] = useState<EmergencyLogRow[]>([])
  const [loading, setLoading] = useState(false)

  const loadHistory = async () => {
    setLoading(true)
    try {
      const res = await emergencyApi.getHistory(50)
      setHistory(res.data ?? [])
    } catch {
      toast.error('Failed to load emergency event history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-slate-100">Emergency Vehicle Priority Center</h1>
          <p className="text-xs text-slate-400">
            Two-stage visual verification (Stage 1 class detection + Stage 2 flashing beacon temporal confirmation) for Ambulances & Fire Brigades
          </p>
        </div>
        <button
          onClick={loadHistory}
          className="p-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-cyan-400"
          title="Reload emergency history"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <EmergencyPanel />

      <Card title="Emergency Audit Log" subtitle="All recorded Stage 1 / Stage 2 detections and signal priority responses">
        {history.length === 0 ? (
          <div className="py-10 text-center text-xs text-slate-500">
            No emergency events recorded in database yet
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2 pr-4">Timestamp</th>
                  <th className="py-2 pr-4">Vehicle</th>
                  <th className="py-2 pr-4">Direction</th>
                  <th className="py-2 pr-4">Stage 1</th>
                  <th className="py-2 pr-4">Stage 2</th>
                  <th className="py-2 pr-4">Confidence</th>
                  <th className="py-2 pr-4">Signal Action</th>
                  <th className="py-2">Cleared</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {history.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 pr-4 text-slate-300">{new Date(row.timestamp).toLocaleString()}</td>
                    <td className="py-2.5 pr-4 uppercase text-red-400 font-semibold">{row.vehicle_type}</td>
                    <td className="py-2.5 pr-4 uppercase text-cyan-400">{row.direction}</td>
                    <td className="py-2.5 pr-4">
                      <Badge variant={row.stage1_detected ? 'success' : 'default'} size="xs">
                        {row.stage1_detected ? 'YES' : 'NO'}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-4">
                      <Badge variant={row.stage2_confirmed ? 'error' : 'warning'} size="xs">
                        {row.stage2_confirmed ? 'CONFIRMED' : 'UNCONFIRMED'}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-4">{(row.confidence * 100).toFixed(0)}%</td>
                    <td className="py-2.5 pr-4 text-slate-300">{row.signal_response ?? 'Monitored'}</td>
                    <td className="py-2.5 text-slate-400">
                      {row.cleared_at ? new Date(row.cleared_at).toLocaleTimeString() : 'Active'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
