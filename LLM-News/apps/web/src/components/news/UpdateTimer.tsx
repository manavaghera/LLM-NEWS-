import { RefreshCw } from 'lucide-react'
import { useUpdateStatus } from '@/api/queries'
import { useNow } from '@/hooks/useNow'
import { countdown, updatesRunning } from '@/lib/updates'

/** "Updated 2:05 PM · next update in 34 min" for the edition the updater works on */
export function UpdateTimer({ date }: { date: string }) {
  const status = useUpdateStatus().data
  const now = useNow(30_000)
  if (!status?.last_update || (status.date && status.date !== date)) return null
  const updated = new Date(status.last_update).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  return (
    <p className="flex items-center gap-1.5 text-sm text-muted">
      <RefreshCw className="size-3.5 shrink-0" aria-hidden />
      <span>
        Updated {updated}
        {updatesRunning(status, now) && status.next_update && <> · next update {countdown(status.next_update, now)}</>}
      </span>
    </p>
  )
}
