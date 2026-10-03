import { ShieldCheck } from 'lucide-react'
import { useAccuracy } from '@/api/queries'
import { formatShortDate, plural } from '@/lib/format'
import { ChartCard, StatTile } from './chartKit'

/** Fact-check results over time: how much of each day's writing the second AI pass removed */
export function AccuracyCard({ days }: { days: number }) {
  const accuracy = useAccuracy(days)
  const checkedDays = (accuracy.data?.days ?? []).filter((d) => d.checked > 0)
  const latest = checkedDays.at(-1)
  const reports = (accuracy.data?.days ?? []).reduce((sum, d) => sum + (d.reader_reports ?? 0), 0)

  return (
    <ChartCard
      title="Fact-check results"
      subtitle="Share of each day's AI-written statements that a second AI pass couldn't match to the sources (removed before publishing)"
      table={{
        columns: ['Day', 'Articles checked', 'Statements', 'Removed', 'Reader reports'],
        rows: (accuracy.data?.days ?? []).map((d) => [
          formatShortDate(d.date), `${d.checked} of ${d.articles}`, d.statements,
          d.removed_pct === null ? '–' : `${d.removed} (${d.removed_pct}%)`, d.reader_reports ?? 0,
        ]),
      }}
    >
      {!latest ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <ShieldCheck className="size-4" aria-hidden /> No fact-checked articles yet. They appear when the news script runs with checks on.
        </p>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatTile label="Statements removed" value={`${latest.removed_pct}%`} note={`${latest.removed} of ${latest.statements} · ${formatShortDate(latest.date)}`} />
            <StatTile label="Articles fact-checked" value={latest.checked} note={`of ${plural(latest.articles, 'article')} that day`} />
            <StatTile label="Reader reports" value={reports} note={`in the last ${days} days`} />
          </div>
          {(accuracy.data?.models.length ?? 0) > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-medium">By model</h3>
              <ul className="divide-y divide-rule rounded-xl bg-sunken text-sm">
                {accuracy.data!.models.map((m) => (
                  <li key={`${m.writer}|${m.checker}`} className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-3">
                    <span>
                      <span className="text-muted">Writer</span> <code className="text-xs">{m.writer}</code>
                      <span className="text-muted"> · checked by </span>
                      <code className="text-xs">{m.checker === m.writer ? 'the same model' : m.checker}</code>
                    </span>
                    <span className="tabular-nums">
                      <strong>{m.removed_pct ?? '–'}%</strong> removed <span className="text-faint">({plural(m.articles, 'article')})</span>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-faint">Lower is better. A model checking its own writing tends to miss the same mistakes.</p>
            </div>
          )}
        </div>
      )}
    </ChartCard>
  )
}
