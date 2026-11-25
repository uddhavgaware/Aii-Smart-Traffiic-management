import { useEffect, useState } from 'react'
import clsx from 'clsx'

interface CountdownTimerProps {
  seconds: number
  phase: 'RED' | 'YELLOW' | 'GREEN'
  size?: 'sm' | 'md' | 'lg'
}

export function CountdownTimer({ seconds, phase, size = 'md' }: CountdownTimerProps) {
  const [displayed, setDisplayed] = useState(seconds)

  useEffect(() => {
    setDisplayed(seconds)
  }, [seconds])

  const colors = {
    RED: 'text-red-400',
    YELLOW: 'text-amber-400',
    GREEN: 'text-emerald-400',
  }

  const sizes = {
    sm: 'text-lg font-bold font-mono',
    md: 'text-2xl font-bold font-mono',
    lg: 'text-4xl font-bold font-mono',
  }

  return (
    <span className={clsx(sizes[size], colors[phase])}>
      {displayed.toString().padStart(2, '0')}s
    </span>
  )
}
