import { Activity, Cpu, HardDrive, Gauge } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { Card } from '../ui/Card'
import { DensityBar } from '../ui/DensityBar'

export function PerformancePanel() {
  const metrics = useAppStore((s) => s.performanceMetrics)
  const vramPct = metrics.vramTotal > 0 ? (metrics.vramUsed / metrics.vramTotal) * 100 : 0

  return (
    <Card
      title="Hardware & Inference Telemetry"
      subtitle="Real measured host CPU, RTX GPU, VRAM, and latency"
    >
      <div className="space-y-3">
        <DensityBar value={metrics.cpuUsage} label="CPU Utilization" height="sm" />
        <DensityBar value={metrics.gpuUsage} label="GPU Utilization (CUDA)" height="sm" />
        <DensityBar
          value={vramPct}
          label={`GPU VRAM (${metrics.vramUsed.toFixed(2)} / ${metrics.vramTotal.toFixed(1)} GB)`}
          height="sm"
        />
        <DensityBar value={metrics.memoryUsage} label="System RAM" height="sm" />

        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800 text-center">
          <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
            <div className="flex items-center justify-center gap-1 text-[10px] text-slate-500 font-mono">
              <Gauge className="w-3 h-3 text-cyan-400" /> LATENCY
            </div>
            <p className="text-sm font-bold font-mono text-slate-100 mt-0.5">
              {metrics.inferenceLatency > 0 ? `${metrics.inferenceLatency.toFixed(1)}ms` : '—'}
            </p>
          </div>

          <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
            <div className="flex items-center justify-center gap-1 text-[10px] text-slate-500 font-mono">
              <Activity className="w-3 h-3 text-emerald-400" /> THROUGHPUT
            </div>
            <p className="text-sm font-bold font-mono text-slate-100 mt-0.5">
              {metrics.detectionFps > 0 ? `${metrics.detectionFps.toFixed(1)} FPS` : '—'}
            </p>
          </div>

          <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
            <div className="flex items-center justify-center gap-1 text-[10px] text-slate-500 font-mono">
              <HardDrive className="w-3 h-3 text-amber-400" /> TARGET
            </div>
            <p className="text-sm font-bold font-mono text-slate-300 mt-0.5">
              ~20 FPS
            </p>
          </div>
        </div>
      </div>
    </Card>
  )
}
