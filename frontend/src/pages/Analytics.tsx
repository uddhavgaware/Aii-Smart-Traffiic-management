import { useEffect, useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { Download, Calendar } from 'lucide-react'
import { trafficApi, emergencyApi, signalApi } from '../services/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import toast from 'react-hot-toast'

interface HistoryPoint {
  time: string
  north: number
  south: number
  east: number
  west: number
  densityAvg: number
}

export default function Analytics() {
  const [period, setPeriod] = useState<'1h' | '6h' | '24h' | '7d'>('24h')
  const [series, setSeries] = useState<HistoryPoint[]>([])
  const [summary, setSummary] = useState<{
    total_vehicles: number
    avg_wait_time_seconds: number
    total_emergency_events: number
    total_signal_changes: number
    congestion_by_direction: { direction: string; congestion_events: number; avg_queue: number }[]
  } | null>(null)
  const [emergencies, setEmergencies] = useState<Array<{ id: number; timestamp: string; direction: string; vehicle_type: string; stage2_confirmed: boolean; confidence: number }>>([])
  const [signals, setSignals] = useState<Array<{ id: number; timestamp: string; direction: string; phase: string; duration: number; triggered_by: string; reason: string }>>([])

  const loadAnalytics = async () => {
    try {
      const [anRes, histRes, emRes, sigRes] = await Promise.allSettled([
        trafficApi.getAnalytics(period),
        trafficApi.getHistory(undefined, period === '1h' ? 1 : period === '6h' ? 6 : period === '7d' ? 168 : 24),
        emergencyApi.getHistory(20),
        signalApi.getHistory(30),
      ])

      if (anRes.status === 'fulfilled') {
        setSummary(anRes.value.data)
      }

      if (histRes.status === 'fulfilled') {
        const rows = (histRes.value.data ?? []) as Array<{
          timestamp: string
          direction: string
          vehicle_count: number
          density_level: string
        }>
        const buckets = new Map<string, HistoryPoint>()
        const densityMap: Record<string, number> = { low: 15, normal: 35, medium: 55, high: 80, traffic_jam: 95 }
        rows.forEach((r) => {
          const t = new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          const existing = buckets.get(t) ?? { time: t, north: 0, south: 0, east: 0, west: 0, densityAvg: 0 }
          if (r.direction === 'north' || r.direction === 'south' || r.direction === 'east' || r.direction === 'west') {
            existing[r.direction] = r.vehicle_count
          }
          existing.densityAvg = densityMap[r.density_level?.toLowerCase()] ?? 20
          buckets.set(t, existing)
        })
        setSeries(Array.from(buckets.values()).slice(-30))
      }

      if (emRes.status === 'fulfilled') setEmergencies(emRes.value.data ?? [])
      if (sigRes.status === 'fulfilled') setSignals(sigRes.value.data ?? [])
    } catch {
      toast.error('Unable to load historical analytics')
    }
  }

  useEffect(() => {
    loadAnalytics()
  }, [period])

  const handleExportCSV = async () => {
    try {
      const hours = period === '1h' ? 1 : period === '6h' ? 6 : period === '7d' ? 168 : 24
      const to = Math.floor(Date.now() / 1000)
      const from = to - hours * 3600
      const res = await trafficApi.exportCSV(from, to)
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `smarttraffic-report-${period}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('CSV report downloaded')
    } catch {
      toast.error('Failed to export CSV report')
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-slate-100">Traffic Analytics & Reporting</h1>
          <p className="text-xs text-slate-400">Historical vehicle counts, congestion duration, emergency log, and CSV export</p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs font-mono">
            <Calendar className="w-3.5 h-3.5 text-slate-400 mx-1.5" />
            {(['1h', '6h', '24h', '7d'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2.5 py-1 rounded ${period === p ? 'bg-cyan-500/20 text-cyan-400 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
              >
                {p}
              </button>
            ))}
          </div>

          <Button variant="primary" size="sm" leftIcon={<Download className="w-4 h-4" />} onClick={handleExportCSV}>
            Export CSV
          </Button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <span className="metric-label">Total Recorded Vehicles</span>
          <p className="metric-value text-cyan-400 mt-1">{summary?.total_vehicles ?? 0}</p>
        </Card>
        <Card>
          <span className="metric-label">Avg Wait Estimate</span>
          <p className="metric-value text-slate-100 mt-1">{(summary?.avg_wait_time_seconds ?? 0).toFixed(1)}s</p>
        </Card>
        <Card>
          <span className="metric-label">Signal Transitions</span>
          <p className="metric-value text-emerald-400 mt-1">{summary?.total_signal_changes ?? signals.length}</p>
        </Card>
        <Card>
          <span className="metric-label">Emergency Events</span>
          <p className="metric-value text-red-400 mt-1">{summary?.total_emergency_events ?? emergencies.length}</p>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Vehicle Counts by Direction" subtitle="Recorded per-direction volume over time">
          {series.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-xs text-slate-500">
              No recorded traffic events in this time window yet
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }} />
                  <Legend />
                  <Line type="monotone" dataKey="north" stroke="#22d3ee" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="south" stroke="#34d399" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="east" stroke="#fbbf24" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="west" stroke="#a78bfa" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Traffic Density History" subtitle="Aggregate density score over selected window">
          {series.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-xs text-slate-500">
              No density telemetry recorded yet
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }} />
                  <Area type="monotone" dataKey="densityAvg" name="Density %" stroke="#22d3ee" fill="#06b6d4" fillOpacity={0.2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {/* Congestion by direction & Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Congestion Events by Approach" subtitle="High / Traffic Jam occurrences per direction">
          {!summary?.congestion_by_direction?.length ? (
            <div className="h-56 flex items-center justify-center text-xs text-slate-500">
              No congestion events logged yet
            </div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={summary.congestion_by_direction}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="direction" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }} />
                  <Bar dataKey="congestion_events" name="Congestion Events" fill="#fbbf24" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Recent Signal Timing Log" subtitle="Executed phases with deterministic reason">
          <div className="max-h-56 overflow-y-auto divide-y divide-slate-800 text-xs font-mono">
            {signals.length === 0 ? (
              <p className="py-12 text-center text-slate-500">No signal changes recorded yet</p>
            ) : (
              signals.map((s) => (
                <div key={s.id} className="py-2 flex items-center justify-between gap-2">
                  <div>
                    <span className="text-cyan-400 uppercase font-bold">{s.direction}</span>{' '}
                    <Badge variant={s.phase === 'GREEN' ? 'success' : s.phase === 'YELLOW' ? 'warning' : 'error'} size="xs">
                      {s.phase}
                    </Badge>{' '}
                    <span className="text-slate-400">({s.duration}s)</span>
                    <p className="text-[11px] text-slate-500 mt-0.5">{s.reason}</p>
                  </div>
                  <span className="text-slate-500 shrink-0">{new Date(s.timestamp).toLocaleTimeString()}</span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
