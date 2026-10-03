import { LoaderCircle, Newspaper, Sparkles } from 'lucide-react'
import { Link } from 'react-router'
import { media } from '@/api/client'
import { useDigest, useNews } from '@/api/queries'
import { AudioPlayer } from '@/components/article/AudioPlayer'
import { Kicker } from '@/components/news/parts'
import { EmptyState, ErrorState } from '@/components/ui/feedback'
import { useEdition } from '@/hooks/useEdition'
import { CATEGORIES, categoryInfo, formatLongDate, plural } from '@/lib/format'

/** LLM output as readable lines: "text", ["a", "b"] or {"k": "v"} all become a list of strings. */
function textItems(value: unknown): string[] {
  if (typeof value === 'string') return value.trim() ? [value.trim()] : []
  if (Array.isArray(value)) return value.flatMap(textItems)
  if (value && typeof value === 'object') return Object.values(value).flatMap(textItems)
  if (typeof value === 'number') return [String(value)]
  return []
}

function TextBlock({ value }: { value: unknown }) {
  const items = textItems(value)
  if (items.length <= 1) return items[0] ? <p className="leading-relaxed">{items[0]}</p> : null
  return (
    <ul className="list-disc space-y-2 pl-5 leading-relaxed">
      {items.map((item, i) => <li key={i}>{item}</li>)}
    </ul>
  )
}

function Writing() {
  return (
    <div role="status" className="flex flex-col items-center gap-3 rounded-2xl border border-rule bg-surface px-6 py-16 text-center">
      <LoaderCircle className="size-6 animate-spin text-accent" aria-hidden />
      <p className="headline text-2xl">Writing the briefing…</p>
      <p className="text-sm text-muted">The AI reads every story of the day. This takes about 15 seconds, only the first time.</p>
    </div>
  )
}

export function DigestPage() {
  const edition = useEdition()
  const digest = useDigest(edition.date)
  const news = useNews(edition.date)

  if (edition.error) {
    return <ErrorState title="Couldn't reach the news server" error={edition.error} onRetry={() => edition.refetch()} />
  }
  if (!edition.isLoading && !edition.date) {
    return <EmptyState icon={<Newspaper />} title="No news to summarise yet">Generate today&apos;s articles first.</EmptyState>
  }

  const pathFor = (headline: string) => {
    const item = news.data?.find((n) => n.headline === headline)
    return item ? `/article/${item.date}/${item.group_id}` : null
  }
  const data = digest.data
  const order = [...CATEGORIES.map((c) => c.value as string)]
  const breakdown = Object.entries(data?.category_breakdown ?? {}).sort(([a], [b]) => {
    const ia = order.indexOf(a)
    const ib = order.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-10 space-y-2 border-b border-rule pb-8">
        <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
          <Sparkles className="size-4" aria-hidden /> Daily Digest
        </p>
        <h1 className="headline text-4xl font-semibold tracking-tight sm:text-5xl">
          {edition.date ? formatLongDate(edition.date) : 'Daily Digest'}
        </h1>
        {data && <p className="text-muted">The day in {plural(data.total_articles, 'story')}, summarised by AI.</p>}
        {data && !data.error && edition.date && (
          <div className="pt-2">
            <AudioPlayer key={edition.date} lazy src={media.briefing(edition.date)} label="Listen to the briefing" />
          </div>
        )}
      </header>

      {(edition.isLoading || digest.isLoading) && <Writing />}
      {digest.error && <ErrorState title="Couldn't write the digest" error={digest.error} onRetry={() => digest.refetch()} />}

      {data && (
        <div className="space-y-12">
          {data.error ? (
            <ErrorState title="The AI couldn't write the digest" error={new Error(data.digest)} onRetry={() => digest.refetch()} />
          ) : (
            <p className="headline text-2xl leading-relaxed">{data.digest}</p>
          )}

          {textItems(data.highlights).length > 0 && (
            <section aria-labelledby="highlights" className="space-y-4">
              <h2 id="highlights" className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">Top highlights</h2>
              <ol className="space-y-4">
                {textItems(data.highlights).map((highlight, i) => (
                  <li key={i} className="flex gap-4">
                    <span className="headline w-6 shrink-0 text-2xl font-semibold text-accent">{i + 1}</span>
                    <p className="pt-1 leading-relaxed">{highlight}</p>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {breakdown.length > 0 && (
            <section aria-labelledby="by-category" className="space-y-6">
              <h2 id="by-category" className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">By category</h2>
              {breakdown.map(([category, info]) => {
                const summary = data.category_summary?.[category] ?? data.category_summary?.[categoryInfo(category).label]
                return (
                  <div key={category} className="space-y-3 rounded-2xl border border-rule bg-surface p-6">
                    <div className="flex items-baseline justify-between gap-2">
                      <Kicker category={category} />
                      <span className="text-xs text-faint">{plural(info.count, 'story')}</span>
                    </div>
                    <TextBlock value={summary} />
                    <ul className="space-y-2 border-t border-rule pt-3">
                      {info.headlines.map((headline) => {
                        const path = pathFor(headline)
                        return (
                          <li key={headline} className="headline text-lg leading-snug">
                            {path ? <Link to={path} className="hover:text-accent hover:underline">{headline}</Link> : headline}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )
              })}
            </section>
          )}

          {textItems(data.trends).length > 0 && (
            <section aria-labelledby="patterns" className="rounded-2xl bg-sunken p-6">
              <h2 id="patterns" className="mb-3 text-sm font-semibold uppercase tracking-[0.14em] text-muted">Patterns to watch</h2>
              <TextBlock value={data.trends} />
            </section>
          )}
        </div>
      )}
    </div>
  )
}
