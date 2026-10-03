import { Headphones, LoaderCircle, Pause, Play } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'

/** 83 -> "1:23"; unknown (NaN/Infinity) -> "–:––" */
const clock = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds < 0) return '–:––'
  const s = Math.floor(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/**
 * Plays a spoken summary.
 * - Default: loads the file's length up front; renders nothing if the file doesn't exist.
 * - lazy: for audio generated on request (translations, the daily briefing): nothing loads until
 *   play is pressed, a spinner shows while it is being generated, and failures are reported.
 */
export function AudioPlayer({ src, lazy = false, label = 'Listen' }: { src: string; lazy?: boolean; label?: string }) {
  const audio = useRef<HTMLAudioElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'missing' | 'failed'>(lazy ? 'ready' : 'loading')
  const [playing, setPlaying] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(0)

  if (status === 'missing') return null
  if (status === 'failed') {
    return <span role="status" className="text-sm text-muted">Audio isn&apos;t available right now.</span>
  }

  const toggle = () => {
    const el = audio.current
    if (!el) return
    if (el.paused) {
      setWaiting(true)
      void el.play().catch(() => setStatus(lazy ? 'failed' : 'missing'))
    } else {
      el.pause()
    }
  }

  return (
    <div className="flex h-10 items-center gap-3 rounded-full border border-rule bg-surface pr-4 pl-1">
      <audio
        ref={audio}
        src={src}
        preload={lazy ? 'none' : 'metadata'}
        onLoadedMetadata={(e) => {
          setDuration(e.currentTarget.duration)
          setStatus('ready')
        }}
        onError={() => {
          setWaiting(false)
          setStatus(lazy ? 'failed' : 'missing')
        }}
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        onWaiting={() => setWaiting(true)}
        onPlaying={() => setWaiting(false)}
        onPlay={() => setPlaying(true)}
        onPause={() => {
          setPlaying(false)
          setWaiting(false)
        }}
        onEnded={() => setPlaying(false)}
      />
      <Button
        variant="primary"
        size="icon"
        className="size-8"
        onClick={toggle}
        disabled={status !== 'ready'}
        aria-label={playing ? 'Pause' : label}
      >
        {waiting ? <LoaderCircle className="animate-spin" /> : playing ? <Pause /> : <Play />}
      </Button>
      <span className="flex items-center gap-1.5 text-sm font-medium">
        <Headphones className="size-4 text-muted" aria-hidden /> {waiting && !duration ? 'Preparing…' : label}
      </span>
      <input
        type="range"
        min={0}
        max={duration || 0}
        step={0.1}
        value={time}
        disabled={!duration}
        onChange={(e) => {
          if (audio.current) audio.current.currentTime = Number(e.target.value)
        }}
        aria-label="Seek"
        className="hidden w-24 accent-[var(--accent)] sm:block"
      />
      <span className="text-xs tabular-nums text-faint">
        {clock(time)} / {duration ? clock(duration) : '–:––'}
      </span>
    </div>
  )
}
