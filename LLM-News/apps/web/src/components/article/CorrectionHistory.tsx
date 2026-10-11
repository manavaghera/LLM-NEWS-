import { useQuery } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { api } from '@/api/client'

export function CorrectionHistory({ date, groupId }: { date: string; groupId: string }) {
  const query = useQuery({ queryKey: ['corrections', date, groupId], queryFn: () => api.corrections(date, groupId) })
  if (query.error) return <p role="status" className="text-sm text-muted">Correction history is temporarily unavailable. <button type="button" onClick={() => { void query.refetch() }} className="text-accent underline">Try again</button></p>
  if (!query.data?.corrections.length) return null
  return (
    <section aria-labelledby="correction-history" className="space-y-3 rounded-2xl border border-accent/40 bg-accent-soft/40 p-5">
      <h2 id="correction-history" className="flex items-center gap-2 font-semibold"><History className="size-4" aria-hidden /> Corrections & updates</h2>
      <ol className="space-y-4">
        {query.data.corrections.map((note) => (
          <li key={note.id}>
            <time dateTime={note.created_at} className="text-xs text-muted">{new Date(note.created_at).toLocaleString()}</time>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{note.text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
