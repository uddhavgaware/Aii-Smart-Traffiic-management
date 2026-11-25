import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { QrCode, Copy, Check } from 'lucide-react'
import { Direction } from '../../store/appStore'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import toast from 'react-hot-toast'

interface QRRegistrationProps {
  junctionCode: string
  selectedDirection: Direction
  onDirectionChange: (dir: Direction) => void
  onRefreshCode?: () => void
}

const DIRECTIONS: Direction[] = ['north', 'south', 'east', 'west']

export function QRRegistration({
  junctionCode,
  selectedDirection,
  onDirectionChange,
  onRefreshCode,
}: QRRegistrationProps) {
  const [copied, setCopied] = useState(false)
  const defaultOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000'
  const [publicOrigin, setPublicOrigin] = useState(() => {
    if (typeof window === 'undefined') return defaultOrigin
    if (window.location.protocol === 'https:') return window.location.origin
    return localStorage.getItem('smarttraffic_public_origin') || defaultOrigin
  })

  const cleanOrigin = publicOrigin.trim().replace(/\/$/, '') || defaultOrigin
  const mobileUrl = `${cleanOrigin}/camera?junction=${encodeURIComponent(junctionCode)}&direction=${selectedDirection}`

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(mobileUrl)
      setCopied(true)
      toast.success('Camera pairing URL copied')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Clipboard permission denied')
    }
  }

  return (
    <Card
      title="QR Code Camera Pairing"
      subtitle="Scan with mobile phone to auto-assign direction and open PWA streamer"
      headerRight={<QrCode className="w-4 h-4 text-cyan-400" />}
    >
      <div className="flex flex-col md:flex-row items-center gap-6">
        <div className="p-4 bg-white rounded-xl shrink-0">
          <QRCodeSVG value={mobileUrl} size={168} level="M" />
        </div>

        <div className="flex-1 space-y-3 w-full">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Mobile HTTPS Base URL (required by phone cameras)</label>
            <input
              type="url"
              value={publicOrigin}
              onChange={(e) => {
                setPublicOrigin(e.target.value)
                localStorage.setItem('smarttraffic_public_origin', e.target.value)
              }}
              placeholder="https://your-tunnel.trycloudflare.com"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Assign Direction</label>
            <div className="grid grid-cols-4 gap-2">
              {DIRECTIONS.map((dir) => (
                <button
                  key={dir}
                  onClick={() => onDirectionChange(dir)}
                  className={`py-2 px-2 rounded-lg text-xs font-mono uppercase border transition-colors ${
                    selectedDirection === dir
                      ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 font-bold'
                      : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500'
                  }`}
                >
                  {dir}
                </button>
              ))}
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
            <div className="text-slate-500 text-[10px]">JUNCTION PAIRING CODE</div>
            <div className="text-cyan-400 font-bold text-sm mt-0.5">{junctionCode}</div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={handleCopy} leftIcon={copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}>
              {copied ? 'Copied URL' : 'Copy Pairing Link'}
            </Button>
            {onRefreshCode && (
              <Button variant="outline" size="sm" onClick={onRefreshCode}>
                Regenerate Code
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}
